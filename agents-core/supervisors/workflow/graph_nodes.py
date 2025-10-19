"""
Workflow Graph Node Implementations - Refactored for OOP Agent Pattern

Individual node functions for the Workflow Supervisor StateGraph.
Each node receives WorkflowGraphState, executes agent via Strands invocation, and returns updated state.

CRITICAL: Agents are OOP class instances that expose Strands Agent via get_agent().
They are invoked via agent_instance.get_agent().ainvoke(), following proper OOP patterns.

Node Types:
- Initialization: Setup workflow and tasks
- Agent Execution: Invoke Strands agents (Parser, Analysis, Content, etc.)
- User Interaction: Await and process feedback
- Completion: Finalize workflow

All nodes emit SSE events and update database records.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from core.database import db_pool
from core.sse_manager import get_sse_manager
from core.error_handling import AgentError, ErrorCode, ErrorSeverity
from core.observability import log_agent_action
from core.memory import get_memory_manager
from models.workflow_models import WorkflowExecutionStatus
from models.sse_models import (
    WorkflowCreated,
    AgentHandoff,
    AwaitingFeedback,
    WorkflowStatusUpdate,
    WorkflowCompleted
)
from tools.database.db_tools import (
    create_workflow_execution,
    create_agent_task,
    update_workflow_execution,
    update_agent_task,
    get_next_incomplete_task,
    update_project,
    reset_agent_tasks
)
from tools.storage.artifact_export import ArtifactExporter

# Import OOP agent classes (not factory functions)
from agents import (
    ParserAgent,
    AnalysisAgent,
    ContentAgent,
    ComplianceAgent,
    QAAgent,
    CommsAgent,
    SubmissionAgent
)

from supervisors.workflow.state_models import WorkflowGraphState


# Module-level manager instances (initialized once)
_sse_manager = None
_agent_name = "workflow_supervisor"


def _get_sse_manager():
    """Get SSE manager instance"""
    global _sse_manager
    if _sse_manager is None:
        _sse_manager = get_sse_manager()
    return _sse_manager


def _extract_agent_output(agent_result: Any) -> Dict[str, Any]:
    """
    Extract structured output from Strands Agent result.
    
    Strands agents return AIMessage objects. We need to extract the
    actual content/output from the message.
    
    Args:
        agent_result: Raw result from agent.ainvoke()
        
    Returns:
        Structured dictionary with agent output
    """
    # Check if result has messages (typical Strands response)
    if hasattr(agent_result, "messages") and agent_result.messages:
        last_message = agent_result.messages[-1]
        content = last_message.content if hasattr(last_message, "content") else str(last_message)
    elif hasattr(agent_result, "content"):
        content = agent_result.content
    else:
        content = str(agent_result)
    
    # Try to parse as JSON if structured output was used
    try:
        if isinstance(content, str):
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else {"output": parsed}
        return {"output": content}
    except (json.JSONDecodeError, TypeError):
        return {"output": content}


def _create_agent_with_memory(
    agent_class,
    agent_name: str,
    state: WorkflowGraphState,
    mode: str = "workflow",
    provider: str = "bedrock"
):
    """
    Create agent instance with AgentCore Memory integration.
    
    This helper function creates an agent instance and configures it with
    appropriate memory based on the workflow context. Memory enables agents
    to maintain context across invocations and learn from past interactions.
    
    Memory Types Configured:
    - Workflow Memory: Session-based context for this execution
    - Project Memory: Project artifacts and document history
    - User Preference Memory: User feedback patterns
    - Agent Learning Memory: Agent-specific performance insights
    
    Args:
        agent_class: Agent class to instantiate (ParserAgent, AnalysisAgent, etc.)
        agent_name: Name of the agent (for logging and memory config)
        state: Current workflow state (contains project_id, user_id, session_id)
        mode: Agent mode (default: "workflow")
        provider: LLM provider (default: "bedrock")
        
    Returns:
        Agent instance configured with memory
        
    Example:
        ```python
        parser = _create_agent_with_memory(
            agent_class=ParserAgent,
            agent_name="parser",
            state=state
        )
        ```
    """
    # Create base agent instance
    agent = agent_class(mode=mode, provider=provider)
    
    # Get memory manager
    memory_manager = get_memory_manager()
    
    # Check if memory is enabled
    if not memory_manager.is_memory_enabled():
        log_agent_action(
            agent_name=_agent_name,
            action="agent_created_without_memory",
            details={
                "agent_name": agent_name,
                "reason": "Memory service not available"
            },
            level="warning"
        )
        return agent
    
    try:
        # Create workflow memory configuration (session-scoped)
        memory_config = memory_manager.create_workflow_memory_config(
            project_id=str(state.project_id),
            session_id=state.session_id,
            ttl_hours=24  # Workflow memory expires after 24 hours
        )
        
        # Configure agent with memory using fluent interface
        agent_with_memory = agent.with_memory(
            memory_config=memory_config,
            session_id=state.session_id,
            user_id=str(state.user_id)
        )
        
        log_agent_action(
            agent_name=_agent_name,
            action="agent_created_with_memory",
            details={
                "agent_name": agent_name,
                "memory_id": memory_config.memory_id,
                "memory_scope": memory_config.scope.value,
                "workflow_id": str(state.workflow_execution_id)
            }
        )
        
        return agent_with_memory
        
    except Exception as memory_error:
        log_agent_action(
            agent_name=_agent_name,
            action="agent_memory_config_failed",
            details={
                "agent_name": agent_name,
                "error": str(memory_error)
            },
            level="warning"
        )
        # Return agent without memory as fallback
        return agent


async def _invoke_agent_with_context(
    agent_instance,
    agent_name: str,
    state: WorkflowGraphState,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Invoke a Strands agent with proper context structure.
    
    OOP Pattern: Takes agent instance (ParserAgent, AnalysisAgent, etc.),
    calls get_agent() to get Strands Agent, then invokes.
    
    Strands agents expect input in the format:
    {
        "messages": [...],  # Conversation history
        "context": {...}    # Additional context data
    }
    
    Args:
        agent_instance: OOP agent instance (e.g., ParserAgent, AnalysisAgent)
        agent_name: Name of the agent (for logging)
        state: Current workflow state
        context: Additional context from previous agents
        
    Returns:
        Extracted agent output as dictionary
    """
    # Prepare input for Strands agent
    input_data = {
        "messages": [
            {
                "role": "system",
                "content": f"Execute {agent_name} task for workflow {state.workflow_execution_id}"
            },
            {
                "role": "user",
                "content": f"Process task for project {state.project_id}"
            }
        ],
        "context": {
            "workflow_execution_id": str(state.workflow_execution_id),
            "project_id": str(state.project_id),
            "user_id": str(state.user_id),
            "session_id": state.session_id,
            "previous_outputs": state.task_outputs,
            **(context or {})
        }
    }
    
    log_agent_action(
        agent_name=_agent_name,
        action=f"invoking_{agent_name}_agent",
        details={
            "workflow_id": str(state.workflow_execution_id),
            "has_context": context is not None
        }
    )
    
    # Get Strands Agent from OOP instance and invoke
    strands_agent = agent_instance.get_agent()
    result = await strands_agent.ainvoke(input_data)
    
    # Extract structured output
    output = _extract_agent_output(result)
    
    log_agent_action(
        agent_name=_agent_name,
        action=f"{agent_name}_agent_completed",
        details={
            "workflow_id": str(state.workflow_execution_id),
            "output_keys": list(output.keys())
        }
    )
    
    return output


