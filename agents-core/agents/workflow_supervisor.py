"""
Workflow Supervisor Agent - Sequential Bid Workflow Orchestration

Orchestrates the sequential bid workflow through StateGraph pattern.
Implements proper OOP design inheriting from BaseAgent.

Responsibilities:
- Initialize workflow execution and agent tasks
- Orchestrate sequential agent execution (Parser → Analysis → Content → etc.)
- Handle user feedback and decision routing
- Manage workflow state transitions
- Update database records and emit SSE events

Mode: Fixed to "workflow" for specialized sequential behavior
"""

import logging
from typing import Optional, Dict, Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class WorkflowSupervisor(BaseAgent):
    """
    Workflow Supervisor - Sequential Bid Workflow Orchestration.
    
    Orchestrates the complete bid workflow using Strands StateGraph pattern.
    Controls sequential execution of specialized sub-agents through defined
    workflow stages with conditional routing based on user feedback.
    
    Workflow Stages:
    1. Parser → Analysis → [User Feedback]
    2. Content → Compliance → QA → [User Review]
    3. Export → Comms → Submission → Complete
    
    The supervisor autonomously:
    1. Creates WorkflowExecution and AgentTask records
    2. Routes to appropriate sub-agents based on workflow state
    3. Handles conditional branching (retry vs proceed)
    4. Awaits user feedback at decision points
    5. Updates progress and emits SSE events
    6. Manages error recovery and task resets
    
    Mode Behavior:
    - Mode is hardcoded to "workflow" for sequential orchestration
    - Uses StateGraph for workflow management
    - Implements checkpoint-based resumption
    
    Example:
        ```python
        # Create workflow supervisor (Java-style)
        supervisor = WorkflowSupervisor()
        
        # Get Strands Agent and invoke via StateGraph
        graph = supervisor.get_agent()
        result = await graph.ainvoke({
            "project_id": "uuid",
            "user_id": "uuid",
            "session_id": "session-123"
        })
        ```
    """
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Workflow Supervisor.
        
        Mode is hardcoded to "workflow" for specialized sequential behavior.
        The supervisor uses StateGraph pattern for workflow orchestration.
        
        Args:
            provider: LLM provider (defaults to env DEFAULT_LLM_PROVIDER)
            model_id: Model ID (defaults to provider's default from env)
            **kwargs: Additional configuration
        """
        # Mode hardcoded for workflow behavior
        super().__init__(mode="workflow", provider=provider, model_id=model_id, **kwargs)
        logger.info("WorkflowSupervisor initialized (mode=workflow)")
    
    @property
    def agent_name(self) -> str:
        """
        Override agent name for tool/prompt resolution.
        
        Returns "supervisor" instead of "workflowsupervisor" to match
        tool configuration naming convention.
        
        Returns:
            "supervisor" for tool and prompt resolution
        """
        return "supervisor"
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """
        Workflow supervisor specific configuration.
        
        Returns:
            Configuration dict with:
            - max_tool_iterations: High limit for complex orchestration (100)
            - require_tool_approval: Whether to require human approval (False)
        """
        return {
            "max_tool_iterations": 100,
            "require_tool_approval": False
        }


__all__ = ["WorkflowSupervisor"]