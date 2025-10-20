"""
SSE (Server-Sent Events) event models for real-time streaming to frontend.

These models define the structure of events sent through SSE connections
to provide real-time workflow progress updates to the web application.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

from .base import TimestampedModel


class SSEEventData(TimestampedModel):
    """Base data structure for SSE events."""
    
    workflow_execution_id: UUID
    session_id: str
    project_id: UUID
    user_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WorkflowCreatedEventData(SSEEventData):
    """Data for workflow_created event."""
    
    total_tasks: int = Field(ge=0)
    agent_sequence: List[str] = Field(description="Ordered list of agent names")
    estimated_duration_minutes: Optional[int] = Field(None, ge=0)


class AgentStartedEventData(SSEEventData):
    """Data for agent_started events (parser_started, analysis_started, etc.)."""
    
    agent_name: str
    task_id: UUID
    sequence_order: int = Field(ge=1)
    total_tasks: int = Field(ge=1)
    progress_percentage: int = Field(ge=0, le=100)
    message: str = Field(description="User-friendly status message")


class AgentCompletedEventData(SSEEventData):
    """Data for agent_completed events."""
    
    agent_name: str
    task_id: UUID
    execution_time_seconds: float = Field(ge=0.0)
    progress_percentage: int = Field(ge=0, le=100)
    message: str
    
    # Optional summary of agent output
    output_summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Summary of agent output (not full data)"
    )


class AgentFailedEventData(SSEEventData):
    """Data for agent_failed events."""
    
    agent_name: str
    task_id: UUID
    error_code: str
    error_message: str
    severity: str = Field(description="Error severity (CRITICAL/HIGH/MEDIUM/LOW)")
    is_recoverable: bool
    retry_available: bool
    suggested_action: Optional[str] = None


class AwaitingFeedbackEventData(SSEEventData):
    """Data for awaiting_feedback event."""
    
    agent_name: str
    feedback_type: str = Field(
        description="Type of feedback needed (approval/clarification/edit)"
    )
    prompt: str = Field(description="Prompt to show user")
    
    # Data to display for review
    review_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Data for user to review (e.g., analysis results)"
    )
    
    # Suggested responses
    suggested_responses: List[str] = Field(
        default_factory=list,
        description="Suggested user responses"
    )
    
    timeout_seconds: Optional[int] = Field(
        None,
        ge=0,
        description="Timeout for user response"
    )


class ArtifactsReadyEventData(SSEEventData):
    """Data for artifacts_ready event."""
    
    total_artifacts: int = Field(ge=0)
    artifact_ids: List[UUID]
    
    # Brief artifact info for rendering tiles
    artifacts: List[Dict[str, Any]] = Field(
        description="Artifact metadata (id, name, type, category)"
    )
    
    message: str = Field(description="Instructions for user")
    allow_editing: bool = Field(default=True)


class ArtifactsExportedEventData(SSEEventData):
    """Data for artifacts_exported event."""
    
    artifact_ids: List[UUID]
    total_size_bytes: int = Field(ge=0)
    export_locations: Dict[str, str] = Field(
        description="Artifact ID -> S3 location mapping"
    )
    export_timestamp: datetime


class PermissionRequestEventData(SSEEventData):
    """Data for permission request events (comms_permission, submission_permission)."""
    
    permission_type: str = Field(
        description="Type of permission (communications/submission)"
    )
    prompt: str = Field(description="Permission prompt for user")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context about what will happen if approved"
    )
    
    # Preview of action
    action_preview: Optional[Dict[str, Any]] = Field(
        None,
        description="Preview of the action (e.g., email draft, notification list)"
    )


class EmailDraftEventData(SSEEventData):
    """Data for email_draft event."""
    
    draft: Dict[str, Any] = Field(
        description="Email draft with title, to, from, body, attachments"
    )
    requires_approval: bool = Field(default=True)
    can_edit: bool = Field(default=True)


class WorkflowCompletedEventData(SSEEventData):
    """Data for workflow_completed event."""
    
    completion_status: str = Field(
        description="Completion status (completed/completed_with_warnings/failed)"
    )
    total_execution_time_seconds: float = Field(ge=0.0)
    completed_tasks: int = Field(ge=0)
    failed_tasks: int = Field(ge=0)
    
    # Summary
    summary: str = Field(description="Workflow completion summary")
    artifacts_created: int = Field(ge=0)
    notifications_sent: int = Field(ge=0)
    submission_status: Optional[str] = Field(
        None,
        description="Submission status if applicable"
    )


class ProgressUpdateEventData(SSEEventData):
    """Data for progress_update event (generic progress indicator)."""
    
    current_step: str
    progress_percentage: int = Field(ge=0, le=100)
    message: str
    estimated_time_remaining_seconds: Optional[int] = Field(None, ge=0)


class ErrorEventData(SSEEventData):
    """Data for error event."""
    
    error_code: str
    error_message: str
    severity: str
    affected_component: str = Field(
        description="Component where error occurred"
    )
    is_recoverable: bool
    recovery_action: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class SSEEvent(TimestampedModel):
    """
    Complete SSE event structure.
    
    This is the actual event sent through the SSE connection.
    """
    
    # Event metadata
    event_id: str = Field(description="Unique event ID for replay/deduplication")
    event_type: str = Field(
        description="Event type (workflow_created, parser_started, etc.)"
    )
    
    # Event data (varies by type)
    data: Dict[str, Any] = Field(
        description="Event-specific data (use specific EventData models)"
    )
    
    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Optional retry info
    retry: int = Field(default=0, ge=0, description="Retry attempt number")
    
    def to_sse_format(self) -> str:
        """
        Convert to SSE format string.
        
        Returns:
            SSE-formatted string ready to send to client
        """
        import json
        
        lines = []
        lines.append(f"id: {self.event_id}")
        lines.append(f"event: {self.event_type}")
        
        # Serialize data to JSON
        data_json = json.dumps(self.data, default=str)
        lines.append(f"data: {data_json}")
        
        if self.retry > 0:
            lines.append(f"retry: {self.retry}")
        
        # SSE format requires empty line at end
        lines.append("")
        lines.append("")
        
        return "\n".join(lines)


class SSEEventLog(TimestampedModel):
    """
    Persistent log entry for SSE events.
    
    SSE events are stored in conversation_messages table with:
    - role='system'
    - message_type='system_event'
    - event_type field for the specific event
    """
    
    id: UUID
    session_id: str
    workflow_execution_id: UUID
    event_id: str
    event_type: str
    event_data: Dict[str, Any]
    client_id: Optional[str] = Field(None, description="Client connection ID")
    delivered: bool = Field(default=False)
    delivery_attempts: int = Field(default=0, ge=0)
    created_at: datetime
    delivered_at: Optional[datetime] = None


# Event type constants for type safety
class SSEEventType:
    """Constants for SSE event types."""
    
    # Workflow lifecycle
    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    
    # Agent lifecycle
    PARSER_STARTED = "parser_started"
    PARSER_COMPLETED = "parser_completed"
    PARSER_FAILED = "parser_failed"
    
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"
    
    CONTENT_STARTED = "content_started"
    CONTENT_COMPLETED = "content_completed"
    CONTENT_FAILED = "content_failed"
    
    COMPLIANCE_STARTED = "compliance_started"
    COMPLIANCE_COMPLETED = "compliance_completed"
    COMPLIANCE_FAILED = "compliance_failed"
    
    QA_STARTED = "qa_started"
    QA_COMPLETED = "qa_completed"
    QA_FAILED = "qa_failed"
    
    COMMS_STARTED = "comms_started"
    COMMS_COMPLETED = "comms_completed"
    COMMS_FAILED = "comms_failed"
    
    SUBMISSION_STARTED = "submission_started"
    SUBMISSION_COMPLETED = "submission_completed"
    SUBMISSION_FAILED = "submission_failed"
    
    # User interaction
    AWAITING_FEEDBACK = "awaiting_feedback"
    AWAITING_REVIEW = "awaiting_review"
    COMMS_PERMISSION = "comms_permission"
    SUBMISSION_PERMISSION = "submission_permission"
    EMAIL_DRAFT = "email_draft"
    
    # Artifacts
    ARTIFACTS_READY = "artifacts_ready"
    ARTIFACTS_EXPORTED = "artifacts_exported"
    
    # Progress
    PROGRESS_UPDATE = "progress_update"
    
    # Control flow
    RETURNING_TO_CONTENT = "returning_to_content"
    ANALYSIS_RESTARTED = "analysis_restarted"
    
    # Errors
    ERROR = "error"
    
    # Health
    HEARTBEAT = "heartbeat"


# Simple event classes for backward compatibility with graph_nodes.py
class WorkflowCreated(TimestampedModel):
    """Simple WorkflowCreated event for graph nodes."""
    workflow_execution_id: str
    project_id: str
    total_tasks: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentHandoff(TimestampedModel):
    """Simple AgentHandoff event for graph nodes."""
    from_agent: str
    to_agent: str
    agent_task_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AwaitingFeedback(TimestampedModel):
    """Simple AwaitingFeedback event for graph nodes."""
    workflow_execution_id: str
    prompt: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WorkflowStatusUpdate(TimestampedModel):
    """Simple WorkflowStatusUpdate event for graph nodes."""
    workflow_execution_id: str
    status: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WorkflowCompleted(TimestampedModel):
    """Simple WorkflowCompleted event for graph nodes."""
    workflow_execution_id: str
    status: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)