# ========================================
# Supervisor Orchestrator Node
# ========================================

async def supervisor_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    AGENT-DRIVEN Supervisor orchestrator node using structured outputs.
    
    **CRITICAL DESIGN CHANGE**: This supervisor is now AGENT-DRIVEN, not hardcoded.
    The supervisor agent uses database tools and structured outputs (Pydantic models)
    to make intelligent routing decisions based on workflow state.
    
    Flow:
    1. Check if workflow initialized (workflow_execution_id exists)
    2. If not initialized → route to "initialize"
    3. If initialized → create WorkflowSupervisor agent instance
    4. Agent queries DB using tools (get_next_incomplete_task, get_workflow_execution, etc.)
    5. Agent analyzes state and returns AgentRoutingDecision (structured output)
    6. Execute the decision (route to agent, reset tasks, await feedback, etc.)
    7. Emit SSE events based on decision
    
    Args:
        state: Current workflow graph state
        
    Returns:
        Updated state with routing decision executed
    """
    log_agent_action(
        agent_name=_agent_name,
        action="supervisor_analyzing_workflow_state",
        details={
            "workflow_id": str(state.workflow_execution_id) if state.workflow_execution_id else "not_initialized",
            "project_id": str(state.project_id),
            "user_id": str(state.user_id),
            "completed_tasks": state.completed_tasks,
            "failed_tasks": state.failed_tasks
        }
    )
    
    # Step 1: Check if workflow needs initialization
    if not state.workflow_execution_id:
        next_node = "initialize"
        reason = "Workflow not initialized - creating WorkflowExecution and AgentTasks in DB"
        
        state.task_outputs["supervisor"] = {
            "next_node": next_node,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
            "agent_driven": False  # This is hardcoded routing for initialization
        }
        
        log_agent_action(
            agent_name=_agent_name,
            action="supervisor_decision_initialize",
            details={"next_node": next_node, "reason": reason}
        )
        
        return state
    
    # Step 2: Create WorkflowSupervisor agent instance (OOP pattern)
    try:
        from agents import WorkflowSupervisor
        from models.supervisor_models import AgentRoutingDecision
        
        supervisor = WorkflowSupervisor()
        strands_agent = supervisor.get_agent()
        
        # Step 3: Prepare context for agent decision-making
        # The agent will use this context + database tools to make decisions
        decision_context = {
            "workflow_execution_id": str(state.workflow_execution_id),
            "project_id": str(state.project_id),
            "user_id": str(state.user_id),
            "session_id": state.session_id,
            "completed_tasks": state.completed_tasks,
            "failed_tasks": state.failed_tasks,
            "awaiting_user_feedback": state.awaiting_user_feedback,
            "last_user_message": state.last_user_message,
            "user_feedback": state.user_feedback,
            "content_edits": state.content_edits,
            "task_outputs": {
                "compliance": state.task_outputs.get("compliance", {}),
                "qa": state.task_outputs.get("qa", {}),
                "analysis": state.task_outputs.get("analysis", {})
            }
        }
        
        # Step 4: Construct prompt for agent
        # The system prompt already instructs the agent to use structured output
        decision_prompt = f"""
You are the Workflow Supervisor for project {state.project_id}.

Current Workflow State:
- Workflow Execution ID: {state.workflow_execution_id}
- Completed Tasks: {', '.join(state.completed_tasks) if state.completed_tasks else 'None'}
- Failed Tasks: {', '.join(state.failed_tasks) if state.failed_tasks else 'None'}
- Awaiting User Feedback: {state.awaiting_user_feedback}
- User Feedback: {state.user_feedback if state.user_feedback else 'None'}
- Last User Message: {state.last_user_message if state.last_user_message else 'None'}

Your Task:
1. Use database tools to query the current state (get_next_incomplete_task, get_workflow_execution)
2. Analyze the workflow progress and determine the next action
3. Return your routing decision as AgentRoutingDecision

