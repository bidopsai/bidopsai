"""
Submission Agent - Bid Submission Specialist

Handles final bid submission via email with attachments.
Implements proper OOP design inheriting from BaseAgent.

Responsibilities:
- Generate email drafts with artifact attachments
- Send emails to clients with bid documents
- Track submission records in database
- Handle email formatting and attachment management

Mode Support:
- Workflow: Final bid submission after user approval
- AI Assistant: On-demand email sending
"""

import logging
from typing import Optional, Dict, Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SubmissionAgent(BaseAgent):
    """
    Submission Agent - Bid Submission Specialist.
    
    Handles final bid submission to clients via email. Generates email
    drafts for review, attaches finalized artifacts from S3, and sends
    professionally formatted emails to client contacts.
    
    The agent autonomously:
    1. Retrieves Analysis output for client contact details
    2. Fetches artifact locations from database
    3. Generates email draft with:
       - Professional subject line
       - Body with bid summary
       - List of attached documents
    4. Presents draft to user for approval (via Supervisor)
    5. After approval, sends email with S3 attachments
    6. Creates SubmissionRecord in database
    7. Updates AgentTask with submission status
    
    Example:
        ```python
        # Create submission agent (like Java)
        submission = SubmissionAgent(mode="workflow")
        
        # Get Strands Agent and invoke
        result = await submission.ainvoke({
            "project_id": "uuid",
            "user_id": "uuid",
            "action": "generate_draft"  # or "send_email"
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
        Initialize Submission Agent.
        
        Args:
            mode: Agent mode (workflow/ai_assistant)
            provider: LLM provider (defaults to env DEFAULT_LLM_PROVIDER)
            model_id: Model ID (defaults to provider's default from env)
            **kwargs: Additional configuration
        """
        super().__init__(mode, provider, model_id, **kwargs)
        logger.info(f"SubmissionAgent initialized (mode={mode})")
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """
        Submission-specific configuration.
        
        Returns:
            Configuration dict with:
            - max_tool_iterations: Number of tool calls allowed (25 for submission)
            - require_tool_approval: Whether to require human approval (False)
        """
        return {
            "max_tool_iterations": 25,
            "require_tool_approval": False
        }


__all__ = ["SubmissionAgent"]