"""
AI Assistant Supervisor - AgentCore Runtime Application

AWS Bedrock AgentCore application for AI Assistant conversations using
Intent Router pattern. Deployed as separate AgentCore Runtime.

This module provides conversational AI capabilities with intent classification
and agent routing for bid management tasks.

Key Features:
- BedrockAgentCoreApp runtime (replaces FastAPI)
- @app.entrypoint decorator for conversational invocation
- Intent Router pattern for query classification
- Native streaming with AgentCore
- RequestContext integration
- Session-based conversation context
- Health check endpoint

Architecture:
- Uses AIAssistantSupervisor OOP class
- Intent classification → Agent routing
- Context-aware conversations
- Multi-turn dialog support
- AgentCore Memory integration
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any
from uuid import UUID, uuid4

from bedrock_agentcore import BedrockAgentCoreApp, RequestContext
from pydantic import BaseModel, Field

from core.config import get_config
from core.conversation_manager import ConversationManager
from core.memory import get_memory_manager
from core.database import init_database, close_database, db_pool
from core.error_handling import AgentError, ErrorCode, ErrorSeverity
from core.observability import (
    log_agent_action,
    initialize_observability,
    track_agent_performance,
    get_observability_manager
)
from models.request_models import InvocationRequest
from supervisors.ai_assistant.state_models import (
    IntentRouterState,
    ConversationContext,
)
from supervisors.ai_assistant.agent_builder import build_ai_assistant_graph
from tools.tool_config import configure_all_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ========================================
# AgentCore Application
# ========================================

app = BedrockAgentCoreApp(
    debug=get_config().environment == "development"
)


# ========================================
# Application Lifecycle Management
# ========================================

@app.on_event("startup")
async def startup_event():
    """
    Application startup - initialize core services.
    
    Initializes:
    - Database pool
    - AgentCore Memory system
    - Memory manager (conversation persistence)
    - Conversation manager
    - Observability (LangFuse, OTEL)
    - Tool configuration
    """
    logger.info("Starting AI Assistant Supervisor...")
    
    log_agent_action(
        agent_name="ai_assistant_executor",
        action="startup_begin",
        details={"environment": get_config().environment}
    )
    
    try:
        # Initialize core services
        await init_database()
        
        # Initialize memory manager (AgentCore Memory integrated via Phase 4)
        get_memory_manager()
        initialize_observability()
        
        # Initialize tool configuration
        configure_all_tools()
        
        log_agent_action(
            agent_name="ai_assistant_executor",
            action="startup_complete",
            details={
                "services": ["database", "memory_manager", "observability", "tools"],
                "mode": "ai_assistant"
            }
        )
        
        logger.info("AI Assistant Supervisor started successfully on port 8001")
        
    except Exception as e:
        log_agent_action(
            agent_name="ai_assistant_executor",
            action="startup_failed",
            details={"error": str(e)},
            level="error"
        )
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown - cleanup resources.
    
    Cleanup:
    - Close database connections
    - Flush observability data
    """
    logger.info("Shutting down AI Assistant Supervisor...")
    
    log_agent_action(
        agent_name="ai_assistant_executor",
        action="shutdown_begin"
    )
    
    try:
        # Close database pool
        await close_database()
        
        log_agent_action(
            agent_name="ai_assistant_executor",
            action="shutdown_complete"
        )
        
        logger.info("AI Assistant Supervisor shutdown complete")
        
    except Exception as e:
        log_agent_action(
            agent_name="ai_assistant_executor",
            action="shutdown_failed",
            details={"error": str(e)},
            level="error"
        )


# ========================================
# Health Check Endpoint
# ========================================

@app.route("/health", methods=["GET"])
async def health_check():
    """
    Health check endpoint.
    
    Checks:
    - Database connectivity
    - Memory manager status
    
    Returns:
        JSON with health status and service checks
    """
    try:
        # Check database
        db_healthy = db_pool.is_initialized
        
        # Check memory manager
        memory_manager = get_memory_manager()
        memory_healthy = memory_manager is not None
        
        all_healthy = db_healthy and memory_healthy
        
        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "service": "ai-assistant-supervisor",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": "up" if db_healthy else "down",
                "memory": "up" if memory_healthy else "down"
            }
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "ai-assistant-supervisor",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# ========================================
# Main AI Assistant Invocation Entrypoint
# ========================================