Remember:
- Query the database BEFORE making decisions
- Consider validation results from Compliance and QA agents
- Handle user feedback appropriately (reparse, reanalyze, proceed)
- Emit appropriate SSE events for frontend updates
- Use RESET_TASKS decision type when validation fails
"""
        
        # Step 5: Invoke agent with structured output
        # NOTE: Strands Agent's structured_output method will be called internally
        # via model binding. For now, we'll invoke normally and parse the output.
        input_data = {
            "messages": [
                {"role": "user", "content": decision_prompt}
            ],
            "context": decision_context
        }
        
        log_agent_action(
            agent_name=_agent_name,
            action="invoking_supervisor_agent",
            details={"workflow_id": str(state.workflow_execution_id)}
        )
        
        result = await strands_agent.ainvoke(input_data)
        
        # Step 6: Extract AgentRoutingDecision from result
        # The agent should return structured output following AgentRoutingDecision model
        decision_data = _extract_agent_output(result)
        
        # Validate and parse as AgentRoutingDecision
        try:
            decision = AgentRoutingDecision(**decision_data)
        except Exception as parse_error:
            log_agent_action(
                agent_name=_agent_name,
                action="supervisor_decision_parse_error",
                details={
                    "error": str(parse_error),
                    "raw_output": decision_data
                },
                level="error"
            )
            # Fallback to safe completion
            decision = AgentRoutingDecision(
                decision_type="COMPLETE_WORKFLOW",
                reasoning=f"Failed to parse agent decision: {str(parse_error)}",
                next_agent=None,
                requires_user_input=False,
                confidence=0.5,
                sse_events_to_emit=[{
                    "event_type": "workflow_error",
                    "message": "Supervisor decision parsing failed - completing workflow"
                }]
            )
        
        log_agent_action(
            agent_name=_agent_name,
            action="supervisor_decision_received",
            details={
                "decision_type": decision.decision_type,
                "next_agent": decision.next_agent,
                "reasoning": decision.reasoning,
                "confidence": decision.confidence
            }
        )
        
        # Step 7: Execute the decision based on decision_type
        if decision.decision_type == "ROUTE_TO_AGENT":
            # Route to next agent
            next_node = decision.next_agent
            state.current_agent = decision.next_agent
            
        elif decision.decision_type == "AWAIT_USER_FEEDBACK":
            # Set awaiting feedback state
            state.awaiting_user_feedback = True
            state.current_status = "WAITING"
            next_node = "await_user_feedback"  # Special node that pauses workflow
            
            # Update workflow in DB
            await update_workflow_execution(
                workflow_execution_id=str(state.workflow_execution_id),
                status="WAITING",
                last_updated_at=datetime.utcnow().isoformat()
            )
            
        elif decision.decision_type == "RESET_TASKS":
            # Reset specified tasks in DB
            if decision.tasks_to_reset:
                await reset_agent_tasks(
                    workflow_execution_id=str(state.workflow_execution_id),
                    agent_names=decision.tasks_to_reset,
                    reset_by=str(state.user_id)
                )
                
                # Remove from completed/failed lists
                for agent_name in decision.tasks_to_reset:
                    if agent_name in state.completed_tasks:
                        state.completed_tasks.remove(agent_name)
                    if agent_name in state.failed_tasks:
                        state.failed_tasks.remove(agent_name)
                    state.task_outputs.pop(agent_name, None)
                
                log_agent_action(
                    agent_name=_agent_name,
                    action="tasks_reset",
                    details={
                        "workflow_id": str(state.workflow_execution_id),
                        "reset_agents": decision.tasks_to_reset,
                        "reason": decision.reasoning
                    }
                )
            
            # Route to restart agent
            next_node = decision.restart_from_agent if decision.restart_from_agent else "supervisor"
            
        elif decision.decision_type == "REQUEST_PERMISSION":
            # Request permission from user
            state.awaiting_user_feedback = True
            state.current_status = "WAITING"
            next_node = "await_permission"  # Special node for permission requests
            
            # Update workflow in DB
            await update_workflow_execution(
                workflow_execution_id=str(state.workflow_execution_id),
                status="WAITING",
                last_updated_at=datetime.utcnow().isoformat()
            )
            
        elif decision.decision_type == "COMPLETE_WORKFLOW":
            # Complete the workflow
            next_node = "complete"
            state.current_status = "COMPLETED"
            
        elif decision.decision_type == "HANDLE_ERROR":
            # Handle error scenario
            log_agent_action(
                agent_name=_agent_name,
                action="supervisor_error_handling",
                details={
                    "error_code": decision.error_code,
                    "error_message": decision.error_message,
                    "error_severity": decision.error_severity
                },
                level="error"
            )
            
            if decision.error_severity == "HIGH":
                # Critical error - complete workflow with failure
                next_node = "complete"
                state.current_status = "FAILED"
                state.errors.append({
                    "code": decision.error_code,
                    "message": decision.error_message,
                    "severity": decision.error_severity,
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                # Recoverable error - retry or proceed
                next_node = decision.next_agent if decision.next_agent else "supervisor"
        
        else:
            # Unknown decision type - fallback to complete
            log_agent_action(
                agent_name=_agent_name,
                action="unknown_decision_type",
                details={"decision_type": decision.decision_type},
                level="warning"
            )
            next_node = "complete"
        
        # Step 8: Store decision in state (for next supervisor iteration)
        state.task_outputs["supervisor"] = {
            "next_node": next_node,
            "decision_type": decision.decision_type,
            "reasoning": decision.reasoning,
            "confidence": decision.confidence,
            "timestamp": datetime.utcnow().isoformat(),
            "agent_driven": True,  # Flag indicating agent-driven decision
            "full_decision": decision.dict()  # Store full decision for debugging
        }
        
        # CRITICAL: Also store next_node in a simple format for conditional edges
        # Strands conditional functions will access this via AgentResult.state
        state.supervisor_next_node = next_node
        
        # Step 9: Emit SSE events
        sse_manager = _get_sse_manager()
        for event_data in decision.sse_events_to_emit:
            try:
                await sse_manager.send_event(
                    session_id=state.session_id,
                    event=WorkflowStatusUpdate(
                        workflow_execution_id=str(state.workflow_execution_id),
                        status=event_data.get("event_type", "update"),
                        message=event_data.get("message", ""),
                        timestamp=datetime.utcnow()
                    )
                )
            except Exception as sse_error:
                log_agent_action(
                    agent_name=_agent_name,
                    action="sse_emit_error",
                    details={"error": str(sse_error)},
                    level="warning"
                )
        
        # Step 10: Update workflow progress if specified
        if decision.update_progress_percentage is not None:
            await update_project(
                project_id=str(state.project_id),
                progress_percentage=decision.update_progress_percentage
            )
        
        log_agent_action(
            agent_name=_agent_name,
            action="supervisor_decision_executed",
            details={
                "next_node": next_node,
                "decision_type": decision.decision_type,
                "workflow_id": str(state.workflow_execution_id)
            }
        )
        
    except Exception as e:
        log_agent_action(
            agent_name=_agent_name,
            action="supervisor_agent_error",
            details={
                "error": str(e),
                "error_type": type(e).__name__,
                "workflow_id": str(state.workflow_execution_id)
            },
            level="error"
        )
        
        # Fallback to safe completion
        next_node = "complete"
        state.task_outputs["supervisor"] = {
            "next_node": next_node,
            "reason": f"Supervisor agent error: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_driven": False,
            "error": str(e)
        }
    
    return state


# ========================================
# Initialization Node
# ========================================

async def initialize_workflow_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Initialize workflow execution and create task records.
    
    Creates:
    - WorkflowExecution database record
    - AgentTask records for each agent in sequence
    - Emits workflow_created SSE event
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with workflow_execution_id set
    """
    log_agent_action(
        agent_name=_agent_name,
        action="initialize_workflow",
        details={"project_id": str(state.project_id)}
    )
    
    # Create workflow execution record
    workflow_execution = await create_workflow_execution(
        project_id=str(state.project_id),
        session_id=state.session_id,
        initiated_by=str(state.user_id),
        workflow_config={"mode": "workflow", "session_id": state.session_id}
    )
    
    workflow_id = UUID(workflow_execution["id"])
    
    # Create agent tasks in sequence
    agent_sequence = [
        ("parser", 1),
        ("analysis", 2),
        ("content", 3),
        ("compliance", 4),
        ("qa", 5),
        ("comms", 6),
        ("submission", 7),
    ]
    
    for agent_name, sequence in agent_sequence:
        await create_agent_task(
            workflow_execution_id=str(workflow_id),
            agent=agent_name,
            sequence_order=sequence,
            initiated_by=str(state.user_id)
        )
    
    # Send workflow created event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=WorkflowCreated(
            workflow_execution_id=str(workflow_id),
            project_id=str(state.project_id),
            total_tasks=len(agent_sequence),
            timestamp=datetime.utcnow()
        )
    )
    
    # Update state
    state.workflow_execution_id = workflow_id
    state.current_status = WorkflowExecutionStatus.IN_PROGRESS.value
    state.last_updated_at = datetime.utcnow()
    
    log_agent_action(
        agent_name=_agent_name,
        action="workflow_initialized",
        details={
            "workflow_id": str(workflow_id),
            "tasks_created": len(agent_sequence)
        }
    )
    
    return state


