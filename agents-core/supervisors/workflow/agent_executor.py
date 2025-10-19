"""
Workflow Agent Executor - AgentCore Runtime Application

AWS Bedrock AgentCore application that exposes the Workflow Supervisor via
the BedrockAgentCoreApp runtime following AWS AgentCore best practices.

This module serves as the entry point for the Workflow Supervisor agent,
providing AgentCore-native endpoints for agent invocation and streaming.

Key Features:
- BedrockAgentCoreApp runtime (replaces FastAPI)
- @app.entrypoint decorator for main invocation
- Native streaming with agent.stream_async()
- RequestContext integration for session management
- Health check endpoint
- Graceful startup/shutdown with resource management
- Request validation with Pydantic models
- AgentCore Memory system integration
- Error handling and observability
- OTEL metrics to CloudWatch (workflow duration, agent task duration, error rates)

Architecture:
- Uses WorkflowSupervisor OOP class for graph execution
- Executes graph with StateGraph pattern
- Handles interruptions for user feedback
- Streams events natively via AgentCore
- Persists conversations via conversation manager
- Integrates with AgentCore Identity and Gateway
"""

import asyncio
import json
import signal
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from bedrock_agentcore import BedrockAgentCoreApp, RequestContext
from pydantic import BaseModel, Field

