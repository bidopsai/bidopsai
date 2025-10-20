"""
Workflow Supervisor Configuration

Configuration specific to workflow supervisor including:
- Agent execution sequence
- Conditional routing rules
- Human-in-the-loop points
- Retry policies
- Progress tracking
"""

from typing import Dict, List
from pydantic import BaseModel, Field


class AgentSequenceConfig(BaseModel):
    """Configuration for agent execution sequence"""
    
    agent_name: str
    sequence_order: int
    description: str
    can_retry: bool = True
    max_retries: int = 3
    requires_previous_output: bool = True
    can_skip: bool = False


class WorkflowConfig(BaseModel):
    """Configuration for workflow supervisor"""
    
    # Agent sequence
    agent_sequence: List[AgentSequenceConfig] = Field(
        default_factory=lambda: [
            AgentSequenceConfig(
                agent_name="parser",
                sequence_order=1,
                description="Parse uploaded documents",
                requires_previous_output=False
            ),
            AgentSequenceConfig(
                agent_name="analysis",
                sequence_order=2,
                description="Analyze RFP requirements"
            ),
            AgentSequenceConfig(
                agent_name="content",
                sequence_order=3,
                description="Generate bid artifacts"
            ),
            AgentSequenceConfig(
                agent_name="compliance",
                sequence_order=4,
                description="Check compliance standards"
            ),
            AgentSequenceConfig(
                agent_name="qa",
                sequence_order=5,
                description="Quality assurance review"
            ),
            AgentSequenceConfig(
                agent_name="comms",
                sequence_order=6,
                description="Send notifications"
            ),
            AgentSequenceConfig(
                agent_name="submission",
                sequence_order=7,
                description="Submit bid documents"
            ),
        ]
    )
    
    # Human-in-the-loop configuration
    await_feedback_after: List[str] = Field(
        default_factory=lambda: ["analysis", "content", "qa"],
        description="Agents after which to await user feedback"
    )
    
    # Retry configuration
    max_workflow_retries: int = 3
    retry_delay_seconds: int = 5
    
    # Timeout configuration
    agent_timeout_seconds: int = 300  # 5 minutes per agent
    workflow_timeout_seconds: int = 3600  # 1 hour total
    
    # Progress tracking
    enable_progress_events: bool = True
    progress_event_interval_seconds: int = 10
    
    # Error handling
    continue_on_non_critical_errors: bool = True
    critical_agents: List[str] = Field(
        default_factory=lambda: ["parser", "analysis"],
        description="Agents whose failure causes workflow failure"
    )


# Default configuration instance
DEFAULT_WORKFLOW_CONFIG = WorkflowConfig()


def get_workflow_config() -> WorkflowConfig:
    """Get workflow configuration (can be overridden from SSM/env)"""
    # TODO: Load from SSM Parameter Store in production
    return DEFAULT_WORKFLOW_CONFIG


def get_agent_config(agent_name: str) -> AgentSequenceConfig:
    """Get configuration for specific agent"""
    config = get_workflow_config()
    for agent_config in config.agent_sequence:
        if agent_config.agent_name == agent_name:
            return agent_config
    raise ValueError(f"No configuration found for agent: {agent_name}")


def should_await_feedback(agent_name: str) -> bool:
    """Check if workflow should await user feedback after this agent"""
    config = get_workflow_config()
    return agent_name in config.await_feedback_after


def is_critical_agent(agent_name: str) -> bool:
    """Check if agent is critical (failure causes workflow failure)"""
    config = get_workflow_config()
    return agent_name in config.critical_agents