# ========================================
# Agent Execution Nodes (OOP Pattern)
# ========================================

async def parser_agent_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Execute Parser Agent node via OOP class instantiation.
    
    Parses uploaded project documents using Bedrock Data Automation.
    Updates ProjectDocument records with processed_file_location.
    
    **STRUCTURED OUTPUT**: This node expects ParserOutput from the agent.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with parser output
    """
    from models import ParserOutput
    
    # Get parser task
    task = await get_next_incomplete_task(
        workflow_execution_id=str(state.workflow_execution_id),
        agent="parser"
    )
    
    if not task:
        raise AgentError(
            code=ErrorCode.AGENT_NO_DATA_FOUND,
            message="Parser task not found",
            severity=ErrorSeverity.HIGH
        )
    
    task_id = UUID(task["id"])
    
    # Update task to in progress
    await update_agent_task(
        task_id=str(task_id),
        status="IN_PROGRESS",
        started_at=datetime.utcnow().isoformat(),
        handled_by=str(state.user_id)
    )
    
    # Send handoff event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=AgentHandoff(
            from_agent="supervisor",
            to_agent="parser",
            agent_task_id=str(task_id),
            timestamp=datetime.utcnow()
        )
    )
    
    try:
        # Create Parser agent with memory (OOP + Memory integration)
        parser = _create_agent_with_memory(
            agent_class=ParserAgent,
            agent_name="parser",
            state=state
        )
        
        # Invoke agent via OOP pattern
        raw_output = await _invoke_agent_with_context(
            agent_instance=parser,
            agent_name="parser",
            state=state,
            context={}
        )
        
        # Parse and validate structured output
        try:
            parser_output = ParserOutput(**raw_output)
            output = parser_output.dict()
            
            log_agent_action(
                agent_name=_agent_name,
                action="parser_structured_output_validated",
                details={
                    "workflow_id": str(state.workflow_execution_id),
                    "documents_processed": parser_output.documents_processed,
                    "documents_failed": parser_output.documents_failed,
                    "status": parser_output.status
                }
            )
        except Exception as parse_error:
            log_agent_action(
                agent_name=_agent_name,
                action="parser_output_validation_failed",
                details={
                    "error": str(parse_error),
                    "raw_output_keys": list(raw_output.keys()) if isinstance(raw_output, dict) else "not_a_dict"
                },
                level="error"
            )
            # Use raw output as fallback
            output = raw_output
        
        # Update task as completed
        await update_agent_task(
            task_id=str(task_id),
            status="COMPLETED",
            output_data=output,
            completed_at=datetime.utcnow().isoformat(),
            completed_by=str(state.user_id)
        )
        
        # Update state
        state.task_outputs["parser"] = output
        state.completed_tasks.append("parser")
        state.current_agent = "parser"
        
        # Update workflow
        await update_workflow_execution(
            workflow_execution_id=str(state.workflow_execution_id)
        )
        
        # Update project progress (10% after parsing)
        await update_project(
            project_id=str(state.project_id),
            progress_percentage=10
        )
        
    except Exception as e:
        # Update task as failed
        await update_agent_task(
            task_id=str(task_id),
            status="FAILED",
            error_message=str(e),
            error_log=[{"error": str(e), "type": type(e).__name__}]
        )
        raise
    
    return state


async def analysis_agent_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Execute Analysis Agent node via OOP class instantiation.
    
    Analyzes RFP requirements, extracts client info, identifies deliverables.
    Generates markdown analysis report for user review.
    
    **STRUCTURED OUTPUT**: This node expects AnalysisOutput from the agent.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with analysis output
    """
    from models.llm_output_models import AnalysisOutput
    
    # Get analysis task
    task = await get_next_incomplete_task(
        workflow_execution_id=str(state.workflow_execution_id),
        agent="analysis"
    )
    
    if not task:
        raise AgentError(
            code=ErrorCode.AGENT_NO_DATA_FOUND,
            message="Analysis task not found",
            severity=ErrorSeverity.HIGH
        )
    
    task_id = UUID(task["id"])
    
    # Update task to in progress
    await update_agent_task(
        agent_task_id=task_id,
        status="IN_PROGRESS",
        started_at=datetime.utcnow(),
        handled_by=str(state.user_id)
    )
    
    # Send handoff event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=AgentHandoff(
            from_agent="parser",
            to_agent="analysis",
            agent_task_id=str(task_id),
            timestamp=datetime.utcnow()
        )
    )
    
    try:
        # Create Analysis agent with memory (OOP + Memory integration)
        analysis = _create_agent_with_memory(
            agent_class=AnalysisAgent,
            agent_name="analysis",
            state=state
        )
        
        # Pass parser output in context
        parser_output = state.task_outputs.get("parser", {})
        context = {"parser_output": parser_output}
        
        # Invoke agent via OOP pattern
        raw_output = await _invoke_agent_with_context(
            agent_instance=analysis,
            agent_name="analysis",
            state=state,
            context=context
        )
        
        # Parse and validate structured output
        try:
            analysis_output = AnalysisOutput(**raw_output)
            output = analysis_output.dict()
            
            log_agent_action(
                agent_name=_agent_name,
                action="analysis_structured_output_validated",
                details={
                    "workflow_id": str(state.workflow_execution_id),
                    "client_name": analysis_output.client_info.name if analysis_output.client_info else "N/A",
                    "deliverables_count": len(analysis_output.deliverables),
                    "deadline": str(analysis_output.deadline) if analysis_output.deadline else "N/A"
                }
            )
        except Exception as parse_error:
            log_agent_action(
                agent_name=_agent_name,
                action="analysis_output_validation_failed",
                details={
                    "error": str(parse_error),
                    "raw_output_keys": list(raw_output.keys()) if isinstance(raw_output, dict) else "not_a_dict"
                },
                level="error"
            )
            # Use raw output as fallback
            output = raw_output
        
        # Update task as completed
        await update_agent_task(
            agent_task_id=task_id,
            status="COMPLETED",
            output_data=output,
            completed_at=datetime.utcnow().isoformat(),
            completed_by=str(state.user_id)
        )
        
        # Update state
        state.task_outputs["analysis"] = output
        state.completed_tasks.append("analysis")
        state.current_agent = "analysis"
        
        # Update workflow
        await update_workflow_execution(
            workflow_execution_id=state.workflow_execution_id,
            last_updated_at=datetime.utcnow().isoformat()
        )
        
        # Update project progress (20% after analysis)
        await update_project(
            project_id=state.project_id,
            progress_percentage=20,
            updated_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        # Update task as failed
        await update_agent_task(
            agent_task_id=task_id,
            status="FAILED",
            error_message=str(e),
            error_log={"error": str(e), "type": type(e).__name__}
        )
        raise
    
    return state


async def content_agent_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Execute Content Agent node via OOP class instantiation.
    
    Generates bid artifacts (documents, Q&A, spreadsheets) using Knowledge Agent.
    Creates Artifact and ArtifactVersion database records.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with content output
    """
    # Get content task
    task = await get_next_incomplete_task(
        workflow_execution_id=str(state.workflow_execution_id),
        agent="content"
    )
    
    if not task:
        raise AgentError(
            code=ErrorCode.AGENT_NO_DATA_FOUND,
            message="Content task not found",
            severity=ErrorSeverity.HIGH
        )
    
    task_id = UUID(task["id"])
    
    # Update task to in progress
    await update_agent_task(
        agent_task_id=task_id,
        status="IN_PROGRESS",
        started_at=datetime.utcnow(),
        handled_by=str(state.user_id)
    )
    
    # Send handoff event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=AgentHandoff(
            from_agent="analysis",
            to_agent="content",
            agent_task_id=str(task_id),
            timestamp=datetime.utcnow()
        )
    )
    
    try:
        # Create Content agent with memory (OOP + Memory integration)
        # Note: ContentAgent has KnowledgeAgent via Composition
        content = _create_agent_with_memory(
            agent_class=ContentAgent,
            agent_name="content",
            state=state
        )
        
        # Pass analysis output and any compliance/QA feedback in context
        context = {
            "analysis_output": state.task_outputs.get("analysis", {}),
            "compliance_feedback": state.task_outputs.get("compliance", {}),
            "qa_feedback": state.task_outputs.get("qa", {}),
            "user_edits": state.content_edits
        }
        
        # Invoke agent via OOP pattern
        output = await _invoke_agent_with_context(
            agent_instance=content,
            agent_name="content",
            state=state,
            context=context
        )
        
        # Update task as completed
        await update_agent_task(
            agent_task_id=task_id,
            status="COMPLETED",
            output_data=output,
            completed_at=datetime.utcnow().isoformat(),
            completed_by=str(state.user_id)
        )
        
        # Update state
        state.task_outputs["content"] = output
        state.completed_tasks.append("content")
        state.current_agent = "content"
        
        # Update workflow
        await update_workflow_execution(
            workflow_execution_id=state.workflow_execution_id,
            last_updated_at=datetime.utcnow().isoformat()
        )
        
        # Update project progress (40% after content)
        await update_project(
            project_id=state.project_id,
            progress_percentage=40,
            updated_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        # Update task as failed
        await update_agent_task(
            agent_task_id=task_id,
            status="FAILED",
            error_message=str(e),
            error_log={"error": str(e), "type": type(e).__name__}
        )
        raise
    
    return state


async def compliance_agent_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Execute Compliance Agent node via OOP class instantiation.
    
    Validates artifacts against Deloitte standards and compliance requirements.
    Provides feedback for non-compliant content.
    
    **STRUCTURED OUTPUT**: This node expects ComplianceCheckOutput from the agent.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with compliance output
    """
    from models.llm_output_models import ComplianceCheckOutput
    
    # Get compliance task
    task = await get_next_incomplete_task(
        workflow_execution_id=str(state.workflow_execution_id),
        agent="compliance"
    )
    
    if not task:
        raise AgentError(
            code=ErrorCode.AGENT_NO_DATA_FOUND,
            message="Compliance task not found",
            severity=ErrorSeverity.HIGH
        )
    
    task_id = UUID(task["id"])
    
    # Update task to in progress
    await update_agent_task(
        agent_task_id=task_id,
        status="IN_PROGRESS",
        started_at=datetime.utcnow(),
        handled_by=str(state.user_id)
    )
    
    # Send handoff event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=AgentHandoff(
            from_agent="content",
            to_agent="compliance",
            agent_task_id=str(task_id),
            timestamp=datetime.utcnow()
        )
    )
    
    try:
        # Create Compliance agent with memory (OOP + Memory integration)
        compliance = _create_agent_with_memory(
            agent_class=ComplianceAgent,
            agent_name="compliance",
            state=state
        )
        
        # Pass content output in context
        context = {"content_output": state.task_outputs.get("content", {})}
        
        # Invoke agent via OOP pattern
        raw_output = await _invoke_agent_with_context(
            agent_instance=compliance,
            agent_name="compliance",
            state=state,
            context=context
        )
        
        # Parse and validate structured output
        try:
            compliance_output = ComplianceCheckOutput(**raw_output)
            output = compliance_output.dict()
            
            log_agent_action(
                agent_name=_agent_name,
                action="compliance_structured_output_validated",
                details={
                    "workflow_id": str(state.workflow_execution_id),
                    "artifacts_reviewed": len(compliance_output.artifact_feedback),
                    "compliant": compliance_output.compliant,
                    "total_issues": sum(len(af.issues) for af in compliance_output.artifact_feedback)
                }
            )
        except Exception as parse_error:
            log_agent_action(
                agent_name=_agent_name,
                action="compliance_output_validation_failed",
                details={
                    "error": str(parse_error),
                    "raw_output_keys": list(raw_output.keys()) if isinstance(raw_output, dict) else "not_a_dict"
                },
                level="error"
            )
            # Use raw output as fallback
            output = raw_output
        
        # Update task as completed
        await update_agent_task(
            agent_task_id=task_id,
            status="COMPLETED",
            output_data=output,
            completed_at=datetime.utcnow().isoformat(),
            completed_by=str(state.user_id)
        )
        
        # Update state
        state.task_outputs["compliance"] = output
        state.completed_tasks.append("compliance")
        state.current_agent = "compliance"
        
        # Update workflow
        await update_workflow_execution(
            workflow_execution_id=state.workflow_execution_id,
            last_updated_at=datetime.utcnow().isoformat()
        )
        
        # Update project progress (60% after compliance)
        await update_project(
            project_id=state.project_id,
            progress_percentage=60,
            updated_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        # Update task as failed
        await update_agent_task(
            agent_task_id=task_id,
            status="FAILED",
            error_message=str(e),
            error_log={"error": str(e), "type": type(e).__name__}
        )
        raise
    
    return state


async def qa_agent_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Execute QA Agent node via OOP class instantiation.
    
    Performs quality assurance checks on artifacts.
    Identifies gaps, missing content, or quality issues.
    
    **STRUCTURED OUTPUT**: This node expects QACheckOutput from the agent.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with QA output
    """
    from models.llm_output_models import QACheckOutput
    
    # Get QA task
    task = await get_next_incomplete_task(
        workflow_execution_id=str(state.workflow_execution_id),
        agent="qa"
    )
    
    if not task:
        raise AgentError(
            code=ErrorCode.AGENT_NO_DATA_FOUND,
            message="QA task not found",
            severity=ErrorSeverity.HIGH
        )
    
    task_id = UUID(task["id"])
    
    # Update task to in progress
    await update_agent_task(
        agent_task_id=task_id,
        status="IN_PROGRESS",
        started_at=datetime.utcnow(),
        handled_by=str(state.user_id)
    )
    
    # Send handoff event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=AgentHandoff(
            from_agent="compliance",
            to_agent="qa",
            agent_task_id=str(task_id),
            timestamp=datetime.utcnow()
        )
    )
    
    try:
        # Create QA agent with memory (OOP + Memory integration)
        qa = _create_agent_with_memory(
            agent_class=QAAgent,
            agent_name="qa",
            state=state
        )
        
        # Pass content and analysis outputs in context
        context = {
            "content_output": state.task_outputs.get("content", {}),
            "analysis_output": state.task_outputs.get("analysis", {})
        }
        
        # Invoke agent via OOP pattern
        raw_output = await _invoke_agent_with_context(
            agent_instance=qa,
            agent_name="qa",
            state=state,
            context=context
        )
        
        # Parse and validate structured output
        try:
            qa_output = QACheckOutput(**raw_output)
            output = qa_output.dict()
            
            log_agent_action(
                agent_name=_agent_name,
                action="qa_structured_output_validated",
                details={
                    "workflow_id": str(state.workflow_execution_id),
                    "artifacts_reviewed": qa_output.summary.total_artifacts_submitted,
                    "missing_artifacts": len(qa_output.missing_artifacts),
                    "total_issues": qa_output.summary.total_issues_found,
                    "overall_status": qa_output.summary.overall_status
                }
            )
        except Exception as parse_error:
            log_agent_action(
                agent_name=_agent_name,
                action="qa_output_validation_failed",
                details={
                    "error": str(parse_error),
                    "raw_output_keys": list(raw_output.keys()) if isinstance(raw_output, dict) else "not_a_dict"
                },
                level="error"
            )
            # Use raw output as fallback
            output = raw_output
        
        # Update task as completed
        await update_agent_task(
            agent_task_id=task_id,
            status="COMPLETED",
            output_data=output,
            completed_at=datetime.utcnow().isoformat(),
            completed_by=str(state.user_id)
        )
        
        # Update state
        state.task_outputs["qa"] = output
        state.completed_tasks.append("qa")
        state.current_agent = "qa"
        
        # Update workflow
        await update_workflow_execution(
            workflow_execution_id=state.workflow_execution_id,
            last_updated_at=datetime.utcnow().isoformat()
        )
        
        # Update project progress (70% after QA)
        await update_project(
            project_id=state.project_id,
            progress_percentage=70,
            updated_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        # Update task as failed
        await update_agent_task(
            agent_task_id=task_id,
            status="FAILED",
            error_message=str(e),
            error_log={"error": str(e), "type": type(e).__name__}
        )
        raise
    
    return state


async def comms_agent_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Execute Comms Agent node via OOP class instantiation.
    
    Creates Slack channels, sends notifications to project members.
    Creates notification records in database.
    
    **STRUCTURED OUTPUT**: This node expects NotificationPlan from the agent.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with comms output
    """
    from models.llm_output_models import NotificationPlan
    
    # Get comms task
    task = await get_next_incomplete_task(
        workflow_execution_id=str(state.workflow_execution_id),
        agent="comms"
    )
    
    if not task:
        raise AgentError(
            code=ErrorCode.AGENT_NO_DATA_FOUND,
            message="Comms task not found",
            severity=ErrorSeverity.HIGH
        )
    
    task_id = UUID(task["id"])
    
    # Update task to in progress
    await update_agent_task(
        agent_task_id=task_id,
        status="IN_PROGRESS",
        started_at=datetime.utcnow(),
        handled_by=str(state.user_id)
    )
    
    # Send handoff event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=AgentHandoff(
            from_agent="supervisor",
            to_agent="comms",
            agent_task_id=str(task_id),
            timestamp=datetime.utcnow()
        )
    )
    
    try:
        # Create Comms agent with memory (OOP + Memory integration)
        comms = _create_agent_with_memory(
            agent_class=CommsAgent,
            agent_name="comms",
            state=state
        )
        
        # Pass artifact export locations in context
        context = {
            "artifact_locations": state.artifact_export_locations,
            "project_id": str(state.project_id)
        }
        
        # Invoke agent via OOP pattern
        raw_output = await _invoke_agent_with_context(
            agent_instance=comms,
            agent_name="comms",
            state=state,
            context=context
        )
        
        # Parse and validate structured output
        try:
            comms_output = NotificationPlan(**raw_output)
            output = comms_output.dict()
            
            log_agent_action(
                agent_name=_agent_name,
                action="comms_structured_output_validated",
                details={
                    "workflow_id": str(state.workflow_execution_id),
                    "channels": comms_output.channels,
                    "recipients_count": len(comms_output.recipients),
                    "has_slack": comms_output.slack_notification is not None
                }
            )
        except Exception as parse_error:
            log_agent_action(
                agent_name=_agent_name,
                action="comms_output_validation_failed",
                details={
                    "error": str(parse_error),
                    "raw_output_keys": list(raw_output.keys()) if isinstance(raw_output, dict) else "not_a_dict"
                },
                level="error"
            )
            # Use raw output as fallback
            output = raw_output
        
        # Update task as completed
        await update_agent_task(
            agent_task_id=task_id,
            status="COMPLETED",
            output_data=output,
            completed_at=datetime.utcnow().isoformat(),
            completed_by=str(state.user_id)
        )
        
        # Update state
        state.task_outputs["comms"] = output
        state.completed_tasks.append("comms")
        state.current_agent = "comms"
        
        # Update workflow
        await update_workflow_execution(
            workflow_execution_id=state.workflow_execution_id,
            last_updated_at=datetime.utcnow().isoformat()
        )
        
        # Update project progress (90% after comms)
        await update_project(
            project_id=state.project_id,
            progress_percentage=90,
            updated_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        # Update task as failed (but don't fail workflow)
        await update_agent_task(
            agent_task_id=task_id,
            status="FAILED",
            error_message=str(e),
            error_log={"error": str(e), "type": type(e).__name__}
        )
        # Log but continue - comms is not critical
        log_agent_action(
            agent_name=_agent_name,
            action="comms_failed_continuing",
            details={"error": str(e)},
            level="warning"
        )
    
    return state


async def submission_agent_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Execute Submission Agent node via OOP class instantiation.
    
    Generates email draft, sends email with artifacts to client.
    Creates submission record in database.
    
    **STRUCTURED OUTPUT**: This node expects EmailDraft from the agent.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with submission output
    """
    from models.llm_output_models import EmailDraft
    
    # Get submission task
    task = await get_next_incomplete_task(
        workflow_execution_id=str(state.workflow_execution_id),
        agent="submission"
    )
    
    if not task:
        raise AgentError(
            code=ErrorCode.AGENT_NO_DATA_FOUND,
            message="Submission task not found",
            severity=ErrorSeverity.HIGH
        )
    
    task_id = UUID(task["id"])
    
    # Update task to in progress
    await update_agent_task(
        agent_task_id=task_id,
        status="IN_PROGRESS",
        started_at=datetime.utcnow(),
        handled_by=str(state.user_id)
    )
    
    # Send handoff event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=AgentHandoff(
            from_agent="comms",
            to_agent="submission",
            agent_task_id=str(task_id),
            timestamp=datetime.utcnow()
        )
    )
    
    try:
        # Create Submission agent with memory (OOP + Memory integration)
        submission = _create_agent_with_memory(
            agent_class=SubmissionAgent,
            agent_name="submission",
            state=state
        )
        
        # Pass analysis and artifact data in context
        context = {
            "analysis_output": state.task_outputs.get("analysis", {}),
            "artifact_locations": state.artifact_export_locations,
            "project_id": str(state.project_id)
        }
        
        # Invoke agent via OOP pattern
        raw_output = await _invoke_agent_with_context(
            agent_instance=submission,
            agent_name="submission",
            state=state,
            context=context
        )
        
        # Parse and validate structured output
        try:
            submission_output = EmailDraft(**raw_output)
            output = submission_output.dict()
            
            log_agent_action(
                agent_name=_agent_name,
                action="submission_structured_output_validated",
                details={
                    "workflow_id": str(state.workflow_execution_id),
                    "to_recipients": len(submission_output.to),
                    "has_subject": bool(submission_output.subject),
                    "attachments_count": len(submission_output.attachments)
                }
            )
        except Exception as parse_error:
            log_agent_action(
                agent_name=_agent_name,
                action="submission_output_validation_failed",
                details={
                    "error": str(parse_error),
                    "raw_output_keys": list(raw_output.keys()) if isinstance(raw_output, dict) else "not_a_dict"
                },
                level="error"
            )
            # Use raw output as fallback
            output = raw_output
        
        # Update task as completed
        await update_agent_task(
            agent_task_id=task_id,
            status="COMPLETED",
            output_data=output,
            completed_at=datetime.utcnow().isoformat(),
            completed_by=str(state.user_id)
        )
        
        # Update state
        state.task_outputs["submission"] = output
        state.completed_tasks.append("submission")
        state.current_agent = "submission"
        
        # Update workflow
        await update_workflow_execution(
            workflow_execution_id=state.workflow_execution_id,
            last_updated_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        # Update task as failed
        await update_agent_task(
            agent_task_id=task_id,
            status="FAILED",
            error_message=str(e),
            error_log={"error": str(e), "type": type(e).__name__}
        )
        raise
    
    return state


# ========================================
# User Interaction Nodes
# ========================================

async def await_analysis_feedback_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Pause workflow and await user feedback on analysis.
    
    Updates workflow status to WAITING and emits awaiting_feedback SSE event.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with awaiting_feedback=True
    """
    # Update workflow to waiting status
    await update_workflow_execution(
        workflow_execution_id=state.workflow_execution_id,
        status=WorkflowExecutionStatus.WAITING.value,
        last_updated_at=datetime.utcnow().isoformat()
    )
    
    # Send awaiting feedback event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=AwaitingFeedback(
            workflow_execution_id=str(state.workflow_execution_id),
            prompt="Please review the analysis and provide feedback. Type 'approved' to continue, or describe any changes needed.",
            timestamp=datetime.utcnow()
        )
    )
    
    state.awaiting_user_feedback = True
    state.current_status = WorkflowExecutionStatus.WAITING.value
    
    log_agent_action(
        agent_name=_agent_name,
        action="awaiting_analysis_feedback",
        details={"workflow_id": str(state.workflow_execution_id)}
    )
    
    return state


