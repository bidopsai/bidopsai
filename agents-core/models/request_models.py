"""
API request and response models for BidOpsAI AgentCore.

These models define the structure of HTTP requests/responses for the FastAPI
/invocations endpoint and other AgentCore runtime APIs.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from .base import ErrorResponse, SuccessResponse, TimestampedModel


class UserInput(TimestampedModel):
    """User input data for agent invocation."""
    
    chat: Optional[str] = Field(
        None,
        description="Chat message from user"
    )
    content_edits: Optional[Dict[str, Any]] = Field(
        None,
        description="Artifact edits from user (artifact_id -> updated content)"
    )
    feedback: Optional[str] = Field(
        None,
        description="General feedback on agent outputs"
    )
    decision: Optional[str] = Field(
        None,
        description="User decision (yes/no/approve/decline)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional user input metadata"
    )


class InvocationRequest(TimestampedModel):
    """
    Request model for /invocations endpoint.
    
    This is the primary entry point for AgentCore runtime invocations.
    """
    
    # Required fields
    project_id: UUID = Field(description="Project ID for this workflow")
    user_id: UUID = Field(description="User initiating the request")
    session_id: str = Field(description="AgentCore session ID")
    
    # Workflow control
    start: bool = Field(
        default=False,
        description="True for new workflow, False for continuation"
    )
    
    # User input (optional)
    user_input: Optional[UserInput] = Field(
        None,
        description="User input for chat, edits, or feedback"
    )
    
    # Workflow configuration (optional, for new workflows)
    workflow_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Workflow configuration for new executions"
    )
    
    # Additional context
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional request metadata"
    )
    
    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Ensure session_id is not empty."""
        if not v or not v.strip():
            raise ValueError("session_id cannot be empty")
        return v.strip()


class InvocationResponse(SuccessResponse):
    """
    Response model for /invocations endpoint.
    
    Returns status and SSE connection details for streaming updates.
    """
    
    workflow_execution_id: UUID = Field(
        description="Workflow execution ID for tracking"
    )
    session_id: str = Field(description="AgentCore session ID")
    status: str = Field(
        description="Current workflow status"
    )
    message: str = Field(
        description="Human-readable status message"
    )
    sse_endpoint: Optional[str] = Field(
        None,
        description="SSE endpoint URL for streaming updates"
    )
    next_action: Optional[str] = Field(
        None,
        description="Suggested next action for client"
    )


class AgentInvocationRequest(TimestampedModel):
    """Internal request for agent task execution."""
    
    task_id: UUID = Field(description="Agent task ID")
    agent_name: str = Field(description="Name of agent to invoke")
    mode: str = Field(description="Execution mode (workflow/ai_assistant)")
    
    # Input data
    input_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input data for agent"
    )
    
    # Configuration
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent configuration"
    )
    
    # Context
    session_id: str = Field(description="Session ID for memory")
    user_id: UUID = Field(description="User ID for tracking")
    
    
class AgentInvocationResponse(SuccessResponse):
    """Internal response from agent task execution."""
    
    task_id: UUID
    agent_name: str
    status: str = Field(description="Task status after execution")
    output_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent output data"
    )
    next_action: Optional[str] = Field(
        None,
        description="Suggested next action"
    )
    execution_time_seconds: float = Field(
        ge=0.0,
        description="Execution time"
    )


class HealthCheckResponse(SuccessResponse):
    """Health check response."""
    
    status: str = Field(default="healthy")
    version: str = Field(description="Application version")
    uptime_seconds: float = Field(ge=0.0)
    database_connected: bool
    memory_manager_ready: bool
    sse_manager_ready: bool
    
    # Optional details
    active_workflows: Optional[int] = Field(None, ge=0)
    active_sessions: Optional[int] = Field(None, ge=0)


