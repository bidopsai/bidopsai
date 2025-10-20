"""
Graph state models for Workflow Supervisor.

These models define the state structure used in the StateGraph for orchestrating
agent workflows using the Strands Graph pattern.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

from models.base import TimestampedModel
from models.workflow_models import (
    AgentTask,
    AgentTaskInput,
    AgentTaskOutput,
    WorkflowExecution,
)


class SupervisorDecision(TimestampedModel):
    """Decision made by supervisor agent."""
    
    next_agent: Optional[str] = Field(
        None,
        description="Next agent to execute (None if workflow complete)"
    )
    action: str = Field(
        description="Action to take (execute_agent/await_feedback/complete/fail)"
    )
    reason: str = Field(description="Reasoning for the decision")
    requires_user_input: bool = Field(
        default=False,
        description="Whether user input is required"
    )
    user_prompt: Optional[str] = Field(
        None,
        description="Prompt to show user if input required"
    )
    retry_previous: bool = Field(
        default=False,
        description="Whether to retry previous agent"
    )
    reset_tasks: List[str] = Field(
        default_factory=list,
        description="Agent tasks to reset (for retry)"
    )


class UserFeedback(TimestampedModel):
    """User feedback captured during workflow."""
    
    feedback_type: str = Field(
        description="Type of feedback (approval/rejection/edit/clarification)"
    )
    content: str = Field(description="Feedback content")
    target_agent: Optional[str] = Field(
        None,
        description="Agent the feedback is for"
    )
    requires_reexecution: bool = Field(
        default=False,
        description="Whether feedback requires re-executing agents"
    )
    artifacts_edited: List[UUID] = Field(
        default_factory=list,
        description="Artifacts edited by user"
    )
    edit_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed edit data"
    )


class WorkflowGraphState(TimestampedModel):
    """
    State maintained throughout workflow graph execution.
    
    This is the primary state object passed between graph nodes in the
    Strands StateGraph implementation.
    """
    
    # Workflow context
    workflow_execution_id: Optional[UUID] = Field(
        None,
        description="Set in initialize node"
    )
    project_id: UUID
    session_id: str
    user_id: UUID
    
    # Execution state
    current_status: str = Field(
        default="OPEN",
        description="Current workflow status"
    )
    current_agent: Optional[str] = Field(
        None,
        description="Currently executing agent"
    )
    
    # Task tracking
    agent_tasks: List[AgentTask] = Field(
        default_factory=list,
        description="All agent tasks in sequence"
    )
    completed_tasks: List[str] = Field(
        default_factory=list,
        description="Names of completed agents"
    )
    failed_tasks: List[str] = Field(
        default_factory=list,
        description="Names of failed agents"
    )
    
    # Execution data
    task_outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Outputs from completed tasks (agent_name -> output)"
    )
    shared_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Shared context between agents"
    )
    
    # Supervisor routing (for conditional edges)
    supervisor_next_node: Optional[str] = Field(
        None,
        description="Next node decided by supervisor (used by conditional edges)"
    )
    
    # User interaction
    awaiting_user_feedback: bool = Field(default=False)
    user_feedback: Optional[str] = Field(
        None,
        description="Raw user feedback text"
    )
    feedback_intent: str = Field(
        default="proceed",
        description="Intent from user feedback: reparse/reanalyze/proceed"
    )
    content_edits: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="User edits to artifacts"
    )
    user_feedback_history: List[UserFeedback] = Field(
        default_factory=list,
        description="History of user feedback"
    )
    last_user_message: Optional[str] = None
    
    # Supervisor decisions
    supervisor_decisions: List[SupervisorDecision] = Field(
        default_factory=list,
        description="History of supervisor decisions"
    )
    
    # Artifacts
    created_artifacts: List[UUID] = Field(
        default_factory=list,
        description="All artifacts created during workflow"
    )
    artifact_export_locations: Dict[UUID, str] = Field(
        default_factory=dict,
        description="S3 locations of exported artifacts"
    )
    
    # Error tracking
    errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Errors encountered during execution"
    )
    retry_count: int = Field(default=0, ge=0)
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Configuration
    workflow_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow configuration"
    )
    
    def get_next_incomplete_task(self) -> Optional[AgentTask]:
        """Get the next incomplete agent task."""
        for task in sorted(self.agent_tasks, key=lambda t: t.sequence_order):
            if task.status in {"OPEN", "FAILED"}:
                return task
        return None
    
    def get_task_by_agent_name(self, agent_name: str) -> Optional[AgentTask]:
        """Get task by agent name."""
        for task in self.agent_tasks:
            if task.agent == agent_name:
                return task
        return None
    
    def get_last_completed_output(self) -> Optional[AgentTaskOutput]:
        """Get output from last completed task."""
        if not self.completed_tasks:
            return None
        last_agent = self.completed_tasks[-1]
        return self.task_outputs.get(last_agent)
    
    def mark_task_complete(
        self,
        agent_name: str,
        output: AgentTaskOutput
    ) -> None:
        """Mark a task as complete and store its output."""
        if agent_name not in self.completed_tasks:
            self.completed_tasks.append(agent_name)
        self.task_outputs[agent_name] = output
        self.last_updated_at = datetime.utcnow()
    
    def mark_task_failed(self, agent_name: str, error: Dict[str, Any]) -> None:
        """Mark a task as failed."""
        if agent_name not in self.failed_tasks:
            self.failed_tasks.append(agent_name)
        self.errors.append(error)
        self.last_updated_at = datetime.utcnow()
    
    def reset_task(self, agent_name: str) -> None:
        """Reset a task for retry."""
        # Remove from completed/failed lists
        if agent_name in self.completed_tasks:
            self.completed_tasks.remove(agent_name)
        if agent_name in self.failed_tasks:
            self.failed_tasks.remove(agent_name)
        
        # Remove output
        self.task_outputs.pop(agent_name, None)
        
        # Update task status in agent_tasks list
        task = self.get_task_by_agent_name(agent_name)
        if task:
            task.status = "OPEN"
            task.retry_count += 1
        
        self.retry_count += 1
        self.last_updated_at = datetime.utcnow()
    
    def calculate_progress(self) -> int:
        """Calculate workflow progress percentage."""
        if not self.agent_tasks:
            return 0
        completed = len(self.completed_tasks)
        total = len(self.agent_tasks)
        return int((completed / total) * 100)
    
    def is_complete(self) -> bool:
        """Check if workflow is complete."""
        return len(self.completed_tasks) == len(self.agent_tasks)
    
    def has_failures(self) -> bool:
        """Check if workflow has failures."""
        return len(self.failed_tasks) > 0


class GraphNodeInput(TimestampedModel):
    """Input to a graph node (supervisor or agent)."""
    
    state: WorkflowGraphState
    node_name: str = Field(description="Name of the node being executed")
    previous_node: Optional[str] = Field(
        None,
        description="Name of previous node in graph"
    )


class GraphNodeOutput(TimestampedModel):
    """Output from a graph node."""
    
    state: WorkflowGraphState
    node_name: str
    success: bool
    next_node: Optional[str] = Field(
        None,
        description="Name of next node to execute"
    )
    message: Optional[str] = Field(
        None,
        description="Status or error message"
    )
    sse_events: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="SSE events to emit"
    )


class AgentHandoff(TimestampedModel):
    """Information for handing off to an agent."""
    
    agent_name: str
    task_id: UUID
    mode: str = Field(description="Execution mode (workflow/ai_assistant)")
    input_data: AgentTaskInput
    config: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context from previous agents"
    )


class SupervisorAnalysis(TimestampedModel):
    """Supervisor's analysis of current state."""
    
    workflow_status: str
    completed_agents: List[str]
    pending_agents: List[str]
    failed_agents: List[str]
    
    # Current situation
    current_task: Optional[str]
    requires_user_input: bool
    blocking_issues: List[str] = Field(
        default_factory=list,
        description="Issues blocking progress"
    )
    
    # Recommendations
    recommended_action: str
    recommended_agent: Optional[str] = None
    retry_recommendations: List[str] = Field(
        default_factory=list,
        description="Agents that should be retried"
    )
    
    # User communication
    user_message: Optional[str] = Field(
        None,
        description="Message to send to user"
    )
    
    # Quality assessment
    quality_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Overall quality score of current outputs"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence in analysis"
    )