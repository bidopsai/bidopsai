"""
State models for AI Assistant Intent Router

Intent Router uses stateless conversations - each query is independent.
State is minimal compared to Workflow Supervisor's complex graph state.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """Types of user intents for AI Assistant routing"""
    
    QUERY_PROJECT_STATUS = "query_project_status"
    ASK_ABOUT_RFP = "ask_about_rfp"
    REQUEST_ARTIFACT_EDIT = "request_artifact_edit"
    GENERAL_QUESTION = "general_question"
    CLARIFICATION_NEEDED = "clarification_needed"


class ConversationContext(BaseModel):
    """Context for current conversation (from session memory)"""
    
    user_id: UUID
    session_id: str
    project_id: Optional[UUID] = None
    active_workflow_id: Optional[UUID] = None
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)


class IntentClassification(BaseModel):
    """Result of intent classification"""
    
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    entities: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str
    requires_context: bool = False


class IntentRouterState(BaseModel):
    """
    State for Intent Router graph - minimal compared to Workflow
    
    Intent Router is stateless by design:
    - Each query is independent
    - No persistent workflow state
    - Context loaded from session memory per query
    - Agent responses streamed back immediately
    """
    
    # Input
    user_query: str
    conversation_context: ConversationContext
    
    # Intent classification
    classified_intent: Optional[IntentClassification] = None
    
    # Agent selection
    selected_agent: Optional[str] = None
    agent_tools: List[str] = Field(default_factory=list)
    
    # Response
    agent_response: Optional[str] = None
    response_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Error handling
    errors: List[str] = Field(default_factory=list)
    retry_count: int = 0
    
    # Timestamps
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    class Config:
        arbitrary_types_allowed = True


class AgentRouteConfig(BaseModel):
    """Configuration for routing intent to agent"""
    
    intent: IntentType
    agent_name: str
    mode: str = "ai_assistant"
    tools: List[str]
    prompt_template: str
    requires_project_context: bool = False
    max_tokens: int = 2000
    temperature: float = 0.7


# Predefined routes for each intent type
INTENT_ROUTES: Dict[IntentType, AgentRouteConfig] = {
    IntentType.QUERY_PROJECT_STATUS: AgentRouteConfig(
        intent=IntentType.QUERY_PROJECT_STATUS,
        agent_name="analysis",
        mode="ai_assistant",
        tools=["query_database", "get_workflow_status", "get_project_details"],
        prompt_template="analysis_assistant",
        requires_project_context=True,
        temperature=0.3  # More factual
    ),
    IntentType.ASK_ABOUT_RFP: AgentRouteConfig(
        intent=IntentType.ASK_ABOUT_RFP,
        agent_name="knowledge",
        mode="ai_assistant",
        tools=["search_knowledge_base", "query_database"],
        prompt_template="knowledge_assistant",
        requires_project_context=False,
        temperature=0.5
    ),
    IntentType.REQUEST_ARTIFACT_EDIT: AgentRouteConfig(
        intent=IntentType.REQUEST_ARTIFACT_EDIT,
        agent_name="content",
        mode="ai_assistant",
        tools=["query_database", "get_artifact", "update_artifact"],
        prompt_template="content_assistant",
        requires_project_context=True,
        temperature=0.7
    ),
    IntentType.GENERAL_QUESTION: AgentRouteConfig(
        intent=IntentType.GENERAL_QUESTION,
        agent_name="general",
        mode="ai_assistant",
        tools=["web_search", "query_database"],
        prompt_template="general_assistant",
        requires_project_context=False,
        temperature=0.8  # More creative
    ),
}