class ConversationMessageRequest(TimestampedModel):
    """Request to save conversation message."""
    
    project_id: UUID
    session_id: str
    user_id: UUID
    role: str = Field(description="Message role (user/assistant/system)")
    content: str = Field(description="Message content")
    
    # Optional metadata
    agent_name: Optional[str] = Field(None, description="Agent that sent message")
    event_type: Optional[str] = Field(None, description="Associated SSE event type")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role field."""
        valid_roles = {"user", "assistant", "system"}
        if v not in valid_roles:
            raise ValueError(f"Role must be one of {valid_roles}")
        return v


class ConversationHistoryRequest(TimestampedModel):
    """Request to retrieve conversation history."""
    
    project_id: UUID
    session_id: Optional[str] = Field(None, description="Filter by session")
    user_id: Optional[UUID] = Field(None, description="Filter by user")
    
    # Pagination
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    
    # Filtering
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    role_filter: Optional[List[str]] = Field(
        None,
        description="Filter by message roles"
    )


class ConversationMessage(TimestampedModel):
    """Single conversation message."""
    
    id: UUID
    project_id: UUID
    session_id: str
    user_id: UUID
    role: str
    content: str
    agent_name: Optional[str] = None
    event_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationHistoryResponse(SuccessResponse):
    """Response containing conversation history."""
    
    messages: List[ConversationMessage]
    total_count: int = Field(ge=0)
    has_more: bool
    
    # Context
    project_id: UUID
    session_id: Optional[str] = None


class ArtifactExportRequest(TimestampedModel):
    """Request to export artifacts to S3."""
    
    artifact_ids: List[UUID] = Field(min_length=1, description="Artifact IDs to export")
    user_id: UUID = Field(description="User requesting export")
    export_format: str = Field(
        default="native",
        description="Export format (native/pdf/docx)"
    )
    include_metadata: bool = Field(
        default=True,
        description="Include metadata in export"
    )


class ArtifactExportResponse(SuccessResponse):
    """Response from artifact export."""
    
    exported_artifacts: List[Dict[str, Any]] = Field(
        description="List of exported artifacts with S3 locations"
    )
    export_timestamp: datetime
    total_size_bytes: int = Field(ge=0)


class BatchOperationRequest(TimestampedModel):
    """Request for batch operations on multiple entities."""
    
    operation: str = Field(description="Operation type (update/delete/export)")
    entity_type: str = Field(description="Entity type (task/artifact/document)")
    entity_ids: List[UUID] = Field(min_length=1, max_length=100)
    
    # Operation-specific data
    operation_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Data for the operation"
    )
    
    # User context
    user_id: UUID


class BatchOperationResponse(SuccessResponse):
    """Response from batch operation."""
    
    operation: str
    entity_type: str
    total_requested: int = Field(ge=0)
    successful: int = Field(ge=0)
    failed: int = Field(ge=0)
    
    # Detailed results
    results: List[Dict[str, Any]] = Field(
        description="Per-entity results"
    )
    errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Errors encountered"
    )


class WorkflowCancellationRequest(TimestampedModel):
    """Request to cancel workflow execution."""
    
    workflow_execution_id: UUID
    user_id: UUID
    reason: Optional[str] = Field(None, description="Cancellation reason")
    force: bool = Field(
        default=False,
        description="Force cancellation even if in critical state"
    )


class WorkflowCancellationResponse(SuccessResponse):
    """Response from workflow cancellation."""
    
    workflow_execution_id: UUID
    status: str = Field(description="Status after cancellation")
    cancelled_at: datetime
    tasks_cancelled: int = Field(ge=0)
    cleanup_performed: bool


class MetricsRequest(TimestampedModel):
    """Request for workflow/agent metrics."""
    
    # Time range
    start_date: datetime
    end_date: datetime
    
    # Filters
    project_ids: Optional[List[UUID]] = None
    agent_names: Optional[List[str]] = None
    user_ids: Optional[List[UUID]] = None
    
    # Aggregation
    group_by: str = Field(
        default="day",
        description="Grouping interval (hour/day/week/month)"
    )
    
    @field_validator("group_by")
    @classmethod
    def validate_group_by(cls, v: str) -> str:
        """Validate group_by field."""
        valid_values = {"hour", "day", "week", "month"}
        if v not in valid_values:
            raise ValueError(f"group_by must be one of {valid_values}")
        return v


class MetricsResponse(SuccessResponse):
    """Response containing metrics data."""
    
    metrics: Dict[str, Any] = Field(
        description="Metrics data grouped by requested interval"
    )
    aggregation: str
    time_range: Dict[str, datetime]
    total_workflows: int = Field(ge=0)
    total_tasks: int = Field(ge=0)
    average_execution_time: float = Field(ge=0.0)
    success_rate: float = Field(ge=0.0, le=1.0)