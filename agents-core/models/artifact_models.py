"""
Artifact-related Pydantic models for BidOpsAI AgentCore.

These models represent artifacts (documents/deliverables) created during
workflow execution, including their versions and content structures.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from .base import IdentifiedModel, TimestampedModel


class TipTapContent(TimestampedModel):
    """
    TipTap editor JSON content structure.
    
    This matches the TipTap document format used by the frontend rich text editor.
    """
    
    type: str = Field(default="doc", description="Document type")
    content: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Array of TipTap nodes (paragraphs, headings, etc.)"
    )


class QAndAItem(TimestampedModel):
    """Single Q&A item for Q&A type artifacts."""
    
    question: str = Field(min_length=1)
    proposed_answer: str
    past_answers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Historical answers with references"
    )
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    requires_review: bool = Field(default=False)
    
    # Optional metadata
    question_id: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = Field(None, description="HIGH/MEDIUM/LOW")


class QAndAContent(TimestampedModel):
    """Content structure for Q&A documents."""
    
    q_and_a: List[QAndAItem] = Field(
        default_factory=list,
        description="List of questions and answers"
    )
    total_questions: int = Field(ge=0)
    answered_questions: int = Field(ge=0)
    review_required_count: int = Field(ge=0)


class TableRow(TimestampedModel):
    """Single row in a table/spreadsheet."""
    
    row_id: str
    cells: Dict[str, Any] = Field(
        description="Column name -> cell value mapping"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TableContent(TimestampedModel):
    """Content structure for table/Excel artifacts."""
    
    columns: List[Dict[str, str]] = Field(
        description="Column definitions (name, type, description)"
    )
    rows: List[TableRow] = Field(default_factory=list)
    total_rows: int = Field(ge=0)
    has_formulas: bool = Field(default=False)
    sheet_name: str = Field(default="Sheet1")


class ArtifactMetadata(TimestampedModel):
    """Metadata for artifacts."""
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_modified_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: UUID
    updated_by: UUID
    
    # Version tracking
    version: int = Field(default=1, ge=1)
    is_latest: bool = Field(default=True)
    
    # Content stats
    word_count: Optional[int] = Field(None, ge=0)
    page_count: Optional[int] = Field(None, ge=0)
    
    # Quality metrics
    completeness_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    compliance_status: Optional[str] = None
    qa_status: Optional[str] = None


class ArtifactContent(TimestampedModel):
    """
    Flexible artifact content that can hold different content types.
    
    The actual structure depends on the artifact category:
    - document: TipTapContent
    - q_and_a: QAndAContent
    - excel: TableContent
    """
    
    # Use one of these based on category
    tiptap: Optional[TipTapContent] = Field(
        None,
        description="TipTap JSON for document type"
    )
    qa: Optional[QAndAContent] = Field(
        None,
        description="Q&A structure for q_and_a type"
    )
    table: Optional[TableContent] = Field(
        None,
        description="Table structure for excel type"
    )
    
    # Raw content as fallback
    raw: Optional[Dict[str, Any]] = Field(
        None,
        description="Raw content if other formats don't apply"
    )


class Artifact(IdentifiedModel):
    """
    Represents a document/deliverable artifact.
    
    Corresponds to artifacts table in database.
    """
    
    project_id: UUID
    name: str = Field(min_length=1, max_length=500)
    
    # Type classification
    type: str = Field(
        description="File type (worddoc/pdf/ppt/excel)"
    )
    category: str = Field(
        description="Content category (document/q_and_a/excel)"
    )
    
    # Status
    status: str = Field(
        default="DRAFT",
        description="Artifact status (DRAFT/REVIEW/APPROVED/REJECTED)"
    )
    
    # User tracking
    created_by: UUID
    approved_by: Optional[UUID] = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    
    # Tags for categorization
    tags: List[str] = Field(
        default_factory=list,
        description="Tags like system_design, cover_letter, exec_summary"
    )
    
    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate artifact type."""
        valid_types = {"worddoc", "pdf", "ppt", "excel"}
        if v not in valid_types:
            raise ValueError(f"Type must be one of {valid_types}")
        return v
    
    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate artifact category."""
        valid_categories = {"document", "q_and_a", "excel"}
        if v not in valid_categories:
            raise ValueError(f"Category must be one of {valid_categories}")
        return v
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate artifact status."""
        valid_statuses = {"DRAFT", "REVIEW", "APPROVED", "REJECTED"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v


class ArtifactVersion(IdentifiedModel):
    """
    Represents a specific version of an artifact.
    
    Corresponds to artifact_versions table in database.
    """
    
    artifact_id: UUID
    version_number: int = Field(ge=1)
    
    # Content
    content: ArtifactContent
    
    # S3 location (for exported files)
    location: Optional[str] = Field(
        None,
        description="S3 path to exported file"
    )
    
    # User tracking
    created_by: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: ArtifactMetadata


class ArtifactWithVersion(TimestampedModel):
    """
    Combined artifact with its latest version.
    
    Used for API responses that need both artifact info and content.
    """
    
    artifact: Artifact
    version: ArtifactVersion
    
    # Computed fields
    is_editable: bool = Field(
        default=True,
        description="Whether artifact can be edited"
    )
    requires_export: bool = Field(
        default=False,
        description="Whether artifact needs to be exported to S3"
    )


class ArtifactTile(TimestampedModel):
    """
    Lightweight artifact info for tile display in frontend.
    
    Used when sending artifacts_ready event to show clickable tiles.
    """
    
    id: UUID
    name: str
    type: str
    category: str
    status: str
    tags: List[str]
    
    # Display info
    icon: str = Field(description="Icon name for frontend")
    preview: Optional[str] = Field(
        None,
        max_length=200,
        description="Short preview text"
    )
    
    # Metadata
    created_at: datetime
    last_modified_at: datetime
    version: int
    
    # Feedback indicators
    has_compliance_issues: bool = Field(default=False)
    has_qa_issues: bool = Field(default=False)
    completeness_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class ComplianceFeedback(TimestampedModel):
    """Compliance feedback for an artifact."""
    
    section: str = Field(description="Section/heading/question identifier")
    issues: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of compliance issues found"
    )


