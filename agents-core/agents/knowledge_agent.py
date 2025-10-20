"""
Knowledge Agent - Knowledge Base Query Specialist

Queries Bedrock Knowledge Bases for historical bid data and Q&A content.
Implements proper OOP design inheriting from BaseAgent.

Responsibilities:
- Query Bedrock Knowledge Bases using RAG
- Retrieve historical bid documents and Q&A responses
- Provide context to Content Agent for artifact generation
- Support both project-specific and global knowledge bases

Mode Support:
- Workflow: Used by Content Agent during artifact generation
- AI Assistant: Direct knowledge base queries for user questions
"""

import logging
from typing import Optional, Dict, Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class KnowledgeAgent(BaseAgent):
    """
    Knowledge Agent - Knowledge Base Query Specialist.
    
    Queries Bedrock Knowledge Bases to retrieve historical bid data,
    past Q&A responses, and reference materials. Used as a tool by
    other agents (especially Content Agent) via Composition pattern.
    
    The agent autonomously:
    1. Accepts query parameters (keywords, filters, KB IDs)
    2. Queries Bedrock Knowledge Bases using RAG
    3. Retrieves relevant historical documents:
       - Past bid responses
       - Q&A answers
       - Case studies
       - Reference materials
    4. Returns structured results with source references
    
    Example:
        ```python
        # Create knowledge agent (like Java)
        knowledge = KnowledgeAgent(mode="workflow")
        
        # Get Strands Agent and invoke
        result = await knowledge.ainvoke({
            "query": "AI security compliance",
            "knowledge_base_ids": ["kb-uuid-1", "kb-uuid-2"]
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
        Initialize Knowledge Agent.
        
        Args:
            mode: Agent mode (workflow/ai_assistant)
            provider: LLM provider (defaults to env DEFAULT_LLM_PROVIDER)
            model_id: Model ID (defaults to provider's default from env)
            **kwargs: Additional configuration
        """
        super().__init__(mode, provider, model_id, **kwargs)
        logger.info(f"KnowledgeAgent initialized (mode={mode})")
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """
        Knowledge-specific configuration.
        
        Returns:
            Configuration dict with:
            - max_tool_iterations: Number of tool calls allowed (20 for KB queries)
            - require_tool_approval: Whether to require human approval (False)
        """
        return {
            "max_tool_iterations": 20,
            "require_tool_approval": False
        }


__all__ = ["KnowledgeAgent"]