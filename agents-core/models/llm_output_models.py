"""
LLM structured output models for BidOpsAI AgentCore.

These Pydantic models enforce structured outputs from LLM calls to ensure
consistent, parseable responses from agents. Used with Bedrock/Anthropic
structured output features.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from .base import TimestampedModel


class DocumentInfo(TimestampedModel):
    """Extracted document information."""
    
    document_type: str = Field(description="Type of document (RFP/RFI/tender/contract)")
    title: str = Field(min_length=1)
    reference_number: Optional[str] = None
    issue_date: Optional[datetime] = None
    submission_deadline: Optional[datetime] = None
    page_count: Optional[int] = Field(None, ge=0)
    language: str = Field(default="en")


class ClientInfo(TimestampedModel):
    """Client information extracted from documents."""
    
    name: str = Field(min_length=1, description="Client organization name")
    location: Optional[str] = Field(None, description="City, State/Country")
    domain: Optional[str] = Field(None, description="Industry domain")
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None


class Stakeholder(TimestampedModel):
    """Key stakeholder information."""
    
    name: str = Field(min_length=1)
    role: str = Field(description="Role in the project")
    department: Optional[str] = None
    responsibilities: List[str] = Field(
        default_factory=list,
        description="Key responsibilities"
    )
    contact_info: Optional[str] = None


class RequiredDocument(TimestampedModel):
    """Document required for submission."""
    
    name: str = Field(min_length=1)
    type: str = Field(
        description="Document type (questionnaire/due_diligence/system_design/etc.)"
    )
    format: str = Field(description="Required format (pdf/doc/excel/ppt)")
    mandatory: bool = Field(default=True)
    description: Optional[str] = Field(
        None,
        description="Description of what should be included"
    )
    page_limit: Optional[int] = Field(None, ge=0)
    special_requirements: List[str] = Field(default_factory=list)


class SubmissionMethod(TimestampedModel):
    """How to submit the bid/proposal."""
    
    method: str = Field(description="Submission method (email/portal/physical)")
    portal_url: Optional[str] = None
    portal_login_required: bool = Field(default=False)
    email_address: Optional[str] = None
    physical_address: Optional[str] = None
    instructions: List[str] = Field(
        default_factory=list,
        description="Step-by-step submission instructions"
    )


class AnalysisOutput(TimestampedModel):
    """
    Structured output from Analysis Agent.
    
    This is the LLM-generated analysis of RFP/bid documents.
    """
    
    # Document metadata
    document_info: DocumentInfo
    
    # Client details
    client: ClientInfo
    stakeholders: List[Stakeholder] = Field(default_factory=list)
    
    # Understanding the ask
    project_summary: str = Field(
        min_length=50,
        description="Summary of what client is asking for"
    )
    key_requirements: List[str] = Field(
        min_length=1,
        description="Key requirements from the RFP"
    )
    scope_of_work: str = Field(description="Detailed scope of work")
    
    # Opportunity analysis
    opportunities: List[str] = Field(
        default_factory=list,
        description="Key opportunities for our company"
    )
    challenges: List[str] = Field(
        default_factory=list,
        description="Potential challenges or risks"
    )
    competitive_advantages: List[str] = Field(
        default_factory=list,
        description="Our advantages for this opportunity"
    )
    
    # Process understanding
    bid_process: str = Field(description="Current RFP/bid process")
    evaluation_criteria: List[str] = Field(
        default_factory=list,
        description="How bids will be evaluated"
    )
    
    # Deliverables
    required_documents: List[RequiredDocument] = Field(
        min_length=1,
        description="Documents that must be provided"
    )
    
    # Timeline
    key_dates: Dict[str, datetime] = Field(
        default_factory=dict,
        description="Important dates (submission_deadline, presentation_date, etc.)"
    )
    
    # Submission
    submission_method: SubmissionMethod
    
    # Additional insights
    special_instructions: List[str] = Field(
        default_factory=list,
        description="Any special instructions or notes"
    )
    
    # Confidence
    analysis_confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence in analysis accuracy"
    )
    areas_needing_clarification: List[str] = Field(
        default_factory=list,
        description="Areas where human clarification is needed"
    )


class ContentGenerationPlan(TimestampedModel):
    """Plan for content generation from Content Agent."""
    
    artifact_name: str = Field(min_length=1)
    artifact_type: str = Field(description="worddoc/pdf/excel/ppt")
    artifact_category: str = Field(description="document/q_and_a/excel")
    tags: List[str] = Field(default_factory=list)
    
    # Content plan
    outline: List[str] = Field(
        description="Outline of sections/topics to cover"
    )
    estimated_length: Optional[int] = Field(
        None,
        ge=0,
        description="Estimated word/page count"
    )
    
    # Knowledge requirements
    knowledge_queries: List[str] = Field(
        default_factory=list,
        description="Queries to make to knowledge base"
    )
    
    # Priority
    priority: str = Field(
        default="MEDIUM",
        description="Priority level (HIGH/MEDIUM/LOW)"
    )


class ComplianceCheck(TimestampedModel):
    """Single compliance check result."""
    
    check_name: str = Field(min_length=1)
    check_category: str = Field(
        description="Category (legal/security/financial/quality)"
    )
    status: str = Field(description="Status (pass/fail/warning)")
    severity: str = Field(description="Severity if failed (CRITICAL/HIGH/MEDIUM/LOW)")
    description: str = Field(description="What was checked")
    findings: List[str] = Field(
        default_factory=list,
        description="Issues found"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="How to fix issues"
    )
    references: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Reference documents/standards"
    )
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status field."""
        valid_statuses = {"pass", "fail", "warning"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v


class ComplianceOutput(TimestampedModel):
    """
    Structured output from Compliance Agent.
    
    LLM-generated compliance review of artifacts.
    """
    
    artifact_id: UUID
    artifact_name: str
    
    # Compliance checks
    checks: List[ComplianceCheck] = Field(
        min_length=1,
        description="Individual compliance checks performed"
    )
    
    # Summary
    overall_status: str = Field(
        description="Overall compliance status (compliant/non_compliant/partial)"
    )
    total_checks: int = Field(ge=0)
    passed_checks: int = Field(ge=0)
    failed_checks: int = Field(ge=0)
    warnings: int = Field(ge=0)
    
    # Critical issues
    blocking_issues: List[str] = Field(
        default_factory=list,
        description="Issues that must be fixed before approval"
    )
    
    # Recommendation
    recommendation: str = Field(
        description="Overall recommendation (approve/reject/revise)"
    )
    
    @field_validator("overall_status")
    @classmethod
    def validate_overall_status(cls, v: str) -> str:
        """Validate overall status."""
        valid_statuses = {"compliant", "non_compliant", "partial"}
        if v not in valid_statuses:
            raise ValueError(f"Overall status must be one of {valid_statuses}")
        return v
    
    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, v: str) -> str:
        """Validate recommendation."""
        valid_recommendations = {"approve", "reject", "revise"}
        if v not in valid_recommendations:
            raise ValueError(f"Recommendation must be one of {valid_recommendations}")
        return v