from core.database import init_database, close_database, db_pool
from core.memory import get_memory_manager
from core.conversation_manager import add_user_input, add_sse_event
from core.config import get_config
from core.error_handling import (
    AgentError,
    ErrorCode,
    ErrorSeverity
)
from core.observability import (
    log_agent_action,
    initialize_observability,
    track_agent_performance,
    get_observability_manager
)
from models.request_models import (
    InvocationRequest,
    InvocationResponse
)
from models.workflow_models import WorkflowExecutionStatus
from tools.tool_config import configure_all_tools
from supervisors.workflow.state_models import WorkflowGraphState


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
    - Observability (LangFuse, OTEL)
    - Tool configuration
    """
    log_agent_action(
        agent_name="workflow_executor",
        action="startup_begin",
        details={"environment": get_config().environment}
    )
    
    try:
        # Initialize core services
        await init_database()  # Creates singleton database pool
        
        # Initialize memory manager (AgentCore Memory integrated via Phase 4)
        get_memory_manager()  # Creates singleton memory manager
        initialize_observability()  # Initialize LangFuse and OTEL
        
        # Initialize tool configuration
        configure_all_tools()
        
        log_agent_action(
            agent_name="workflow_executor",
            action="startup_complete",
            details={
                "services": ["database", "memory_manager", "observability", "tools"],
                "mode": "workflow"
            }
        )
        
    except Exception as e:
        log_agent_action(
            agent_name="workflow_executor",
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
    log_agent_action(
        agent_name="workflow_executor",
        action="shutdown_begin"
    )
    
    try:
        # Close database pool
        await close_database()
        
        log_agent_action(
            agent_name="workflow_executor",
            action="shutdown_complete"
        )
        
    except Exception as e:
        log_agent_action(
            agent_name="workflow_executor",
            action="shutdown_failed",
            details={"error": str(e)},
            level="error"
        )


# ========================================
# Health Check - Automatically provided by BedrockAgentCoreApp
# ========================================
# The /ping endpoint is automatically created by BedrockAgentCoreApp
# Returns: {"status": "Healthy"} or {"status": "HealthyBusy"}
# No custom health endpoint needed - AgentCore Runtime uses /ping


# ========================================
# Main Agent Invocation Entrypoint
# ========================================

@app.entrypoint
async def invoke_workflow(
    payload: dict,
    context: RequestContext
):
    """
    Main agent invocation entrypoint (AgentCore native with streaming).
    
    IMPORTANT: AWS AgentCore passes raw dict payload, NOT Pydantic models.
    This function validates and parses the dict into InvocationRequest model.
    
    Receives workflow execution requests and orchestrates the complete
    bid processing workflow using Strands StateGraph pattern.
    
    Supports two execution modes:
    1. Initial Start (start=True): Creates new workflow, initializes state
    2. Resumption (start=False): Loads from memory, applies user input, resumes
    
    Args:
        payload: Raw dict payload from AgentCore with:
            - project_id: UUID of the project
            - user_id: UUID of the requesting user
            - session_id: Session ID for memory and streaming
            - start: Boolean indicating if this is initial workflow start
            - user_input: Optional user feedback/edits
                - chat: Text feedback/messages
                - content_edits: Artifact edit payloads
        context: RequestContext from AgentCore with:
            - user_id: Authenticated user ID
            - session_id: AgentCore session ID
            - metadata: Additional context
    
    Yields:
        String events (SSE format) with JSON data containing:
        - type: Event type (node_completed, awaiting_feedback, workflow_complete, etc.)
        - data: Event-specific data
        - timestamp: ISO timestamp
    
    Raises:
        AgentError: On validation or execution errors
    """
    # Parse and validate payload (AgentCore passes raw dict, not Pydantic model)
    try:
        # Handle both string and dict payloads
        import json
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        # Validate and parse into Pydantic model
        request = InvocationRequest(**payload)
        
    except Exception as e:
        error_msg = f"Invalid request payload: {str(e)}"
        log_agent_action(
            agent_name="workflow_executor",
            action="payload_validation_failed",
            details={"error": error_msg, "payload": str(payload)},
            level="error"
        )
        
        # Yield error event
        yield {
            "type": "error",
            "data": {
                "error_message": error_msg,
                "error_code": ErrorCode.VALIDATION_ERROR
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        raise AgentError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=error_msg,
            severity=ErrorSeverity.LOW
        )
    
    log_agent_action(
        agent_name="workflow_executor",
        action="invocation_received",
        details={
            "project_id": str(request.project_id),
            "user_id": str(request.user_id),
            "session_id": request.session_id,
            "start": request.start,
            "has_user_input": request.user_input is not None,
            "context_session_id": context.session_id  # RequestContext only has session_id
        }
    )
    
    try:
        # Validate request
        _validate_invocation_request(request)
        
        # Persist user input to conversation history
        if request.user_input:
            await _persist_user_input(request)
        
        # Yield start event - RAW dict, NOT JSON string
        yield {
            "type": "workflow_started",
            "data": {
                "project_id": str(request.project_id),
                "session_id": request.session_id,
                "start": request.start
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Execute workflow with streaming - yield RAW event dicts
        async for event in _execute_workflow_with_streaming(
            request=request,
            context=context
        ):
            # Yield raw event dict - BedrockAgentCoreApp handles JSON serialization
            yield event
        
    except AgentError as e:
        log_agent_action(
            agent_name="workflow_executor",
            action="invocation_failed",
            details={
                "error_code": e.error_code,
                "error_message": str(e),
                "severity": e.severity
            },
            level="error"
        )
        
        # Yield error event
        yield json.dumps({
            "type": "error",
            "data": {
                "error_code": e.error_code,
                "error_message": str(e),
                "severity": e.severity
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        raise
        
    except Exception as e:
        log_agent_action(
            agent_name="workflow_executor",
            action="invocation_failed",
            details={"error": str(e)},
            level="error"
        )
        
        # Yield error event - RAW dict
        yield {
            "type": "error",
            "data": {
                "error_message": f"Internal server error: {str(e)}"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        raise AgentError(
            error_code=ErrorCode.UNKNOWN_ERROR,
            message=f"Internal server error: {str(e)}",
            severity=ErrorSeverity.CRITICAL
        )


# ========================================
# Helper Functions - Validation
# ========================================

def _validate_invocation_request(request: InvocationRequest) -> None:
    """
    Validate invocation request parameters.
    
    Validations:
    - Session ID format and length
    - Start flag consistency
    - User input validation
    
    Args:
        request: Invocation request
        
    Raises:
        AgentError: On validation failure
    """
    # Validate session_id format
    if not request.session_id or len(request.session_id) < 10:
        raise AgentError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Invalid session_id format (minimum 10 characters)",
            severity=ErrorSeverity.LOW
        )
    
    # Validate start flag logic
    if request.start and request.user_input:
        raise AgentError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Cannot provide user_input when start=true (initial workflow start)",
            severity=ErrorSeverity.LOW
        )


async def _persist_user_input(request: InvocationRequest) -> None:
    """
    Persist user input to conversation history.
    
    Args:
        request: Invocation request with user input
    """
    try:
        if request.user_input.chat:
            await add_user_input(
                project_id=request.project_id,
                session_id=request.session_id,
                user_id=request.user_id,
                content=request.user_input.chat,
                message_type="chat",
                metadata={"start": request.start}
            )
        
        if request.user_input.content_edits:
            await add_user_input(
                project_id=request.project_id,
                session_id=request.session_id,
                user_id=request.user_id,
                content=str(request.user_input.content_edits),
                message_type="content_edit",
                metadata={"edit_count": len(request.user_input.content_edits)}
            )
            
    except Exception as e:
        # Log but don't fail workflow if conversation persistence fails
        log_agent_action(
            agent_name="workflow_executor",
            action="conversation_persist_failed",
            details={"error": str(e)},
            level="warning"
        )


# ========================================
# Helper Functions - Workflow Execution
# ========================================

async def _execute_workflow_with_streaming(
    request: InvocationRequest,
    context: RequestContext
):
    """
    Execute workflow using Strands GraphBuilder with native AgentCore streaming.
    
    Handles two execution modes:
    1. Initial start (request.start=True): Create new workflow, initialize state
    2. Resumption (request.start=False): Load from memory, apply user input, resume
    
    Args:
        request: Invocation request
        context: RequestContext from AgentCore
        
    Yields:
        Dictionary events with:
        - type: Event type (node_completed, awaiting_feedback, workflow_complete, error)
        - data: Event-specific data
        - timestamp: ISO timestamp
    """
    log_agent_action(
        agent_name="workflow_executor",
        action="workflow_execution_start",
        details={
            "session_id": request.session_id,
            "mode": "initial" if request.start else "resumption"
        }
    )
    
    # Start workflow performance tracking
    workflow_start_time = time.time()
    obs = get_observability_manager()
    
    try:
        # Prepare initial state
        if request.start:
            # NEW WORKFLOW: Initialize state
            state = _create_initial_state(request)
        else:
            # RESUMPTION: Load from memory and update
            state = await _load_and_update_state(request, context)
        
        # Get the compiled graph directly from builder
        from supervisors.workflow.agent_builder import build_workflow_graph
        graph = build_workflow_graph()
        
        # Strands Graph uses invocation_state for passing shared state
        # The task parameter is a simple string describing the workflow
        task = f"Execute workflow for project_id: {request.project_id}"
        invocation_state = {
            "workflow_state": state,
            "session_id": request.session_id,
            "user_id": str(request.user_id)
        }
        
        # Execute graph using invoke_async (Strands Graph standard method)
        # Note: Strands Graph expects (task: str, invocation_state: dict)
        graph_result = await graph.invoke_async(task, invocation_state)
        
        # Extract final state from graph results
        # The graph_result is a MultiAgentResult containing NodeResults for each node
        final_state = invocation_state.get("workflow_state")
        
        log_agent_action(
            agent_name="workflow_executor",
            action="graph_execution_complete",
            details={
                "workflow_id": str(final_state.workflow_execution_id) if final_state else None,
                "current_agent": final_state.current_agent if final_state else None,
                "completed_tasks": len(final_state.completed_tasks) if final_state else 0
            }
        )
        
        # Check if graph interrupted for user feedback
        if final_state and final_state.awaiting_user_feedback:
            log_agent_action(
                agent_name="workflow_executor",
                action="graph_interrupted",
                details={
                    "workflow_id": str(final_state.workflow_execution_id),
                    "reason": "awaiting_user_feedback"
                }
            )
            
            # Yield awaiting feedback event
            yield {
                "type": "awaiting_feedback",
                "data": {
                    "workflow_id": str(final_state.workflow_execution_id),
                    "message": "Workflow paused - awaiting user feedback",
                    "progress": final_state.calculate_progress()
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Record workflow duration metric
        workflow_duration = time.time() - workflow_start_time
        if final_state:
            obs.record_workflow_duration(
                duration_seconds=workflow_duration,
                workflow_id=str(final_state.workflow_execution_id),
                status=final_state.current_status,
                agent_count=len(final_state.completed_tasks)
            )
        
        # If loop completed without interruption, workflow is complete
        if final_state and not final_state.awaiting_user_feedback:
            log_agent_action(
                agent_name="workflow_executor",
                action="graph_execution_complete",
                details={
                    "workflow_id": str(final_state.workflow_execution_id),
                    "status": final_state.current_status,
                    "duration_seconds": workflow_duration
                }
            )
            
            # Yield completion event
            yield {
                "type": "workflow_complete",
                "data": {
                    "workflow_execution_id": str(final_state.workflow_execution_id),
                    "status": final_state.current_status,
                    "message": _get_status_message(final_state),
                    "duration_seconds": workflow_duration
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        
    except Exception as e:
        # Record error metric
        workflow_duration = time.time() - workflow_start_time
        obs.record_agent_error(
            agent_name="workflow_executor",
            error_type=type(e).__name__,
            error_code=getattr(e, 'error_code', ErrorCode.WORKFLOW_EXECUTION_FAILED)
        )
        
        # Record failed workflow duration
        if hasattr(locals().get('final_state'), 'workflow_execution_id'):
            obs.record_workflow_duration(
                duration_seconds=workflow_duration,
                workflow_id=str(final_state.workflow_execution_id),
                status="failed",
                agent_count=len(final_state.completed_tasks) if final_state else 0
            )
        
        log_agent_action(
            agent_name="workflow_executor",
            action="workflow_execution_failed",
            details={
                "error": str(e),
                "duration_seconds": workflow_duration
            },
            level="error"
        )
        
        # Yield error event
        yield {
            "type": "error",
            "data": {
                "error_message": f"Workflow execution failed: {str(e)}",
                "error_code": ErrorCode.WORKFLOW_EXECUTION_FAILED
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        raise AgentError(
            error_code=ErrorCode.WORKFLOW_EXECUTION_FAILED,
            message=f"Workflow execution failed: {str(e)}",
            severity=ErrorSeverity.HIGH
        )


def _create_initial_state(request: InvocationRequest) -> WorkflowGraphState:
    """
    Create initial state for new workflow execution.
    
    Args:
        request: Invocation request
        
    Returns:
        Initialized WorkflowGraphState
    """
    log_agent_action(
        agent_name="workflow_executor",
        action="creating_initial_state",
        details={"project_id": str(request.project_id)}
    )
    
    # Create initial state with required fields
    initial_state = WorkflowGraphState(
        workflow_execution_id=None,  # Set in initialize node
        project_id=request.project_id,
        user_id=request.user_id,
        session_id=request.session_id,
        current_agent=None,
        current_status=WorkflowExecutionStatus.OPEN.value,
        agent_tasks=[],
        completed_tasks=[],
        failed_tasks=[],
        task_outputs={},
        shared_context={},
        awaiting_user_feedback=False,
        user_feedback=None,
        feedback_intent="proceed",
        content_edits=[],
        user_feedback_history=[],
        last_user_message=None,
        supervisor_decisions=[],
        created_artifacts=[],
        artifact_export_locations={},
        errors=[],
        retry_count=0,
        started_at=datetime.utcnow(),
        last_updated_at=datetime.utcnow(),
        workflow_config={}
    )
    
    return initial_state


async def _load_and_update_state(
    request: InvocationRequest,
    context: RequestContext
) -> WorkflowGraphState:
    """
    Load existing state from AgentCore Memory and update with user input.
    
    Uses RequestContext.session_id for state persistence across invocations,
    enabling proper workflow resumption and multi-turn interactions.
    
    Args:
        request: Invocation request with session_id
        context: RequestContext from AgentCore
        
    Returns:
        Updated WorkflowGraphState ready for resumption
        
    Raises:
        AgentError: If state not found in memory
    """
    log_agent_action(
        agent_name="workflow_executor",
        action="loading_state_from_memory",
        details={
            "session_id": request.session_id,
            "context_session_id": context.session_id,
            "user_id": str(request.user_id)
        }
    )
    
    try:
        # Load state from AgentCore Memory system
        # Note: Strands Graph doesn't have get_state() - we use memory_manager
        from core.memory import get_memory_manager
        
        memory_manager = get_memory_manager()
        
        # Retrieve workflow state from memory
        memory_key = f"workflow_state_{request.session_id}"
        state_data = await memory_manager.get(
            key=memory_key,
            user_id=str(request.user_id)
        )
        
        if not state_data:
            raise AgentError(
                error_code=ErrorCode.WORKFLOW_STATE_INVALID,
                message=f"No workflow found for session_id: {request.session_id}",
                severity=ErrorSeverity.MEDIUM
            )
        
        # Deserialize state from memory
        import json
        state_dict = json.loads(state_data) if isinstance(state_data, str) else state_data
        state = WorkflowGraphState(**state_dict)
        
        log_agent_action(
            agent_name="workflow_executor",
            action="state_loaded",
            details={
                "workflow_id": str(state.workflow_execution_id),
                "current_agent": state.current_agent,
                "completed_tasks": len(state.completed_tasks),
                "source": "checkpoint"
            }
        )
        
        # Update state with user input
        if request.user_input:
            if request.user_input.chat:
                state.user_feedback = request.user_input.chat
                state.last_user_message = request.user_input.chat
                state.feedback_intent = _analyze_feedback_intent(request.user_input.chat)
            
            if request.user_input.content_edits:
                state.content_edits = request.user_input.content_edits
            
            # Clear awaiting flag so graph resumes
            state.awaiting_user_feedback = False
            state.last_updated_at = datetime.utcnow()
            
            log_agent_action(
                agent_name="workflow_executor",
                action="state_updated_with_feedback",
                details={
                    "workflow_id": str(state.workflow_execution_id),
                    "feedback_intent": state.feedback_intent,
                    "has_edits": len(state.content_edits) > 0
                }
            )
        
        return state
        
    except AgentError:
        raise
    except Exception as e:
        log_agent_action(
            agent_name="workflow_executor",
            action="state_load_failed",
            details={"error": str(e)},
            level="error"
        )
        raise AgentError(
            error_code=ErrorCode.WORKFLOW_STATE_INVALID,
            message=f"Failed to load workflow state: {str(e)}",
            severity=ErrorSeverity.HIGH
        )


def _analyze_feedback_intent(feedback: str) -> str:
    """
    Analyze user feedback to determine intent.
    
    Intent classification:
    - "reparse": Issues with document parsing
    - "reanalyze": Issues with analysis
    - "proceed": User approved, continue
    
    Args:
        feedback: User feedback text
        
    Returns:
        Intent string
    """
    feedback_lower = feedback.lower()
    
    # Check for reparse keywords
    reparse_keywords = ["reparse", "re-parse", "parse again", "parsing", "document issue"]
    if any(keyword in feedback_lower for keyword in reparse_keywords):
        return "reparse"
    
    # Check for reanalyze keywords
    reanalyze_keywords = ["reanalyze", "re-analyze", "analyze again", "analysis issue", "wrong analysis"]
    if any(keyword in feedback_lower for keyword in reanalyze_keywords):
        return "reanalyze"
    
    # Default to proceed
    return "proceed"


def _get_status_message(state: WorkflowGraphState) -> str:
    """
    Get human-readable status message based on workflow state.
    
    Args:
        state: Workflow graph state
        
    Returns:
        Status message
    """
    if state.awaiting_user_feedback:
        return "Workflow paused - awaiting user feedback"
    elif state.current_status == WorkflowExecutionStatus.COMPLETED.value:
        return "Workflow completed successfully"
    elif state.current_status == WorkflowExecutionStatus.FAILED.value:
        return f"Workflow failed: {state.errors[-1] if state.errors else 'Unknown error'}"
    else:
        return f"Workflow in progress - current agent: {state.current_agent or 'initializing'}"


# ========================================
# Signal Handlers
# ========================================

def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    log_agent_action(
        agent_name="workflow_executor",
        action="shutdown_signal_received",
        details={"signal": signum}
    )
    sys.exit(0)


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


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
        port=config.workflow_agent_port,
        log_level="info",
        access_log=True
    )