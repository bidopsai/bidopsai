"""
Content Agent - Artifact Generation Specialist

Generates bid artifacts using historical data from Knowledge Agent.
Implements proper OOP design with Composition pattern.

Responsibilities:
- Use Knowledge Agent to query historical bid data
- Generate TipTap JSON artifacts for documents, Q&A, and spreadsheets
- Create multiple artifact types based on Analysis output
- Store artifacts in database with versioning

Mode Support:
- Workflow: Sequential artifact generation after analysis
- AI Assistant: On-demand artifact generation or updates
"""

import logging
from typing import Optional, Dict, Any

from agents.base_agent import BaseAgent
from agents.knowledge_agent import KnowledgeAgent

logger = logging.getLogger(__name__)


class ContentAgent(BaseAgent):
    """
    Content Agent - Artifact Generation Specialist.
    
    Generates bid artifacts in TipTap JSON format using historical data
    retrieved by KnowledgeAgent (Composition pattern). Creates multiple
    document types with structured output schemas.
    
    Composition Pattern:
        ContentAgent HAS-A KnowledgeAgent for historical data retrieval.
        The knowledge agent is created during initialization and used
        internally to fetch relevant bid data.
    
    The agent autonomously:
    1. Retrieves Analysis output to understand required documents
    2. Uses KnowledgeAgent to query historical bids and Q&A
    3. Generates TipTap JSON artifacts for each document type:
       - Executive summaries (worddoc/document)
       - RFP Q&A responses (pdf/q_and_a)
       - System design docs (worddoc/document)
       - Pricing spreadsheets (excel/excel)
       - Cover letters (worddoc/document)
       - Case studies (ppt/document)
    4. Creates Artifact and ArtifactVersion records in database
    5. Returns structured artifact metadata array
    
    Example:
        ```python
        # Create content agent (like Java)
        content = ContentAgent(mode="workflow")
        
        # Get Strands Agent and invoke
        result = await content.ainvoke({
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
        Initialize Content Agent with composed KnowledgeAgent.
        
        Args:
            mode: Agent mode (workflow/ai_assistant)
            provider: LLM provider (defaults to env DEFAULT_LLM_PROVIDER)
            model_id: Model ID (defaults to provider's default from env)
            **kwargs: Additional configuration
        """
        super().__init__(mode, provider, model_id, **kwargs)
        
        # Composition: ContentAgent HAS-A KnowledgeAgent
        self._knowledge_agent = KnowledgeAgent(
            mode=mode,
            provider=provider,
            model_id=model_id
        )
        
        logger.info(f"ContentAgent initialized with KnowledgeAgent (mode={mode})")
    
    @property
    def knowledge_agent(self) -> KnowledgeAgent:
        """Access to composed KnowledgeAgent instance."""
        return self._knowledge_agent
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """
        Content-specific configuration.
        
        Returns:
            Configuration dict with:
            - max_tool_iterations: Number of tool calls allowed (50 for content generation)
            - require_tool_approval: Whether to require human approval (False)
        """
        return {
            "max_tool_iterations": 50,
            "require_tool_approval": False
        }


__all__ = ["ContentAgent"]