@app.entrypoint
@track_agent_performance(agent_name="ai_assistant_executor")
async def invoke_ai_assistant(
    request: InvocationRequest,
    context: RequestContext
):
    """
    Invoke AI Assistant with user query (AgentCore native streaming).
    
    This endpoint handles conversational AI interactions using Intent Router pattern.
    Each query is classified and routed to appropriate sub-agent.
    
    Yields events in real-time as they occur:
    - intent_classifying: Intent classification started
    - intent_classified: Intent and agent selected
    - agent_responding: Agent processing query
    - response_ready: Final response available
    - conversation_completed: Conversation turn finished
    
    Args:
        request: InvocationRequest with:
            - user_id: UUID of user
            - session_id: Session ID for conversation continuity
            - project_id: Optional UUID for project context
            - user_input: Dict with "chat" key containing user query
        context: RequestContext from AgentCore with:
            - user_id: Authenticated user ID
            - session_id: AgentCore session ID
            - metadata: Additional context
    
    Yields:
        Event dictionaries with type, status, data, timestamp
    
    Raises:
        AgentError: On validation or execution errors
    """
    conversation_id = uuid4()
    
    log_agent_action(
        agent_name="ai_assistant_executor",
        action="invocation_received",
        details={
            "user_id": str(request.user_id),
            "session_id": request.session_id,
            "conversation_id": str(conversation_id),
            "has_project": request.project_id is not None,
            "context_user_id": context.user_id,
            "context_session_id": context.session_id
        }
    )
    
    try:
        # Validate request
        if not request.user_input or not request.user_input.get("chat"):
            raise AgentError(
                message="user_input.chat is required for AI Assistant",
                code=ErrorCode.VALIDATION_ERROR,
                severity=ErrorSeverity.LOW
            )
        
        user_query = request.user_input["chat"]
        
        logger.info(
            f"AI Assistant invocation - User: {request.user_id}, "
            f"Session: {request.session_id}, Query: {user_query[:100]}..."
        )
        
        # Load conversation context from session memory
        conversation_context = await _load_conversation_context(
            user_id=request.user_id,
            session_id=request.session_id,
            project_id=request.project_id
        )
        
        # Persist user input to conversation history
        if request.project_id:
            conversation_manager = ConversationManager()
            await conversation_manager.add_user_message(
                project_id=request.project_id,
                session_id=request.session_id,
                user_id=request.user_id,
                message_type="chat",
                content=user_query
            )
        
        # Execute AI Assistant with real-time streaming
        final_response = None
        final_agent = None
        final_metadata = {}
        
        async for event in _execute_ai_assistant_with_streaming(
            user_query=user_query,
            conversation_context=conversation_context,
            conversation_id=conversation_id,
            request=request,
            context=context
        ):
            # Yield each event immediately to AgentCore
            yield event
            
            # Capture final response for persistence
            if event["type"] == "response_ready":
                final_response = event.get("response")
                final_metadata = event.get("metadata", {})
            elif event["type"] == "intent_classified":
                final_agent = event.get("agent", "ai_assistant")
        
        # Persist agent response after streaming completes
        if request.project_id and final_response:
            conversation_manager = ConversationManager()
            await conversation_manager.add_agent_message(
                project_id=request.project_id,
                session_id=request.session_id,
                agent_name=final_agent,
                content=final_response,
                metadata=final_metadata
            )
        
        log_agent_action(
            agent_name="ai_assistant_executor",
            action="invocation_complete",
            details={
                "conversation_id": str(conversation_id),
                "agent": final_agent
            }
        )
        
    except AgentError as e:
        log_agent_action(
            agent_name="ai_assistant_executor",
            action="invocation_failed",
            details={
                "conversation_id": str(conversation_id),
                "error_code": e.code,
                "error_message": str(e),
                "severity": e.severity
            },
            level="error"
        )
        raise
        
    except Exception as e:
        log_agent_action(
            agent_name="ai_assistant_executor",
            action="invocation_failed",
            details={
                "conversation_id": str(conversation_id),
                "error": str(e)
            },
            level="error"
        )
        
        raise AgentError(
            message=f"AI Assistant error: {str(e)}",
            code=ErrorCode.INTERNAL_ERROR,
            severity=ErrorSeverity.HIGH
        )


