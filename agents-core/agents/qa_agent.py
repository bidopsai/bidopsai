"""
QA Agent - Quality Assurance Specialist

Validates artifacts against requirements and quality standards.
Implements proper OOP design inheriting from BaseAgent.

Responsibilities:
- Verify artifacts meet Analysis requirements
- Check for completeness and missing documents
- Validate content quality and accuracy
- Provide structured feedback with gap analysis

Mode Support:
- Workflow: Sequential QA check after compliance verification
- AI Assistant: On-demand quality reviews
"""

import logging
from typing import Optional, Dict, Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class QAAgent(BaseAgent):
    """
    QA Agent - Quality Assurance Specialist.
    
    Validates artifacts against Analysis requirements, checking for
    completeness, accuracy, and quality. Identifies missing documents
    and provides structured feedback for improvements.
    
    The agent autonomously:
    1. Retrieves artifacts and Analysis output
    2. Validates each artifact against:
       - Analysis requirements (expected documents)
       - Content completeness (all sections present)
       - Quality standards (accuracy, clarity, formatting)
       - Client-specific requirements
    3. Identifies missing artifacts
    4. Generates structured feedback:
       - Per-artifact validation results
       - Missing artifact list with descriptions
       - Overall summary with status (partial/complete/failed)
    5. Updates AgentTask with QA results
    
    Example:
        ```python
        # Create QA agent (like Java)
        qa = QAAgent(mode="workflow")
        
        # Get Strands Agent and invoke
        result = await qa.ainvoke({
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
        Initialize QA Agent.
        
        Args:
            mode: Agent mode (workflow/ai_assistant)
            provider: LLM provider (defaults to env DEFAULT_LLM_PROVIDER)
            model_id: Model ID (defaults to provider's default from env)
            **kwargs: Additional configuration
        """
        super().__init__(mode, provider, model_id, **kwargs)
        logger.info(f"QAAgent initialized (mode={mode})")
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """
        QA-specific configuration.
        
        Returns:
            Configuration dict with:
            - max_tool_iterations: Number of tool calls allowed (40 for QA)
            - require_tool_approval: Whether to require human approval (False)
        """
        return {
            "max_tool_iterations": 40,
            "require_tool_approval": False
        }


__all__ = ["QAAgent"]