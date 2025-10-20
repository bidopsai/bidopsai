"""
Analysis Agent - Document Analysis Specialist

Analyzes RFP/Bid documents to extract structured information.
Implements proper OOP design inheriting from BaseAgent.

Responsibilities:
- Retrieve processed documents from S3
- Analyze content using structured LLM outputs (Pydantic models)
- Extract client, stakeholder, opportunity, and requirement details
- Generate analysis markdown for user review

Mode Support:
- Workflow: Sequential analysis after document parsing
- AI Assistant: On-demand document analysis queries
"""

import logging
from typing import Optional, Dict, Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AnalysisAgent(BaseAgent):
    """
    Analysis Agent - Document Analysis Specialist.
    
    Analyzes RFP/Bid documents to extract structured information using
    LLM with Pydantic model schemas. Inherits common agent functionality
    from BaseAgent.
    
    The agent autonomously:
    1. Retrieves processed documents from Parser output
    2. Analyzes content using structured output (Pydantic schemas)
    3. Extracts:
       - Client information (name, location, domain, contacts)
       - Key stakeholders and their roles
       - Opportunity assessment
       - Process understanding
       - Required documents list
       - Deadlines and submission details
    4. Generates analysis markdown for user review
    5. Updates AgentTask with structured output
    
    Example:
        ```python
        # Create analysis agent (like Java)
        analysis = AnalysisAgent(mode="workflow")
        
        # Get Strands Agent and invoke
        result = await analysis.ainvoke({
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
        Initialize Analysis Agent.
        
        Args:
            mode: Agent mode (workflow/ai_assistant)
            provider: LLM provider (defaults to env DEFAULT_LLM_PROVIDER)
            model_id: Model ID (defaults to provider's default from env)
            **kwargs: Additional configuration
        """
        super().__init__(mode, provider, model_id, **kwargs)
        logger.info(f"AnalysisAgent initialized (mode={mode})")
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """
        Analysis-specific configuration.
        
        Returns:
            Configuration dict with:
            - max_tool_iterations: Number of tool calls allowed (30 for analysis)
            - require_tool_approval: Whether to require human approval (False)
        """
        return {
            "max_tool_iterations": 30,
            "require_tool_approval": False
        }


__all__ = ["AnalysisAgent"]