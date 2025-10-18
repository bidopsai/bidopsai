"""
Parser Agent Structured Output Model

Pydantic model for Parser Agent to ensure deterministic, parseable outputs.
The Parser Agent processes documents using Bedrock Data Automation and returns
structured information about processed files.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import Field, field_validator

from .base import TimestampedModel


class ProcessedDocument(TimestampedModel):
    """Information about a single processed document."""
    
    document_id: UUID = Field(description="ProjectDocument database ID")
    file_name: str = Field(min_length=1, description="Original file name")
    file_type: str = Field(description="Document type (pdf/docx/xlsx/audio/video)")
    
    # Processing results
    raw_file_location: str = Field(min_length=1, description="S3 URI of original file")
    processed_file_location: str = Field(
        min_length=1,
        description="S3 URI of processed file from Bedrock DA"
    )
    
    # Processing metadata
    processing_time_seconds: float = Field(ge=0.0, description="Time taken to process")
    file_size_bytes: Optional[int] = Field(None, ge=0, description="Original file size")
    
    # Extracted data summary
    extracted_text_length: Optional[int] = Field(
        None,
        ge=0,
        description="Length of extracted text"
    )
    tables_found: int = Field(default=0, ge=0, description="Number of tables extracted")
    pages_processed: Optional[int] = Field(None, ge=0, description="Number of pages")
    
    # Status
    processing_status: str = Field(
        default="success",
        description="Processing status (success/partial/failed)"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if processing failed"
    )
    
    @field_validator("file_type")
    @classmethod
    def validate_file_type(cls, v: str) -> str:
        """Validate file type is supported."""
        valid_types = {"pdf", "docx", "xlsx", "audio", "video", "doc", "xls"}
        if v.lower() not in valid_types:
            raise ValueError(f"File type must be one of {valid_types}")
        return v.lower()
    
    @field_validator("processing_status")
    @classmethod
    def validate_processing_status(cls, v: str) -> str:
        """Validate processing status."""
        valid_statuses = {"success", "partial", "failed"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v


class ParserOutput(TimestampedModel):
    """
    Structured output from Parser Agent.
    
    This model enforces consistent, parseable responses from the Parser Agent
    when processing project documents via Bedrock Data Automation.
    
    The agent autonomously:
    1. Queries database for project documents
    2. Processes each document using Bedrock DA MCP
    3. Updates database with processed file locations
    4. Returns this structured output
    
    Example:
        ```python
        output = ParserOutput(
            status="completed",
            total_documents=3,
            documents_processed=3,
            documents_failed=0,
            processed_files=[
                ProcessedDocument(
                    document_id=UUID("..."),
                    file_name="rfp_requirements.pdf",
                    file_type="pdf",
                    raw_file_location="s3://bucket/raw/file.pdf",
                    processed_file_location="s3://bucket/processed/file.json",
                    processing_time_seconds=5.2,
                    extracted_text_length=15000,
                    tables_found=3,
                    processing_status="success"
                ),
                ...
            ],
            message="Successfully processed 3 documents"
        )
        ```
    """
    
    # Overall status
    status: str = Field(
        description="Overall parsing status (completed/partial/failed)"
    )
    
    # Counts
    total_documents: int = Field(ge=0, description="Total documents to process")
    documents_processed: int = Field(
        ge=0,
        description="Number of documents successfully processed"
    )
    documents_failed: int = Field(
        ge=0,
        description="Number of documents that failed processing"
    )
    
    # Processed files detail
    processed_files: List[ProcessedDocument] = Field(
        description="Detailed information about each processed document"
    )
    
    # Execution metadata
    total_processing_time_seconds: float = Field(
        ge=0.0,
        description="Total time spent processing all documents"
    )
    
    # Summary message
    message: str = Field(
        min_length=1,
        description="Human-readable summary of parsing results"
    )
    
    # Error details (if any failures)
    errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of errors encountered during processing"
    )
    
    # Database updates
    database_updates_successful: bool = Field(
        default=True,
        description="Whether all ProjectDocument records were updated successfully"
    )
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate overall status."""
        valid_statuses = {"completed", "partial", "failed"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v
    
    @field_validator("documents_processed")
    @classmethod
    def validate_processed_count(cls, v: int, info) -> int:
        """Ensure processed count doesn't exceed total."""
        if "total_documents" in info.data and v > info.data["total_documents"]:
            raise ValueError("documents_processed cannot exceed total_documents")
        return v
    
    @field_validator("documents_failed")
    @classmethod
    def validate_failed_count(cls, v: int, info) -> int:
        """Ensure failed count doesn't exceed total."""
        if "total_documents" in info.data and v > info.data["total_documents"]:
            raise ValueError("documents_failed cannot exceed total_documents")
        return v
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_documents == 0:
            return 0.0
        return (self.documents_processed / self.total_documents) * 100.0
    
    @property
    def has_failures(self) -> bool:
        """Check if any documents failed processing."""
        return self.documents_failed > 0


__all__ = ["ParserOutput", "ProcessedDocument"]