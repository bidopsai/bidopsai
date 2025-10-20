"""
Parser Agent - Document Processing Specialist

Processes documents using Bedrock Data Automation MCP tools.
Implements proper OOP design inheriting from BaseAgent.

Responsibilities:
- Retrieve project documents from database
- Process documents using Bedrock Data Automation MCP
- Update database with processed file locations
- Handle errors gracefully

Mode Support:
- Workflow: Sequential document processing task
- AI Assistant: On-demand document parsing queries
"""

import logging
from typing import Optional, Dict, Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ParserAgent(BaseAgent):
    """
    Parser Agent - Document Processing Specialist.
    
    Processes documents using Bedrock Data Automation MCP tools following
    the workflow defined in system prompts. Inherits common agent functionality
    from BaseAgent.
    
    The agent autonomously:
    1. Queries database for project documents (ProjectDocument table)
    2. Retrieves raw document locations (raw_file_location)
    3. Processes documents using Bedrock Data Automation MCP
    4. Saves processed documents to S3
    5. Updates database with processed file locations
    6. Updates AgentTask status and output_data
    
    Example:
        ```python
        # Create parser agent (like Java)
        parser = ParserAgent(mode="workflow")
        
        # Get Strands Agent and invoke
        result = await parser.ainvoke({
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
        Initialize Parser Agent.
        
        Args:
            mode: Agent mode (workflow/ai_assistant)
            provider: LLM provider (defaults to env DEFAULT_LLM_PROVIDER)
            model_id: Model ID (defaults to provider's default from env)
            **kwargs: Additional configuration
        """
        super().__init__(mode, provider, model_id, **kwargs)
        logger.info(f"ParserAgent initialized (mode={mode})")
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """
        Parser-specific configuration.
        
        Returns:
            Configuration dict with:
            - max_tool_iterations: Number of tool calls allowed (20 for parsing)
            - require_tool_approval: Whether to require human approval (False)
        """
        return {
            "max_tool_iterations": 20,
            "require_tool_approval": False
        }


__all__ = ["ParserAgent"]