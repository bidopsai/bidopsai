"""
AI Assistant Supervisor Agent - Intent-Based AI Assistance

Provides intent-based routing for AI assistant queries.
Implements proper OOP design inheriting from BaseAgent.

Responsibilities:
- Understand user intent from natural language queries
- Route to appropriate specialized sub-agents
- Provide contextual assistance without workflow constraints
- Support ad-hoc document analysis and generation
- Answer questions about projects and artifacts

Mode: Fixed to "ai_assistant" for intent-based behavior
"""

import logging
from typing import Optional, Dict, Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AIAssistantSupervisor(BaseAgent):
    """
    AI Assistant Supervisor - Intent-Based AI Assistance.
    
    Provides flexible, intent-based AI assistance without the constraints
    of sequential workflow. Routes user queries to appropriate sub-agents
    based on detected intent using Intent Router pattern.
    
    Use Cases:
    - Ad-hoc document analysis ("Analyze this RFP")
    - Quick artifact generation ("Create an executive summary")
    - Project queries ("What's the status of Project X?")
    - Knowledge base searches ("Find past bids for healthcare")
    - Compliance checks ("Is this compliant with SOC2?")
    
    The supervisor autonomously:
    1. Analyzes user query to detect intent
    2. Routes to appropriate sub-agent(s):
       - Parser: Document processing requests
       - Analysis: RFP analysis queries
       - Content: Artifact generation requests
       - Knowledge: Historical data searches
       - Compliance: Compliance verification
       - QA: Quality assessment queries
    3. Aggregates multi-agent responses if needed
    4. Provides conversational, helpful responses
    
    Mode Behavior:
    - Mode is hardcoded to "ai_assistant" for intent routing
    - Uses Intent Router pattern (not StateGraph)
    - No workflow constraints - handles one-off requests
    - Stateless execution per query
    
    Example:
        ```python
        # Create AI assistant supervisor (Java-style)
        assistant = AIAssistantSupervisor()
        
        # Get Strands Agent and invoke
        agent = assistant.get_agent()
        result = await agent.ainvoke({
            "messages": [{
                "role": "user",
                "content": "Analyze the healthcare RFP document"
            }]
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
        Initialize AI Assistant Supervisor.
        
        Mode is hardcoded to "ai_assistant" for intent-based routing.
        The supervisor uses Intent Router pattern for flexible assistance.
        
        Args:
            provider: LLM provider (defaults to env DEFAULT_LLM_PROVIDER)
            model_id: Model ID (defaults to provider's default from env)
            **kwargs: Additional configuration
        """
        # Mode hardcoded for AI assistant behavior
        super().__init__(mode="ai_assistant", provider=provider, model_id=model_id, **kwargs)
        logger.info("AIAssistantSupervisor initialized (mode=ai_assistant)")
    
    @property
    def agent_name(self) -> str:
        """
        Override agent name for tool/prompt resolution.
        
        Returns "supervisor" instead of "aiassistantsupervisor" to match
        tool configuration naming convention.
        
        Returns:
            "supervisor" for tool and prompt resolution
        """
        return "supervisor"
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """
        AI assistant supervisor specific configuration.
        
        Returns:
            Configuration dict with:
            - max_tool_iterations: Moderate limit for conversational flow (50)
            - require_tool_approval: Whether to require human approval (False)
        """
        return {
            "max_tool_iterations": 50,
            "require_tool_approval": False
        }


__all__ = ["AIAssistantSupervisor"]