async def await_artifact_review_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Pause workflow and await user review of artifacts.
    
    Updates workflow status to WAITING and emits awaiting_feedback SSE event.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with awaiting_feedback=True
    """
    # Update workflow to waiting status
    await update_workflow_execution(
        workflow_execution_id=state.workflow_execution_id,
        status=WorkflowExecutionStatus.WAITING.value,
        last_updated_at=datetime.utcnow().isoformat()
    )
    
    # Send awaiting feedback event with artifacts
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=AwaitingFeedback(
            workflow_execution_id=str(state.workflow_execution_id),
            prompt="Artifacts are ready for review. Please review and edit if needed. Type 'approved' to continue.",
            timestamp=datetime.utcnow()
        )
    )
    
    state.awaiting_user_feedback = True
    state.current_status = WorkflowExecutionStatus.WAITING.value
    
    log_agent_action(
        agent_name=_agent_name,
        action="awaiting_artifact_review",
        details={"workflow_id": str(state.workflow_execution_id)}
    )
    
    return state


async def await_comms_permission_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Pause workflow and await user permission for communications.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state awaiting comms permission
    """
    # Update workflow to waiting status
    await update_workflow_execution(
        workflow_execution_id=state.workflow_execution_id,
        status=WorkflowExecutionStatus.WAITING.value,
        last_updated_at=datetime.utcnow().isoformat()
    )
    
    # Send awaiting feedback event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=AwaitingFeedback(
            workflow_execution_id=str(state.workflow_execution_id),
            prompt="Send notifications to project stakeholders? (yes/no)",
            timestamp=datetime.utcnow()
        )
    )
    
    state.awaiting_user_feedback = True
    state.current_status = WorkflowExecutionStatus.WAITING.value
    
    return state