class QACheckResult(TimestampedModel):
    """Single QA check result."""
    
    check_type: str = Field(
        description="Type of check (completeness/accuracy/consistency/formatting)"
    )
    section: str = Field(description="Section/question/table checked")
    status: str = Field(description="Status (met/partially_met/not_met)")
    severity: str = Field(description="Severity if not met (CRITICAL/HIGH/MEDIUM/LOW)")
    description: str = Field(description="What was checked")
    findings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    references: List[Dict[str, str]] = Field(default_factory=list)
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status."""
        valid_statuses = {"met", "partially_met", "not_met"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v


class MissingArtifact(TimestampedModel):
    """Information about a missing required artifact."""
    
    expected_name: str = Field(min_length=1)
    expected_type: str = Field(description="Expected artifact type")
    description: str = Field(description="Why this artifact is expected")
    priority: str = Field(
        default="HIGH",
        description="Priority (CRITICAL/HIGH/MEDIUM/LOW)"
    )
    based_on: str = Field(
        description="What requirement this is based on"
    )


class QAOutput(TimestampedModel):
    """
    Structured output from QA Agent.
    
    LLM-generated quality assurance review of artifacts.
    """
    
    project_id: UUID
    
    # Reviewed artifacts
    artifacts_reviewed: List[Dict[str, Any]] = Field(
        description="List of artifacts with QA feedback"
    )
    
    # Missing artifacts
    missing_artifacts: List[MissingArtifact] = Field(
        default_factory=list,
        description="Required artifacts that are missing"
    )
    
    # QA checks
    qa_checks: List[QACheckResult] = Field(
        default_factory=list,
        description="All QA checks performed"
    )
    
    # Summary
    overall_status: str = Field(
        description="Overall QA status (complete/partial/failed)"
    )
    total_artifacts_expected: int = Field(ge=0)
    total_artifacts_submitted: int = Field(ge=0)
    total_issues_found: int = Field(ge=0)
    critical_issues: int = Field(ge=0)
    
    # Blocking issues
    blocking_issues: List[str] = Field(
        default_factory=list,
        description="Issues blocking approval"
    )
    
    # Recommendation
    recommendation: str = Field(
        description="QA recommendation (pass/fail/revise)"
    )
    next_steps: List[str] = Field(
        default_factory=list,
        description="Recommended next steps"
    )
    
    @field_validator("overall_status")
    @classmethod
    def validate_overall_status(cls, v: str) -> str:
        """Validate overall status."""
        valid_statuses = {"complete", "partial", "failed"}
        if v not in valid_statuses:
            raise ValueError(f"Overall status must be one of {valid_statuses}")
        return v
    
    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, v: str) -> str:
        """Validate recommendation."""
        valid_recommendations = {"pass", "fail", "revise"}
        if v not in valid_recommendations:
            raise ValueError(f"Recommendation must be one of {valid_recommendations}")
        return v


class EmailDraft(TimestampedModel):
    """LLM-generated email draft from Submission Agent."""
    
    title: str = Field(min_length=1, description="Email subject line")
    to: List[str] = Field(min_length=1, description="Recipient email addresses")
    from_email: str = Field(description="Sender email address")
    cc: List[str] = Field(default_factory=list)
    bcc: List[str] = Field(default_factory=list)
    
    # Email body (rich text in TipTap format or plain text)
    body: str = Field(min_length=10, description="Email body content")
    body_format: str = Field(
        default="plain",
        description="Format (plain/html/tiptap)"
    )
    
    # Attachments
    attachments: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Attachments with name and S3 URL"
    )
    
    # Metadata
    tone: str = Field(
        default="professional",
        description="Email tone (professional/formal/friendly)"
    )
    urgency: str = Field(
        default="normal",
        description="Urgency level (urgent/normal/low)"
    )
    
    # Follow-up
    requires_follow_up: bool = Field(default=False)
    follow_up_date: Optional[datetime] = None


class NotificationPlan(TimestampedModel):
    """Plan for notifications from Comms Agent."""
    
    # Recipients
    user_ids: List[UUID] = Field(min_length=1)
    email_addresses: List[str] = Field(default_factory=list)
    
    # Slack
    create_slack_channel: bool = Field(default=True)
    slack_channel_name: Optional[str] = None
    slack_message: Optional[str] = None
    
    # Email notification
    send_email: bool = Field(default=True)
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    
    # In-app notification
    notification_title: str = Field(min_length=1)
    notification_message: str = Field(min_length=1)
    notification_type: str = Field(
        default="info",
        description="Notification type (info/success/warning/error)"
    )
    
    # Attachments/links
    include_artifact_links: bool = Field(default=True)
    artifact_ids: List[UUID] = Field(default_factory=list)


class IntentClassification(TimestampedModel):
    """
    LLM output for intent classification (AI Assistant mode).
    
    Used by AI Assistant Supervisor to route user queries to appropriate agents.
    """
    
    primary_intent: str = Field(
        description="Primary intent (query/clarification/edit/approval/etc.)"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    
    # Secondary intents
    secondary_intents: List[str] = Field(
        default_factory=list,
        description="Other detected intents"
    )
    
    # Routing decision
    recommended_agent: str = Field(description="Agent to handle this intent")
    alternative_agents: List[str] = Field(
        default_factory=list,
        description="Alternative agents that could handle this"
    )
    
    # Context
    requires_context: List[str] = Field(
        default_factory=list,
        description="Context items needed (project_data/artifacts/history)"
    )
    
    # Extracted entities
    entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted entities from user input"
    )
    
    # Clarification
    needs_clarification: bool = Field(default=False)
    clarification_questions: List[str] = Field(default_factory=list)


# ============================================================================
# New Compliance & QA Models (Phase 5)
# ============================================================================

class ComplianceReference(TimestampedModel):
    """Reference document for compliance issue."""
    
    title: str = Field(min_length=1)
    link: str = Field(min_length=1, description="URL to reference document")


class ComplianceIssue(TimestampedModel):
    """Single compliance issue within a section."""
    
    description: str = Field(min_length=1, description="Description of the issue")
    references: List[ComplianceReference] = Field(
        default_factory=list,
        description="Reference documents justifying this issue"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Suggested fixes/improvements"
    )


class ComplianceFeedback(TimestampedModel):
    """Compliance feedback for a section of an artifact."""
    
    section: str = Field(min_length=1, description="Section name/heading")
    issues: List[ComplianceIssue] = Field(
        default_factory=list,
        description="Issues found in this section"
    )


class ComplianceCheckOutput(TimestampedModel):
    """
    Structured output from Compliance Agent for a single artifact.
    
    Matches the specification format from requirements document.
    """
    
    is_compliant: bool = Field(description="Whether artifact meets compliance standards")
    feedback: List[ComplianceFeedback] = Field(
        default_factory=list,
        description="Feedback per section with issues and suggestions"
    )


class QAStatus(str, Enum):
    """QA status enum for feedback items."""
    MET = "met"
    PARTIALLY_MET = "partially_met"
    NOT_MET = "not_met"


class QAReference(TimestampedModel):
    """Reference document for QA feedback."""
    
    title: str = Field(min_length=1)
    link: str = Field(min_length=1, description="URL to reference document")


class QAFeedbackItem(TimestampedModel):
    """Single QA feedback item for a section/question/table."""
    
    section_or_question_or_table: str = Field(
        min_length=1,
        description="Section heading, Q&A question, or table name"
    )
    description: str = Field(min_length=1, description="Issue or observation")
    status: QAStatus = Field(description="met/partially_met/not_met")
    references: List[QAReference] = Field(
        default_factory=list,
        description="Optional references to justify feedback"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Optional guidance to fix/complete"
    )


class QAArtifactReview(TimestampedModel):
    """QA review for a single artifact."""
    
    name: str = Field(min_length=1, description="Artifact name/title")
    type: str = Field(description="worddoc | pdf | excel | q_and_a | ppt")
    submitted_content: Dict[str, Any] = Field(
        description="Original content JSON (TipTap, tables, Q&A)"
    )
    feedback: List[QAFeedbackItem] = Field(
        default_factory=list,
        description="Feedback items for this artifact"
    )


class QAMissingArtifact(TimestampedModel):
    """Information about a missing artifact."""
    
    expected_name: str = Field(min_length=1)
    expected_type: str = Field(description="worddoc | pdf | excel | q_and_a | ppt")
    description: str = Field(description="Why this artifact is considered missing")


class QASummary(TimestampedModel):
    """Summary of QA check results."""
    
    total_artifacts_expected: int = Field(ge=0)
    total_artifacts_submitted: int = Field(ge=0)
    total_issues_found: int = Field(ge=0)
    overall_status: str = Field(
        description="partial | complete | failed"
    )
    
    @field_validator("overall_status")
    @classmethod
    def validate_overall_status(cls, v: str) -> str:
        """Validate overall status."""
        valid_statuses = {"partial", "complete", "failed"}
        if v not in valid_statuses:
            raise ValueError(f"Overall status must be one of {valid_statuses}")
        return v


class QACheckOutput(TimestampedModel):
    """
    Structured output from QA Agent.
    
    Matches the specification format from requirements document.
    """
    
    project_id: str = Field(description="Project ID/reference")
    artifacts_reviewed: List[QAArtifactReview] = Field(
        default_factory=list,
        description="List of reviewed artifacts with feedback"
    )
    missing_artifacts: List[QAMissingArtifact] = Field(
        default_factory=list,
        description="Expected artifacts that are missing"
    )
    summary: QASummary = Field(description="Summary of QA check")