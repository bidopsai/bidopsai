"""
S3 storage tools for document and artifact management.

Provides tools for agents to interact with AWS S3 for uploading/downloading
documents, generating presigned URLs, and managing artifact storage.

All tool functions use the @tool decorator for Strands Agent integration.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError
from strands import tool

from core.config import get_config
from core.error_handling import (
    ErrorCode,
    ErrorSeverity,
    RetryableError,
    handle_errors,
    retry_with_backoff,
)
from core.observability import trace_operation

logger = logging.getLogger(__name__)


class S3Manager:
    """AWS S3 manager for file operations."""
    
    _instance: Optional["S3Manager"] = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize S3 client."""
        if not hasattr(self, "_initialized"):
            config = get_config()
            self.bucket_name = config.get("AWS_S3_BUCKET_NAME")
            self.region = config.get("AWS_REGION", "us-east-1")
            
            # Initialize S3 client
            self.s3_client = boto3.client(
                "s3",
                region_name=self.region,
                aws_access_key_id=config.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=config.get("AWS_SECRET_ACCESS_KEY"),
            )
            
            self._initialized = True
            logger.info(f"S3Manager initialized (bucket: {self.bucket_name})")
    
    @trace_operation("s3_upload")
    @retry_with_backoff(max_retries=3)
    async def upload_file(
        self,
        file_content: bytes,
        s3_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Upload file to S3.
        
        Args:
            file_content: File content as bytes
            s3_key: S3 object key (path)
            content_type: MIME type
            metadata: Additional metadata
            
        Returns:
            S3 URI (s3://bucket/key)
        """
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            if metadata:
                extra_args["Metadata"] = metadata
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                **extra_args
            )
            
            s3_uri = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"Uploaded file to {s3_uri}")
            
            return s3_uri
        
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            raise RetryableError(
                f"S3 upload failed: {error_code}",
                error_code=ErrorCode.S3_UPLOAD_ERROR,
                severity=ErrorSeverity.HIGH,
                original_exception=e,
            )
    
    @trace_operation("s3_download")
    @retry_with_backoff(max_retries=3)
    async def download_file(self, s3_uri: str) -> bytes:
        """
        Download file from S3.
        
        Args:
            s3_uri: S3 URI (s3://bucket/key) or just the key
            
        Returns:
            File content as bytes
        """
        try:
            # Parse S3 URI
            if s3_uri.startswith("s3://"):
                parsed = urlparse(s3_uri)
                bucket = parsed.netloc
                key = parsed.path.lstrip("/")
            else:
                bucket = self.bucket_name
                key = s3_uri
            
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response["Body"].read()
            
            logger.info(f"Downloaded file from s3://{bucket}/{key}")
            
            return content
        
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            raise RetryableError(
                f"S3 download failed: {error_code}",
                error_code=ErrorCode.S3_DOWNLOAD_ERROR,
                severity=ErrorSeverity.HIGH,
                original_exception=e,
            )
    
    @trace_operation("s3_presigned_url")
    async def generate_presigned_url(
        self,
        s3_key: str,
        expiration_seconds: int = 3600,
        operation: str = "get_object",
    ) -> str:
        """
        Generate presigned URL for S3 object.
        
        Args:
            s3_key: S3 object key
            expiration_seconds: URL expiration time
            operation: S3 operation (get_object/put_object)
            
        Returns:
            Presigned URL
        """
        try:
            params = {"Bucket": self.bucket_name, "Key": s3_key}
            
            url = self.s3_client.generate_presigned_url(
                ClientMethod=operation,
                Params=params,
                ExpiresIn=expiration_seconds
            )
            
            logger.info(f"Generated presigned URL for {s3_key} (expires in {expiration_seconds}s)")
            
            return url
        
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise
    
    @trace_operation("s3_list_objects")
    async def list_objects(
        self,
        prefix: str = "",
        max_keys: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        List objects in S3 bucket.
        
        Args:
            prefix: Key prefix to filter
            max_keys: Maximum number of keys to return
            
        Returns:
            List of object metadata
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            objects = []
            for obj in response.get("Contents", []):
                objects.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "etag": obj["ETag"],
                })
            
            logger.info(f"Listed {len(objects)} objects with prefix '{prefix}'")
            
            return objects
        
        except ClientError as e:
            logger.error(f"Failed to list objects: {e}")
            raise
    
    @trace_operation("s3_delete")
    async def delete_object(self, s3_key: str) -> bool:
        """
        Delete object from S3.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if successful
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Deleted object: {s3_key}")
            return True
        
        except ClientError as e:
            logger.error(f"Failed to delete object: {e}")
            return False
    
    @trace_operation("s3_copy")
    async def copy_object(
        self,
        source_key: str,
        destination_key: str,
        source_bucket: Optional[str] = None,
    ) -> str:
        """
        Copy object within S3.
        
        Args:
            source_key: Source object key
            destination_key: Destination object key
            source_bucket: Source bucket (defaults to same bucket)
            
        Returns:
            Destination S3 URI
        """
        try:
            source_bucket = source_bucket or self.bucket_name
            copy_source = {"Bucket": source_bucket, "Key": source_key}
            
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=destination_key
            )
            
            dest_uri = f"s3://{self.bucket_name}/{destination_key}"
            logger.info(f"Copied {source_key} to {dest_uri}")
            
            return dest_uri
        
        except ClientError as e:
            logger.error(f"Failed to copy object: {e}")
            raise


# Singleton instance
def get_s3_manager() -> S3Manager:
    """Get singleton S3Manager instance."""
    return S3Manager()


# ==============================================================================
# TOOL FUNCTIONS (for ToolManager registration)
# ==============================================================================

@tool
@handle_errors
async def upload_file_to_s3(
    file_content: bytes,
    s3_key: str,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Upload file to S3 (tool function)."""
    s3 = get_s3_manager()
    s3_uri = await s3.upload_file(file_content, s3_key, content_type, metadata)
    
    return {
        "success": True,
        "s3_uri": s3_uri,
        "bucket": s3.bucket_name,
        "key": s3_key,
    }


@tool
@handle_errors
async def download_file_from_s3(s3_uri: str) -> Dict[str, Any]:
    """Download file from S3 (tool function)."""
    s3 = get_s3_manager()
    content = await s3.download_file(s3_uri)
    
    return {
        "success": True,
        "content": content,
        "size_bytes": len(content),
    }


@tool
@handle_errors
async def generate_s3_presigned_url(
    s3_key: str,
    expiration_seconds: int = 3600,
    operation: str = "get_object",
) -> Dict[str, Any]:
    """Generate presigned URL (tool function)."""
    s3 = get_s3_manager()
    url = await s3.generate_presigned_url(s3_key, expiration_seconds, operation)
    
    expires_at = datetime.utcnow() + timedelta(seconds=expiration_seconds)
    
    return {
        "success": True,
        "url": url,
        "expires_at": expires_at.isoformat(),
        "expiration_seconds": expiration_seconds,
    }


@tool
@handle_errors
async def list_s3_objects(
    prefix: str = "",
    max_keys: int = 1000
) -> Dict[str, Any]:
    """List S3 objects (tool function)."""
    s3 = get_s3_manager()
    objects = await s3.list_objects(prefix, max_keys)
    
    return {
        "success": True,
        "objects": objects,
        "count": len(objects),
        "prefix": prefix,
    }


@tool
@handle_errors
async def delete_s3_object(s3_key: str) -> Dict[str, Any]:
    """Delete S3 object (tool function)."""
    s3 = get_s3_manager()
    success = await s3.delete_object(s3_key)
    
    return {
        "success": success,
        "key": s3_key,
    }


@tool
@handle_errors
async def copy_s3_object(
    source_key: str,
    destination_key: str,
    source_bucket: Optional[str] = None,
) -> Dict[str, Any]:
    """Copy S3 object (tool function)."""
    s3 = get_s3_manager()
    dest_uri = await s3.copy_object(source_key, destination_key, source_bucket)
    
    return {
        "success": True,
        "source_key": source_key,
        "destination_key": destination_key,
        "destination_uri": dest_uri,
    }