async def await_submission_permission_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Pause workflow and await user permission for submission.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state awaiting submission permission
    """
    # Update workflow to waiting status
    await update_workflow_execution(
        workflow_execution_id=state.workflow_execution_id,
        status=WorkflowExecutionStatus.WAITING.value,
        last_updated_at=datetime.utcnow().isoformat()
    )
    
    # Send awaiting feedback event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=AwaitingFeedback(
            workflow_execution_id=str(state.workflow_execution_id),
            prompt="Submit bid to client? (yes/no)",
            timestamp=datetime.utcnow()
        )
    )
    
    state.awaiting_user_feedback = True
    state.current_status = WorkflowExecutionStatus.WAITING.value
    
    return state


# ========================================
# Finalization Nodes
# ========================================

async def export_artifacts_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Export approved artifacts to S3.
    
    Updates ArtifactVersion records with S3 locations.
    Emits export progress SSE events.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with export results
    """
    try:
        log_agent_action(
            agent_name=_agent_name,
            action="exporting_artifacts",
            details={
                "workflow_id": str(state.workflow_execution_id),
                "project_id": str(state.project_id)
            }
        )
        
        # Send export event
        sse_manager = _get_sse_manager()
        await sse_manager.send_event(
            session_id=state.session_id,
            event=WorkflowStatusUpdate(
                workflow_execution_id=str(state.workflow_execution_id),
                status="exporting_artifacts",
                message="Exporting artifacts to S3...",
                timestamp=datetime.utcnow()
            )
        )
        
        # Export artifacts
        export_result = await export_artifacts(
            project_id=state.project_id,
            user_id=state.user_id
        )
        
        # Store export result in state
        state.task_outputs["artifact_export"] = export_result
        
        # Update artifact locations in state
        for artifact_id_str, location in export_result.get("artifact_locations", {}).items():
            artifact_id = UUID(artifact_id_str)
            state.artifact_export_locations[artifact_id] = location
        
        # Send export complete event
        await sse_manager.send_event(
            session_id=state.session_id,
            event=WorkflowStatusUpdate(
                workflow_execution_id=str(state.workflow_execution_id),
                status="artifacts_exported",
                message=f"Successfully exported {export_result['exported_count']} artifacts to S3",
                timestamp=datetime.utcnow()
            )
        )
        
        log_agent_action(
            agent_name=_agent_name,
            action="artifacts_exported",
            details={
                "workflow_id": str(state.workflow_execution_id),
                "exported_count": export_result['exported_count']
            }
        )
        
    except Exception as e:
        log_agent_action(
            agent_name=_agent_name,
            action="artifact_export_failed",
            details={"error": str(e)},
            level="error"
        )
        
        # Send error event
        sse_manager = _get_sse_manager()
        await sse_manager.send_event(
            session_id=state.session_id,
            event=WorkflowStatusUpdate(
                workflow_execution_id=str(state.workflow_execution_id),
                status="export_failed",
                message=f"Failed to export artifacts: {str(e)}",
                timestamp=datetime.utcnow()
            )
        )
        
        raise AgentError(
            code=ErrorCode.TOOL_EXECUTION_FAILED,
            message=f"Failed to export artifacts: {str(e)}",
            severity=ErrorSeverity.HIGH,
            details={"error": str(e)}
        ) from e
    
    return state


