"""
AI Assistant Supervisor Module

Intent-based conversational agent using Intent Router pattern.
Classifies user queries and routes to specialized sub-agents.

Architecture:
- IntentClassifier: Determines user intent from natural language
- IntentRouter: Routes classified intent to appropriate sub-agent
- Reuses sub-agents from agents/ with mode="ai_assistant"
- Separate prompts from workflow mode
- Stateless conversations (no workflow state)

Deployment:
- Separate AgentCore Runtime from Workflow Supervisor
- FastAPI app on port 8001
- SSE streaming for responses
- Session-based memory (no persistent workflow state)
"""

from .agent_builder import build_ai_assistant_graph
from .agent_executor import app as ai_assistant_app
from .intent_classifier import classify_intent, IntentType
from .state_models import IntentRouterState, ConversationContext

__all__ = [
    "build_ai_assistant_graph",
    "ai_assistant_app",
    "classify_intent",
    "IntentType",
    "IntentRouterState",
    "ConversationContext",
]