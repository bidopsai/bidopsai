"""
Workflow-related Pydantic models for BidOpsAI AgentCore.

These models represent workflow execution state, agent tasks, and related entities
that correspond to the database schema (workflow_executions, agent_tasks tables).
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from .base import IdentifiedModel, TimestampedModel


class WorkflowExecutionStatus(str, Enum):
    """Workflow execution status values."""
    
    OPEN = "OPEN"
    IN_PROGRESS = "INPROGRESS"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentTaskStatus(str, Enum):
    """Agent task status values."""
    
    OPEN = "OPEN"
    IN_PROGRESS = "INPROGRESS"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowConfig(TimestampedModel):
    """Configuration for workflow execution."""
    
    selected_agents: List[str] = Field(
        description="List of agent names to execute in sequence"
    )
    max_retry_attempts: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts per agent task"
    )
    timeout_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Timeout for entire workflow in seconds"
    )
    enable_human_in_loop: bool = Field(
        default=True,
        description="Enable human approval checkpoints"
    )
    auto_save_artifacts: bool = Field(
        default=True,
        description="Automatically save artifacts to S3"
    )
    notification_preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="User notification preferences"
    )


class AgentTaskConfig(TimestampedModel):
    """Configuration for individual agent task."""
    
    agent_name: str = Field(description="Name of the agent")
    mode: str = Field(description="Execution mode (workflow, ai_assistant)")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=256, le=200000)
    timeout_seconds: int = Field(default=600, ge=30, le=3600)
    retry_on_failure: bool = Field(default=True)
    require_approval: bool = Field(
        default=False,
        description="Require human approval before execution"
    )
    tools: List[str] = Field(
        default_factory=list,
        description="List of tool names available to agent"
    )


class AgentTaskInput(TimestampedModel):
    """Input data for agent task execution."""
    
    user_message: Optional[str] = Field(None, description="User input message")
    context_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context from previous tasks"
    )
    file_locations: List[str] = Field(
        default_factory=list,
        description="S3 paths to input files"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentTaskOutput(TimestampedModel):
    """Output data from agent task execution."""
    
    result: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task execution result"
    )
    artifacts_created: List[UUID] = Field(
        default_factory=list,
        description="IDs of artifacts created by this task"
    )
    file_locations: List[str] = Field(
        default_factory=list,
        description="S3 paths to output files"
    )
    next_action: Optional[str] = Field(
        None,
        description="Suggested next action (e.g., 'require_user_feedback')"
    )
    confidence_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Agent confidence in output quality"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ErrorLog(TimestampedModel):
    """Structured error log entry."""
    
    error_code: str = Field(description="Error code (e.g., 'DB_1001')")
    error_type: str = Field(description="Error type (e.g., 'ConnectionError')")
    severity: str = Field(description="Severity level (CRITICAL/HIGH/MEDIUM/LOW)")
    message: str = Field(description="Human-readable error message")
    stack_trace: Optional[str] = Field(None, description="Stack trace if available")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context about the error"
    )
    recovery_attempted: bool = Field(
        default=False,
        description="Whether automatic recovery was attempted"
    )
    recovery_strategy: Optional[str] = Field(
        None,
        description="Recovery strategy used"
    )


class AgentTask(IdentifiedModel):
    """Represents an agent task in workflow execution."""
    
    workflow_execution_id: UUID = Field(description="Parent workflow execution ID")
    agent: str = Field(description="Agent name")
    status: str = Field(
        default="OPEN",
        description="Task status (OPEN/INPROGRESS/WAITING/COMPLETED/FAILED)"
    )
    sequence_order: int = Field(ge=1, description="Order in workflow sequence")
    
    # User tracking
    initiated_by: UUID = Field(description="User who initiated the task")
    handled_by: Optional[UUID] = Field(None, description="User handling the task")
    completed_by: Optional[UUID] = Field(None, description="User who completed")
    
    # Task data
    input_data: Optional[AgentTaskInput] = None
    output_data: Optional[AgentTaskOutput] = None
    task_config: Optional[AgentTaskConfig] = None
    
    # Error handling
    error_log: Optional[List[ErrorLog]] = Field(
        None,
        description="List of errors encountered"
    )
    error_message: Optional[str] = Field(
        None,
        description="Latest error message"
    )
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_seconds: Optional[float] = Field(
        None,
        ge=0.0,
        description="Total execution time"
    )
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status field."""
        valid_statuses = {"OPEN", "INPROGRESS", "WAITING", "COMPLETED", "FAILED"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v


class WorkflowExecution(IdentifiedModel):
    """Represents a workflow execution instance."""
    
    project_id: UUID = Field(description="Associated project ID")
    status: str = Field(
        default="OPEN",
        description="Workflow status (OPEN/INPROGRESS/WAITING/COMPLETED/FAILED)"
    )
    
    # User tracking
    initiated_by: UUID = Field(description="User who initiated workflow")
    handled_by: Optional[UUID] = Field(None, description="User handling workflow")
    completed_by: Optional[UUID] = Field(None, description="User who completed")
    
    # Workflow data
    workflow_config: Optional[WorkflowConfig] = None
    results: Optional[Dict[str, Any]] = Field(
        None,
        description="Final workflow results"
    )
    
    # Error handling
    error_log: Optional[List[ErrorLog]] = None
    error_message: Optional[str] = None
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Session tracking
    session_id: str = Field(description="AgentCore session ID")
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status field."""
        valid_statuses = {"OPEN", "INPROGRESS", "WAITING", "COMPLETED", "FAILED"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v


class WorkflowProgress(TimestampedModel):
    """Progress information for workflow execution."""
    
    workflow_execution_id: UUID
    total_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    failed_tasks: int = Field(ge=0)
    current_task: Optional[str] = Field(None, description="Currently executing agent")
    progress_percentage: int = Field(ge=0, le=100)
    estimated_completion: Optional[datetime] = None
    
    @field_validator("completed_tasks", "failed_tasks")
    @classmethod
    def validate_task_counts(cls, v: int, info) -> int:
        """Ensure task counts don't exceed total."""
        if "total_tasks" in info.data and v > info.data["total_tasks"]:
            raise ValueError("Task count cannot exceed total_tasks")
        return v


class Project(IdentifiedModel):
    """Project model (subset of fields from database)."""
    
    name: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    status: str = Field(default="OPEN")
    value: Optional[Decimal] = None
    deadline: Optional[datetime] = None
    progress_percentage: int = Field(default=0, ge=0, le=100)
    
    # User tracking
    created_by: UUID
    completed_by: Optional[UUID] = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status field."""
        valid_statuses = {"OPEN", "INPROGRESS", "COMPLETED", "CANCELLED"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v


class ProjectDocument(IdentifiedModel):
    """Project document model."""
    
    project_id: UUID
    file_name: str = Field(min_length=1)
    file_path: str
    file_type: str
    file_size: int = Field(ge=0)
    
    # S3 locations
    raw_file_location: str = Field(description="Original file location in S3")
    processed_file_location: Optional[str] = Field(
        None,
        description="Processed file location after parsing"
    )
    
    # Processing status
    parsing_status: str = Field(
        default="PENDING",
        description="Parsing status (PENDING/PROCESSING/COMPLETED/FAILED)"
    )
    
    # User tracking
    uploaded_by: UUID
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("parsing_status")
    @classmethod
    def validate_parsing_status(cls, v: str) -> str:
        """Validate parsing status."""
        valid_statuses = {"PENDING", "PROCESSING", "COMPLETED", "FAILED"}
        if v not in valid_statuses:
            raise ValueError(f"Parsing status must be one of {valid_statuses}")
        return v