async def complete_workflow_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Complete workflow execution.
    
    Updates workflow and project status to COMPLETED.
    Emits workflow_completed SSE event.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with workflow_status=COMPLETED
    """
    # Update workflow status
    await update_workflow_execution(
        workflow_execution_id=state.workflow_execution_id,
        status=WorkflowExecutionStatus.COMPLETED.value,
        completed_by=str(state.user_id),
        completed_at=datetime.utcnow().isoformat(),
        last_updated_at=datetime.utcnow().isoformat()
    )
    
    # Update project status (100% complete)
    await update_project(
        project_id=state.project_id,
        status="COMPLETED",
        progress_percentage=100,
        completed_by=str(state.user_id),
        completed_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat()
    )
    
    # Send completion event
    sse_manager = _get_sse_manager()
    await sse_manager.send_event(
        session_id=state.session_id,
        event=WorkflowCompleted(
            workflow_execution_id=str(state.workflow_execution_id),
            status="completed",
            message="Workflow completed successfully",
            timestamp=datetime.utcnow()
        )
    )
    
    state.current_status = WorkflowExecutionStatus.COMPLETED.value
    
    log_agent_action(
        agent_name=_agent_name,
        action="workflow_completed",
        details={"workflow_id": str(state.workflow_execution_id)}
    )
    
    return state