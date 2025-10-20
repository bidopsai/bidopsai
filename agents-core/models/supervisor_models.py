"""
Supervisor agent structured output models.

These Pydantic models define the structured outputs returned by the supervisor agent
when making routing decisions, analyzing feedback, and managing workflow state.
All decisions are database-driven using tools to query workflow state.
"""

from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from .base import TimestampedModel


class SupervisorDecisionType(str, Enum):
    """Types of decisions the supervisor agent can make."""

    ROUTE_TO_AGENT = "ROUTE_TO_AGENT"  # Route to specific sub-agent
    AWAIT_USER_FEEDBACK = "AWAIT_USER_FEEDBACK"  # Wait for user input
    RESET_TASKS = "RESET_TASKS"  # Reset tasks for retry loop
    REQUEST_PERMISSION = "REQUEST_PERMISSION"  # Request user permission
    COMPLETE_WORKFLOW = "COMPLETE_WORKFLOW"  # Mark workflow complete
    HANDLE_ERROR = "HANDLE_ERROR"  # Error recovery


class FeedbackType(str, Enum):
    """Types of user feedback."""

    PARSING_ISSUE = "PARSING_ISSUE"
    ANALYSIS_ISSUE = "ANALYSIS_ISSUE"
    CONTENT_CHANGE = "CONTENT_CHANGE"
    APPROVAL = "APPROVAL"
    REJECTION = "REJECTION"
    CLARIFICATION = "CLARIFICATION"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"