# ========================================
# Helper Functions
# ========================================

async def _load_conversation_context(
    user_id: UUID,
    session_id: str,
    project_id: UUID = None
) -> ConversationContext:
    """
    Load conversation context for AI Assistant.
    
    Creates minimal conversation context. Full context is managed by
    AgentCore Memory system integrated in Phase 4 via agent.with_memory().
    
    Args:
        user_id: User ID
        session_id: Session ID from RequestContext
        project_id: Optional project ID for context
    
    Returns:
        ConversationContext for this conversation turn
    """
    log_agent_action(
        agent_name="ai_assistant_executor",
        action="creating_conversation_context",
        details={
            "session_id": session_id,
            "user_id": str(user_id),
            "has_project": project_id is not None
        }
    )
    
    # Create conversation context
    # Note: Agent memory is handled via Phase 4's with_memory() integration
    return ConversationContext(
        user_id=user_id,
        session_id=session_id,
        project_id=project_id,
        conversation_history=[],  # Agent memory handles history
        user_preferences={}  # Agent memory handles preferences
    )


async def _execute_ai_assistant_with_streaming(
    user_query: str,
    conversation_context: ConversationContext,
    conversation_id: UUID,
    request: InvocationRequest,
    context: RequestContext
):
    """
    Execute AI Assistant with real-time event streaming.
    
    Yields events as they occur during intent classification and agent execution.
    
    Args:
        supervisor: AIAssistantSupervisor instance
        user_query: User's query text
        conversation_context: Loaded conversation context
        conversation_id: UUID for this conversation turn
        request: Original invocation request
        context: RequestContext from AgentCore
    
    Yields:
        Event dictionaries with type, data, timestamp
    """
    log_agent_action(
        agent_name="ai_assistant_executor",
        action="ai_assistant_execution_start",
        details={
            "conversation_id": str(conversation_id),
            "query_length": len(user_query)
        }
    )
    
    # Start conversation performance tracking
    conversation_start_time = time.time()
    obs = get_observability_manager()
    
    try:
        # Create initial state
        initial_state = IntentRouterState(
            user_query=user_query,
            conversation_context=conversation_context
        )
        
        # Get compiled graph from builder
        graph = build_ai_assistant_graph()
        
        # Configure graph
        config = {
            "configurable": {
                "thread_id": request.session_id,
                "user_id": str(request.user_id)
            }
        }
        
        # Emit intent classification started
        yield {
            "type": "intent_classifying",
            "status": "classifying user intent",
            "conversation_id": str(conversation_id),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Execute graph with streaming
        final_state = None
        async for event in graph.astream(initial_state, config):
            # Each event represents a node completion
            node_name = list(event.keys())[0] if event else None
            node_state = event.get(node_name) if node_name else None
            
            if node_name == "classify_intent" and node_state:
                # Intent classified
                if node_state.classified_intent:
                    yield {
                        "type": "intent_classified",
                        "intent": node_state.classified_intent.intent.value,
                        "confidence": node_state.classified_intent.confidence,
                        "agent": node_state.selected_agent,
                        "conversation_id": str(conversation_id),
                        "timestamp": datetime.utcnow().isoformat()
                    }
            
            elif node_name == "route_to_agent" and node_state:
                # Agent selected and responding
                yield {
                    "type": "agent_responding",
                    "agent": node_state.selected_agent,
                    "conversation_id": str(conversation_id),
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Update final state
            final_state = node_state if node_state else final_state
        
        # Emit response ready
        if final_state and final_state.agent_response:
            yield {
                "type": "response_ready",
                "response": final_state.agent_response,
                "metadata": final_state.response_metadata,
                "conversation_id": str(conversation_id),
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Calculate duration
        final_state.completed_at = datetime.utcnow()
        duration = (final_state.completed_at - final_state.started_at).total_seconds()
        
        # Record conversation duration metric
        conversation_duration = time.time() - conversation_start_time
        agent_name = f"ai_assistant_{final_state.selected_agent}" if final_state.selected_agent else "ai_assistant"
        obs.record_agent_task_duration(
            duration_seconds=conversation_duration,
            agent_name=agent_name,
            status="completed",
            task_id=str(conversation_id)
        )
        
        # Record LLM token usage if available
        if final_state.response_metadata and "usage" in final_state.response_metadata:
            usage = final_state.response_metadata["usage"]
            if "total_tokens" in usage:
                obs.record_llm_tokens(
                    token_count=usage["total_tokens"],
                    token_type="total",
                    model=get_config().bedrock_model_id
                )
        
        # Emit conversation completed
        yield {
            "type": "conversation_completed",
            "conversation_id": str(conversation_id),
            "duration_seconds": duration,
            "errors": final_state.errors,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Persist session context for conversation continuity
        await _persist_session_context(
            session_id=request.session_id,
            user_id=str(request.user_id),
            conversation_context=conversation_context,
            final_state=final_state
        )
        
        log_agent_action(
            agent_name="ai_assistant_executor",
            action="ai_assistant_execution_complete",
            details={
                "conversation_id": str(conversation_id),
                "duration": duration,
                "intent": final_state.classified_intent.intent.value if final_state.classified_intent else None,
                "agent": final_state.selected_agent
            }
        )
        
    except Exception as e:
        # Record error metric
        conversation_duration = time.time() - conversation_start_time
        obs.record_agent_error(
            agent_name="ai_assistant_executor",
            error_type=type(e).__name__,
            error_code=getattr(e, 'code', ErrorCode.EXECUTION_ERROR)
        )
        
        # Record failed conversation duration
        obs.record_agent_task_duration(
            duration_seconds=conversation_duration,
            agent_name="ai_assistant_error",
            status="failed",
            task_id=str(conversation_id)
        )
        
        log_agent_action(
            agent_name="ai_assistant_executor",
            action="ai_assistant_execution_failed",
            details={
                "conversation_id": str(conversation_id),
                "error": str(e),
                "duration_seconds": conversation_duration
            },
            level="error"
        )
        
        raise AgentError(
            message=f"AI Assistant execution failed: {str(e)}",
            code=ErrorCode.EXECUTION_ERROR,
            severity=ErrorSeverity.HIGH
        )


async def _persist_session_context(
    session_id: str,
    user_id: str,
    conversation_context: ConversationContext,
    final_state: IntentRouterState
) -> None:
    """
    Log session completion (persistence handled by AgentCore Memory).
    
    Session context is automatically persisted by AgentCore Memory system
    via Phase 4 integration. This function logs the completion for observability.
    
    Args:
        session_id: Session ID
        user_id: User ID
        conversation_context: Current conversation context
        final_state: Final state from execution
    """
    log_agent_action(
        agent_name="ai_assistant_executor",
        action="session_completed",
        details={
            "session_id": session_id,
            "user_id": user_id,
            "intent": final_state.classified_intent.intent.value if final_state.classified_intent else None,
            "agent": final_state.selected_agent,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# ========================================
# Main Entry Point
# ========================================

if __name__ == "__main__":
    # Use bedrock_agentcore_starter_toolkit for deployment
    # For local development, AgentCore provides dev server
    import uvicorn
    
    config = get_config()
    
    # Note: In production, this will be deployed via AgentCore Runtime
    # For local dev, we can still use uvicorn with the ASGI app
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,  # Different port from Workflow Supervisor (8000)
        log_level="info",
        access_log=True
    )