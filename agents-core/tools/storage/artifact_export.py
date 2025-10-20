"""
Artifact Export Utilities

Converts artifacts from database formats (TipTap JSON, Q&A JSON, Table JSON)
to exportable file formats (PDF, DOCX, XLSX) and uploads to S3.

Responsibilities:
- Convert TipTap JSON → PDF/DOCX
- Convert Q&A JSON → PDF
- Convert Table JSON → XLSX
- Upload to S3 with naming convention
- Update artifact version location in database
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
import io

from core.error_handling import AgentError, ErrorCode, ErrorSeverity
from core.observability import log_agent_action
from tools.database import (
    get_artifact,
    get_latest_artifact_version,
    update_artifact_version
)


class ArtifactExporter:
    """
    Export artifacts to S3 in various file formats.
    
    Converts internal JSON representations to user-friendly file formats.
    """
    
    def __init__(self, s3_client: Any, bucket_name: str):
        """
        Initialize artifact exporter.
        
        Args:
            s3_client: Boto3 S3 client
            bucket_name: S3 bucket for artifacts
        """
        self.s3_client = s3_client
        self.bucket_name = bucket_name
    
    async def export_artifacts(
        self,
        artifact_ids: List[UUID],
        project_id: UUID
    ) -> List[Dict[str, str]]:
        """
        Export multiple artifacts to S3.
        
        Args:
            artifact_ids: List of artifact IDs to export
            project_id: Project ID for S3 path
            
        Returns:
            List of dicts with artifact_id and s3_location
            
        Raises:
            AgentError: On export failure
        """
        results = []
        
        for artifact_id in artifact_ids:
            try:
                location = await self._export_single_artifact(
                    artifact_id=artifact_id,
                    project_id=project_id
                )
                results.append({
                    "artifact_id": str(artifact_id),
                    "s3_location": location
                })
            except Exception as e:
                log_agent_action(
                    agent_name="artifact_exporter",
                    action="export_error",
                    details={
                        "artifact_id": str(artifact_id),
                        "error": str(e)
                    },
                    level="error"
                )
                # Continue with other artifacts
                continue
        
        if not results:
            raise AgentError(
                code=ErrorCode.AGENT_NO_RESULTS,
                message="No artifacts exported successfully",
                severity=ErrorSeverity.HIGH
            )
        
        return results
    
    async def _export_single_artifact(
        self,
        artifact_id: UUID,
        project_id: UUID
    ) -> str:
        """
        Export single artifact to S3.
        
        Args:
            artifact_id: Artifact ID
            project_id: Project ID
            
        Returns:
            S3 URI of exported file
        """
        # Get artifact metadata
        artifact = await get_artifact(artifact_id=artifact_id)
        
        # Get latest version
        version = await get_latest_artifact_version(artifact_id=artifact_id)
        
        if not version:
            raise AgentError(
                code=ErrorCode.AGENT_NO_DATA_FOUND,
                message=f"No version found for artifact {artifact_id}",
                severity=ErrorSeverity.MEDIUM
            )
        
        # Determine conversion and upload
        artifact_type = artifact["type"]
        artifact_category = artifact["category"]
        content = version["content"]
        
        # Generate S3 key
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = artifact["name"].replace(" ", "_").replace("/", "-")
        
        # Convert based on type
        if artifact_type in ["worddoc", "pdf"] and artifact_category == "document":
            # TipTap JSON → PDF (simplified - use library like reportlab or weasyprint)
            file_data, extension = await self._convert_tiptap_to_pdf(content, safe_name)
        elif artifact_type == "pdf" and artifact_category == "q_and_a":
            # Q&A JSON → PDF
            file_data, extension = await self._convert_qa_to_pdf(content, safe_name)
        elif artifact_type == "excel":
            # Table JSON → XLSX
            file_data, extension = await self._convert_table_to_xlsx(content, safe_name)
        else:
            # Default: save JSON
            file_data = json.dumps(content, indent=2).encode('utf-8')
            extension = "json"
        
        # Upload to S3
        s3_key = f"projects/{project_id}/artifacts/{safe_name}_{timestamp}.{extension}"
        
        await self._upload_to_s3(
            file_data=file_data,
            s3_key=s3_key,
            content_type=self._get_content_type(extension)
        )
        
        s3_uri = f"s3://{self.bucket_name}/{s3_key}"
        
        # Update artifact version location
        await update_artifact_version(
            version_id=UUID(version["id"]),
            location=s3_uri
        )
        
        log_agent_action(
            agent_name="artifact_exporter",
            action="artifact_exported",
            details={
                "artifact_id": str(artifact_id),
                "s3_uri": s3_uri,
                "extension": extension
            }
        )
        
        return s3_uri
    
    async def _convert_tiptap_to_pdf(
        self,
        tiptap_content: Dict[str, Any],
        filename: str
    ) -> Tuple[bytes, str]:
        """
        Convert TipTap JSON to PDF.
        
        Note: This is a simplified implementation. For production,
        use libraries like reportlab, weasyprint, or pdfkit.
        
        Args:
            tiptap_content: TipTap JSON structure
            filename: Base filename
            
        Returns:
            Tuple of (pdf_bytes, extension)
        """
        # TODO: Implement actual TipTap → PDF conversion
        # For now, return placeholder
        
        # Simplified: Convert to markdown-like text
        text = self._tiptap_to_text(tiptap_content)
        
        # Return as text file for now (replace with PDF generation)
        return text.encode('utf-8'), "txt"
    
    async def _convert_qa_to_pdf(
        self,
        qa_content: Dict[str, Any],
        filename: str
    ) -> Tuple[bytes, str]:
        """
        Convert Q&A JSON to PDF.
        
        Args:
            qa_content: Q&A JSON structure
            filename: Base filename
            
        Returns:
            Tuple of (pdf_bytes, extension)
        """
        # TODO: Implement actual Q&A → PDF conversion
        # For now, return placeholder
        
        # Simplified: Format as text
        text_lines = []
        
        if "q_and_a" in qa_content:
            for item in qa_content["q_and_a"]:
                text_lines.append(f"Q: {item.get('question', 'N/A')}\n")
                text_lines.append(f"A: {item.get('proposed_answer', 'N/A')}\n\n")
        
        text = "\n".join(text_lines)
        return text.encode('utf-8'), "txt"
    
    async def _convert_table_to_xlsx(
        self,
        table_content: Dict[str, Any],
        filename: str
    ) -> Tuple[bytes, str]:
        """
        Convert table JSON to XLSX.
        
        Args:
            table_content: Table JSON structure
            filename: Base filename
            
        Returns:
            Tuple of (xlsx_bytes, extension)
        """
        # TODO: Implement actual table → XLSX conversion
        # Use openpyxl or xlsxwriter library
        
        # For now, return CSV format
        csv_lines = []
        
        if "rows" in table_content:
            for row in table_content["rows"]:
                csv_lines.append(",".join(str(cell) for cell in row))
        
        csv_text = "\n".join(csv_lines)
        return csv_text.encode('utf-8'), "csv"
    
    def _tiptap_to_text(self, tiptap_content: Dict[str, Any]) -> str:
        """
        Convert TipTap JSON to plain text (simplified).
        
        Args:
            tiptap_content: TipTap JSON
            
        Returns:
            Plain text representation
        """
        lines = []
        
        if "content" in tiptap_content:
            for block in tiptap_content["content"]:
                if block.get("type") == "heading":
                    level = block.get("attrs", {}).get("level", 1)
                    text = self._extract_text_from_block(block)
                    lines.append(f"{'#' * level} {text}\n")
                elif block.get("type") == "paragraph":
                    text = self._extract_text_from_block(block)
                    lines.append(f"{text}\n")
                elif block.get("type") in ["bulletList", "orderedList"]:
                    for item in block.get("content", []):
                        text = self._extract_text_from_block(item)
                        lines.append(f"- {text}\n")
        
        return "\n".join(lines)
    
    def _extract_text_from_block(self, block: Dict[str, Any]) -> str:
        """Extract text from TipTap block."""
        if "content" in block:
            texts = []
            for item in block["content"]:
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif "content" in item:
                    texts.append(self._extract_text_from_block(item))
            return " ".join(texts)
        return ""
    
    async def _upload_to_s3(
        self,
        file_data: bytes,
        s3_key: str,
        content_type: str
    ) -> None:
        """
        Upload file to S3.
        
        Args:
            file_data: File bytes
            s3_key: S3 key
            content_type: MIME type
        """
        try:
            # Upload to S3
            await asyncio.to_thread(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_data,
                ContentType=content_type
            )
        except Exception as e:
            raise AgentError(
                code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message=f"S3 upload failed: {str(e)}",
                severity=ErrorSeverity.HIGH,
                details={"s3_key": s3_key}
            ) from e
    
    def _get_content_type(self, extension: str) -> str:
        """Get MIME type for file extension."""
        content_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv": "text/csv",
            "txt": "text/plain",
            "json": "application/json"
        }
        return content_types.get(extension, "application/octet-stream")


# Factory function
def create_artifact_exporter(s3_client: Any, bucket_name: str) -> ArtifactExporter:
    """
    Factory function to create Artifact Exporter.
    
    Args:
        s3_client: Boto3 S3 client
        bucket_name: S3 bucket name
        
    Returns:
        ArtifactExporter instance
    """
    return ArtifactExporter(s3_client=s3_client, bucket_name=bucket_name)