class ValidationStatus(str, Enum):
    """Status of validation checks (Compliance/QA)."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    PENDING = "PENDING"


class PermissionType(str, Enum):
    """Types of permissions the supervisor can request."""

    SEND_COMMUNICATIONS = "SEND_COMMUNICATIONS"
    SUBMIT_BID = "SUBMIT_BID"
    EXPORT_ARTIFACTS = "EXPORT_ARTIFACTS"
    RE_REVIEW = "RE_REVIEW"


class ErrorSeverity(str, Enum):
    """Severity levels for errors."""

    LOW = "LOW"  # Minor issue, can continue
    MEDIUM = "MEDIUM"  # Significant issue, may need retry
    HIGH = "HIGH"  # Critical issue, workflow blocked
    CRITICAL = "CRITICAL"  # Fatal error, workflow must abort


class AgentRoutingDecision(TimestampedModel):
    """
    Structured output for supervisor agent routing decisions.
    
    The supervisor queries database state and uses this model to return
    deterministic routing decisions based on workflow execution state.
    """

    decision_type: SupervisorDecisionType = Field(
        ..., description="Type of decision being made"
    )

    # Routing information
    next_agent: Optional[str] = Field(
        None,
        description="Name of next agent to execute (from get_next_incomplete_task())",
    )

    reasoning: str = Field(
        ...,
        description="WHY this decision was made, referencing database query results",
    )

    # Database context (from queries)
    current_workflow_status: str = Field(
        ..., description="Current workflow execution status from DB"
    )

    next_incomplete_task: Optional[str] = Field(
        None, description="Next incomplete agent task name from DB"
    )

    last_completed_agent: Optional[str] = Field(
        None, description="Last agent that completed successfully"
    )

    # Actions to execute
    update_workflow_status: Optional[str] = Field(
        None, description="New workflow status to set in DB (if changing)"
    )

    tasks_to_reset: List[str] = Field(
        default_factory=list,
        description="List of agent task names to reset to 'Open' status",
    )

    # User interaction
    user_prompt: Optional[str] = Field(
        None,
        description="Message to display to user (for feedback/permission requests)",
    )

    permission_type: Optional[PermissionType] = Field(
        None, description="Type of permission being requested (if applicable)"
    )

    # SSE events
    sse_events_to_emit: List[str] = Field(
        default_factory=list,
        description="List of SSE event types to emit to frontend",
    )

    # Error handling
    is_error_state: bool = Field(
        default=False, description="Whether this is an error recovery decision"
    )

    error_severity: Optional[ErrorSeverity] = Field(
        None, description="Severity of error (if is_error_state=True)"
    )

    recovery_action: Optional[str] = Field(
        None, description="Action to take for error recovery"
    )

    # Confidence
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in decision (0.0-1.0), based on DB state clarity",
    )

    @field_validator("next_agent")
    @classmethod
    def validate_next_agent(cls, v: Optional[str], info) -> Optional[str]:
        """Validate that next_agent is provided when routing to agent."""
        decision_type = info.data.get("decision_type")
        if decision_type == SupervisorDecisionType.ROUTE_TO_AGENT and not v:
            raise ValueError("next_agent required when decision_type is ROUTE_TO_AGENT")
        return v

    @field_validator("user_prompt")
    @classmethod
    def validate_user_prompt(cls, v: Optional[str], info) -> Optional[str]:
        """Validate that user_prompt is provided when awaiting feedback or requesting permission."""
        decision_type = info.data.get("decision_type")
        if decision_type in [
            SupervisorDecisionType.AWAIT_USER_FEEDBACK,
            SupervisorDecisionType.REQUEST_PERMISSION,
        ] and not v:
            raise ValueError(
                "user_prompt required when awaiting feedback or requesting permission"
            )
        return v


class FeedbackAnalysis(TimestampedModel):
    """
    Structured output for analyzing user feedback.
    
    Used by supervisor to understand user intent and determine required actions.
    """

    feedback_type: FeedbackType = Field(..., description="Type of feedback received")

    intent_summary: str = Field(
        ..., description="Summary of what user is asking for"
    )

    requires_task_reset: bool = Field(
        default=False, description="Whether tasks need to be reset based on feedback"
    )

    tasks_to_reset: List[str] = Field(
        default_factory=list, description="Specific tasks to reset (if applicable)"
    )

    restart_from_agent: Optional[str] = Field(
        None, description="Which agent to restart workflow from"
    )

    specific_changes_requested: List[str] = Field(
        default_factory=list, description="Specific changes user requested"
    )

    is_approval: bool = Field(
        default=False, description="Whether feedback is approval to proceed"
    )

    is_rejection: bool = Field(
        default=False, description="Whether feedback is rejection/concern"
    )

    next_action: str = Field(
        ...,
        description="What supervisor should do next based on this feedback",
    )

    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in feedback interpretation",
    )


class ValidationAnalysis(TimestampedModel):
    """
    Structured output for analyzing Compliance/QA validation results.
    
    Used by supervisor to determine whether to proceed or reset based on validation.
    """

    validation_type: str = Field(..., description="Type of validation (Compliance/QA)")

    overall_status: ValidationStatus = Field(
        ..., description="Overall validation status"
    )

    passed: bool = Field(
        ..., description="Whether validation passed (proceed to next step)"
    )

    issues_found: List[str] = Field(
        default_factory=list, description="List of issues found during validation"
    )

    blocking_issues: List[str] = Field(
        default_factory=list,
        description="Issues that block workflow progression",
    )

    tasks_to_reset: List[str] = Field(
        default_factory=list,
        description="Tasks to reset if validation failed",
    )

    restart_from_agent: Optional[str] = Field(
        None, description="Which agent to restart from if validation failed"
    )

    recommendation: str = Field(
        ...,
        description="Recommendation for supervisor (proceed/reset/request_review)",
    )

    requires_user_review: bool = Field(
        default=False,
        description="Whether supervisor should ask user before proceeding",
    )

    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in validation analysis",
    )


class WorkflowProgressAssessment(TimestampedModel):
    """
    Structured output for assessing overall workflow progress.
    
    Used by supervisor to track progress and determine completion.
    """

    total_tasks: int = Field(..., description="Total number of agent tasks")

    completed_tasks: int = Field(..., description="Number of completed tasks")

    in_progress_tasks: int = Field(..., description="Number of tasks in progress")

    failed_tasks: int = Field(..., description="Number of failed tasks")

    progress_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Progress percentage (0-100)"
    )

    current_phase: str = Field(..., description="Current workflow phase name")

    next_milestone: Optional[str] = Field(
        None, description="Next major milestone to achieve"
    )

    estimated_remaining_tasks: int = Field(
        ..., description="Estimated tasks remaining"
    )

    is_workflow_complete: bool = Field(
        default=False, description="Whether all tasks are complete"
    )

    is_workflow_blocked: bool = Field(
        default=False, description="Whether workflow is blocked"
    )

    blocking_reason: Optional[str] = Field(
        None, description="Reason workflow is blocked (if applicable)"
    )


class PermissionRequest(TimestampedModel):
    """
    Structured output for requesting user permissions.
    
    Used by supervisor when user approval is needed before proceeding.
    """

    permission_type: PermissionType = Field(..., description="Type of permission needed")

    request_message: str = Field(
        ..., description="Message to display to user explaining permission request"
    )

    context: str = Field(
        ..., description="Context explaining why this permission is needed"
    )

    default_action: str = Field(
        ..., description="What happens if user declines permission"
    )

    approval_action: str = Field(
        ..., description="What happens if user approves permission"
    )

    requires_explicit_approval: bool = Field(
        default=True, description="Whether explicit user approval is required"
    )

    timeout_seconds: Optional[int] = Field(
        None, description="Timeout for permission request (seconds)"
    )