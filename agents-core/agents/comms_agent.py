"""
Comms Agent - Communications Specialist

Handles notifications via Slack and email for project stakeholders.
Implements proper OOP design inheriting from BaseAgent.

Responsibilities:
- Create Slack channels for project teams
- Send Slack notifications with artifact links
- Create database notification records
- Notify project members via multiple channels

Mode Support:
- Workflow: Send notifications after artifacts finalized
- AI Assistant: On-demand notification sending
"""

import logging
from typing import Optional, Dict, Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CommsAgent(BaseAgent):
    """
    Comms Agent - Communications Specialist.
    
    Handles project communications via Slack and database notifications.
    Creates channels, sends messages, and maintains notification records
    for project stakeholders.
    
    The agent autonomously:
    1. Retrieves project members from database
    2. Fetches member emails and contact details
    3. Creates Slack channel for project (if not exists)
    4. Sends Slack notifications with:
       - Project status update
       - Artifact links from S3
       - Next steps information
    5. Creates Notification records in database
    6. Updates AgentTask with communication results
    
    Example:
        ```python
        # Create comms agent (like Java)
        comms = CommsAgent(mode="workflow")
        
        # Get Strands Agent and invoke
        result = await comms.ainvoke({
            "project_id": "uuid",
            "user_id": "uuid"
        })
        ```
    """
    
    def __init__(
        self,
        mode: str = "workflow",
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Comms Agent.
        
        Args:
            mode: Agent mode (workflow/ai_assistant)
            provider: LLM provider (defaults to env DEFAULT_LLM_PROVIDER)
            model_id: Model ID (defaults to provider's default from env)
            **kwargs: Additional configuration
        """
        super().__init__(mode, provider, model_id, **kwargs)
        logger.info(f"CommsAgent initialized (mode={mode})")
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """
        Comms-specific configuration.
        
        Returns:
            Configuration dict with:
            - max_tool_iterations: Number of tool calls allowed (30 for comms)
            - require_tool_approval: Whether to require human approval (False)
        """
        return {
            "max_tool_iterations": 30,
            "require_tool_approval": False
        }


__all__ = ["CommsAgent"]