class QAFeedback(TimestampedModel):
    """QA feedback for an artifact."""
    
    section_or_question_or_table: str
    description: str
    status: str = Field(
        description="Status (met/partially_met/not_met)"
    )
    references: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Supporting references"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Improvement suggestions"
    )
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status field."""
        valid_statuses = {"met", "partially_met", "not_met"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v


class ArtifactFeedback(TimestampedModel):
    """Combined feedback for an artifact (from Compliance and QA agents)."""
    
    artifact_id: UUID
    artifact_name: str
    artifact_type: str
    
    # Feedback from agents
    compliance_feedback: List[ComplianceFeedback] = Field(default_factory=list)
    qa_feedback: List[QAFeedback] = Field(default_factory=list)
    
    # Summary
    overall_status: str = Field(
        description="Overall status (pass/partial/fail)"
    )
    total_issues: int = Field(ge=0)
    critical_issues: int = Field(ge=0)
    
    @field_validator("overall_status")
    @classmethod
    def validate_overall_status(cls, v: str) -> str:
        """Validate overall status."""
        valid_statuses = {"pass", "partial", "fail"}
        if v not in valid_statuses:
            raise ValueError(f"Overall status must be one of {valid_statuses}")
        return v


class ArtifactExport(TimestampedModel):
    """Information about an exported artifact."""
    
    artifact_id: UUID
    version_number: int
    s3_location: str
    file_size_bytes: int = Field(ge=0)
    export_format: str = Field(description="Export format (native/pdf/docx)")
    exported_by: UUID
    exported_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(
        None,
        description="Expiration time for presigned URL"
    )
    download_url: Optional[str] = Field(
        None,
        description="Presigned download URL"
    )