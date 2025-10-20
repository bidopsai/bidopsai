"""
AI Assistant Agent Builder - Pure Strands GraphBuilder Pattern

Builds Intent Router graph using Strands GraphBuilder.
Routes classified intents to appropriate sub-agents with mode="ai_assistant".

CRITICAL: This uses PURE Strands GraphBuilder pattern - NO LangGraph!
"""

import logging
from typing import Dict
from strands.multiagent import GraphBuilder
from strands import Agent

from agents import (
    AnalysisAgent,
    ContentAgent,
    KnowledgeAgent
)
from core.config import get_config
from prompts.prompt_manager import PromptManager
from supervisors.ai_assistant.intent_classifier import (
    classify_intent,
    get_clarification_prompt,
    validate_context_availability,
)
from supervisors.ai_assistant.state_models import (
    IntentType,
    INTENT_ROUTES,
)
from tools.tool_manager import ToolManager

logger = logging.getLogger(__name__)


# Global instances (initialized once per app startup)
_tool_manager: ToolManager = None
_prompt_manager: PromptManager = None


async def initialize_managers(cognito_jwt: str = None):
    """Initialize shared managers for AI Assistant"""
    global _tool_manager, _prompt_manager
    
    if _tool_manager is None:
        _tool_manager = ToolManager(cognito_jwt)
        await _tool_manager.initialize()
        logger.info("ToolManager initialized for AI Assistant")
    
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
        logger.info("PromptManager initialized for AI Assistant")


def _should_retry(state) -> bool:
    """
    Conditional edge: Check if should retry classification.
    
    Strands pattern: Check state.results for error conditions.
    
    Args:
        state: Strands graph state
        
    Returns:
        True if should retry, False otherwise
    """
    # Get routing result
    route_result = state.results.get("route_to_agent")
    if not route_result:
        return False
    
    # Extract result data
    result_data = route_result.result if hasattr(route_result, "result") else {}
    if isinstance(result_data, dict):
        has_errors = result_data.get("has_errors", False)
        retry_count = result_data.get("retry_count", 0)
        return has_errors and retry_count < 2
    
    return False


def build_ai_assistant_graph(cognito_jwt: str = None):
    """
    Build AI Assistant Intent Router graph using pure Strands GraphBuilder.
    
    Graph structure (Pure Strands Pattern):
    START -> classify_intent -> route_to_agent -> END
                                      |
                                  (on error)
                                      |
                                   retry -> classify_intent
    
    Args:
        cognito_jwt: User JWT token for AgentCore Gateway authentication
    
    Returns:
        Compiled Strands Graph ready for execution
    """
    # Initialize managers
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(initialize_managers(cognito_jwt))
        else:
            loop.run_until_complete(initialize_managers(cognito_jwt))
    except RuntimeError:
        # No event loop, will be initialized on first use
        pass
    
    # Initialize GraphBuilder (Pure Strands)
    builder = GraphBuilder()
    
    # ========================================
    # Create Agent Instances
    # ========================================
    
    # Classifier agent - Determines user intent
    classifier_agent = Agent(
        name="intent_classifier",
        system_prompt="""You are an intent classification agent for an AI assistant.
        
Your task is to analyze user queries and classify them into one of these intents:
- ANALYSIS_QUESTION: Questions about project analysis, documents, or RFP requirements
- CONTENT_QUESTION: Questions about generating or editing content/artifacts
- KNOWLEDGE_QUESTION: Questions about past bids, company knowledge, or Q&A history
- GENERAL_QUESTION: General questions or chitchat
- CLARIFICATION_NEEDED: When context is missing or query is unclear

Return your classification as JSON:
{
    "intent": "<intent_type>",
    "confidence": <0.0-1.0>,
    "entities": {"key": "value"},
    "reasoning": "explanation",
    "requires_context": true/false
}"""
    )
    
    # Router agent - Routes to appropriate sub-agent
    router_agent = Agent(
        name="intent_router",
        system_prompt="""You are a routing agent for an AI assistant.

Based on the classified intent, you route queries to specialized agents:
- Analysis queries → AnalysisAgent
- Content queries → ContentAgent  
- Knowledge queries → KnowledgeAgent
- General queries → Handle directly

You coordinate execution and return the final response to the user.

Return responses as JSON:
{
    "response": "agent response text",
    "agent_name": "agent_used",
    "has_errors": false,
    "retry_count": 0
}"""
    )
    
    # ========================================
    # Add Nodes (Pure Strands Pattern)
    # ========================================
    
    builder.add_node(classifier_agent, "classify_intent")
    builder.add_node(router_agent, "route_to_agent")
    
    # ========================================
    # Set Entry Point
    # ========================================
    
    builder.set_entry_point("classify_intent")
    
    # ========================================
    # Add Edges (Pure Strands Pattern)
    # ========================================
    
    # Sequential: classify → route
    builder.add_edge("classify_intent", "route_to_agent")
    
    # Conditional: retry on error
    builder.add_edge("route_to_agent", "classify_intent", condition=_should_retry)
    
    # ========================================
    # Build Graph
    # ========================================
    
    graph = builder.build()
    
    logger.info("AI Assistant Intent Router graph compiled successfully (Pure Strands)")
    
    return graph


def get_ai_assistant_graph(cognito_jwt: str = None):
    """
    Get compiled AI Assistant graph (singleton pattern).
    
    Args:
        cognito_jwt: User JWT token
        
    Returns:
        Compiled Strands Graph instance
    """
    return build_ai_assistant_graph(cognito_jwt)