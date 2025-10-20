# Phase 5: FastAPI Integration Plan

## Overview

Update `agent_executor.py` to properly integrate with the refactored Strands Graph, handling graph initialization, execution, interruptions, and resumption.

## Current State Analysis

### What's Already Good ✅

1. **Lifespan Management**: Properly initializes core services (DB, SSE, Memory, Observability, Tools)
2. **Health Check**: Comprehensive health endpoint
3. **SSE Streaming**: Working SSE endpoint for real-time updates
4. **Request Validation**: Pydantic models and validation logic
5. **Error Handling**: AgentError framework and HTTP status mapping
6. **Conversation Persistence**: User input persistence
7. **Observability**: LangFuse integration and logging

### What Needs Updating ❌

The `_execute_workflow()` function (lines 509-545) has several critical issues:

#### Issue 1: Simple .ainvoke() Without Interruption Handling

**Current Code**:
```python
result_state = await graph.ainvoke(initial_state, config)
```

**Problem**: This executes the entire graph in one go without handling interruptions for user feedback.

**Solution**: Must use `.astream()` or handle graph interruptions properly when `awaiting_user_feedback=True` is set in state.

#### Issue 2: Missing State Resumption Logic

**Current Code**: Always creates `initial_state` from scratch.

**Problem**: When user provides feedback after workflow pauses, we need to **resume** from the interrupted state, not restart.

**Solution**: Must check if `request.start == False` and load existing graph state using checkpointer.

#### Issue 3: Incorrect State Initialization

**Current Code**:
```python
initial_state = WorkflowGraphState(
    workflow_execution_id=None,  # Set in initialize node
    project_id=request.project_id,
    user_id=request.user_id,
    session_id=request.session_id,
    current_agent="supervisor",
    user_feedback=request.user_input.chat if request.user_input else None,
    content_edits=request.user_input.content_edits if request.user_input else [],
    awaiting_user_feedback=False,
    current_status=WorkflowExecutionStatus.OPEN.value,
    last_updated_at=datetime.utcnow()
)
```

**Problems**:
- Missing many required state fields (agent_tasks, task_outputs, etc.)
- Sets `current_agent="supervisor"` but supervisor isn't executed directly
- Doesn't handle `request.start` flag properly

**Solution**: Create complete state for new workflows, load state for resumptions.

#### Issue 4: No Graph Checkpoint Configuration

**Current Code**:
```python
config = {"configurable": {"thread_id": request.session_id}}
```

**Problem**: While this sets thread_id for checkpointing, we need to ensure:
- MemorySaver is properly configured in graph builder
- Interrupt strategy is defined
- State is properly persisted/loaded

**Solution**: Verify graph builder checkpoint config, add interrupt handling.

#### Issue 5: Missing SSE Event Streaming During Execution

**Current Code**: Graph executes, then returns result. No SSE events sent during execution.

**Problem**: Frontend expects real-time SSE updates as graph progresses through nodes.

**Solution**: Stream graph events and emit SSE events during execution.

---

## Implementation Plan

### Step 1: Update Graph Builder for Interrupts

**File**: `supervisors/workflow/agent_builder.py`

**Changes**:
- Ensure MemorySaver is configured with proper checkpoint serialization
- Add interrupt configuration for user feedback nodes
- Document checkpoint behavior

### Step 2: Refactor `_execute_workflow()` Function

**File**: `supervisors/workflow/agent_executor.py`

**New Logic**:

```python
async def _execute_workflow(request: AgentCoreInvocationRequest) -> Dict[str, Any]:
    """
    Execute workflow using Strands StateGraph with checkpoint support.
    
    Handles two execution modes:
    1. Initial start (request.start=True): Create new workflow, initialize state
    2. Resumption (request.start=False): Load checkpoint, apply user input, resume
    """
    
    # Get compiled graph with checkpointer
    graph = get_workflow_graph()
    config = {"configurable": {"thread_id": request.session_id}}
    
    # Determine execution mode
    if request.start:
        # NEW WORKFLOW: Initialize state
        state = await _initialize_workflow_state(request)
    else:
        # RESUMPTION: Load checkpoint and update with user input
        state = await _resume_workflow_state(request, graph, config)
    
    # Execute graph with streaming
    return await _execute_graph_with_streaming(graph, state, config, request)
```

### Step 3: Implement State Initialization

**New Function**: `_initialize_workflow_state()`

**Purpose**: Create complete initial state for new workflows.

**Logic**:
- Query database for project details
- Set all required WorkflowGraphState fields
- Initialize empty collections (agent_tasks will be created by initialize node)
- Return properly structured state

### Step 4: Implement State Resumption

**New Function**: `_resume_workflow_state()`

**Purpose**: Load existing state from checkpoint and update with user input.

**Logic**:
- Load checkpoint state using `graph.get_state(config)`
- If no checkpoint found, raise error (workflow doesn't exist)
- Update state with user feedback/content edits from request
- Analyze feedback intent (proceed/reparse/reanalyze/etc.)
- Return updated state ready for resumption

### Step 5: Implement Graph Streaming Execution

**New Function**: `_execute_graph_with_streaming()`

**Purpose**: Execute graph with real-time SSE event streaming.

**Logic**:
```python
async def _execute_graph_with_streaming(
    graph, 
    state: WorkflowGraphState, 
    config: Dict, 
    request: AgentCoreInvocationRequest
) -> Dict[str, Any]:
    """Execute graph and stream events via SSE."""
    
    sse_manager = get_sse_manager()
    final_state = None
    
    # Stream graph execution
    async for event in graph.astream(state, config):
        # Extract state update from event
        if isinstance(event, dict):
            for node_name, node_output in event.items():
                # Update final state
                if isinstance(node_output, WorkflowGraphState):
                    final_state = node_output
                
                # Emit SSE event for node completion
                await sse_manager.emit_event(
                    session_id=request.session_id,
                    event_type=f"node_completed",
                    data={
                        "node": node_name,
                        "current_agent": node_output.current_agent,
                        "progress": node_output.calculate_progress(),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
                # Persist event to conversation
                await add_sse_event(
                    project_id=request.project_id,
                    session_id=request.session_id,
                    event_type=f"node_completed",
                    data={"node": node_name}
                )
        
        # Check if graph interrupted for user feedback
        if final_state and final_state.awaiting_user_feedback:
            # Graph interrupted - return current state
            break
    
    # Return execution result
    return {
        "workflow_execution_id": final_state.workflow_execution_id,
        "status": final_state.current_status,
        "awaiting_feedback": final_state.awaiting_user_feedback,
        "message": _get_status_message(final_state)
    }
```

### Step 6: Add Feedback Intent Analysis

**New Function**: `_analyze_feedback_intent()`

**Purpose**: Understand what user wants from their feedback.

**Logic**:
- Parse user_input.chat using simple keyword matching or LLM
- Classify intent: "proceed", "reparse", "reanalyze", "edit_content", "approve_comms", etc.
- Return intent string to update state.feedback_intent

### Step 7: Update Error Handling

**Changes**:
- Add specific error for "workflow not found" during resumption
- Add error for "invalid state transition"
- Improve error messages for checkpoint failures

### Step 8: Add Observability Hooks

**Changes**:
- Log graph execution start/end
- Log node transitions
- Track interruption events
- Monitor checkpoint operations

---

## Key Concepts

### Graph Checkpointing

**LangGraph Checkpointing**: Automatically saves state after each node execution using MemorySaver.

**Thread ID**: `session_id` serves as the checkpoint key. Same session_id = same checkpoint.

**State Resumption**: `graph.get_state(config)` retrieves last saved state for the thread.

### Graph Interruption

**Interrupt Points**: Nodes that set `state.awaiting_user_feedback = True` cause the graph to pause.

**Resumption**: Calling `graph.astream(updated_state, config)` resumes from the interruption point.

**Example Flow**:
1. Graph executes: init → parser → analysis → await_feedback (sets awaiting_user_feedback=True)
2. Graph pauses, returns to FastAPI
3. FastAPI returns response with awaiting_feedback=True
4. User provides feedback
5. FastAPI loads checkpoint, updates state with feedback, calls graph.astream()
6. Graph resumes: analyze_feedback → content → ...

### SSE Event Streaming

**Real-time Updates**: As graph executes nodes, emit SSE events for each transition.

**Event Types**:
- `workflow_created`: When workflow initialized
- `node_completed`: After each node execution
- `agent_started`: When agent node begins
- `agent_completed`: When agent node finishes
- `awaiting_feedback`: When graph pauses for user input
- `workflow_completed`: When all tasks complete
- `error`: On failures

---

## Testing Strategy

### Unit Tests

1. **Test `_initialize_workflow_state()`**
   - Verify all required fields set
   - Check database queries

2. **Test `_resume_workflow_state()`**
   - Mock checkpoint loading
   - Verify state update with user input
   - Test intent analysis

3. **Test `_execute_graph_with_streaming()`**
   - Mock graph.astream()
   - Verify SSE events emitted
   - Test interruption handling

### Integration Tests

1. **Full Workflow Test**
   - Start new workflow (request.start=True)
   - Verify initialize node creates workflow_execution_id
   - Verify SSE events streamed

2. **Interruption Test**
   - Execute until analysis complete
   - Verify graph pauses with awaiting_feedback=True
   - Provide feedback, verify resumption

3. **Error Recovery Test**
   - Trigger agent failure
   - Verify error handling and user notification

---

## Files to Modify

1. **`supervisors/workflow/agent_executor.py`** (Primary changes)
   - Refactor `_execute_workflow()` → split into 3 functions
   - Add state initialization/resumption logic
   - Add streaming execution with SSE
   - Add feedback intent analysis

2. **`supervisors/workflow/agent_builder.py`** (Minor verification)
   - Ensure MemorySaver configured correctly
   - Document interrupt behavior

---

## Success Criteria

✅ New workflows properly initialize with all state fields
✅ Workflow resumption loads checkpoint and applies user input
✅ Graph execution streams SSE events in real-time
✅ Graph interruptions handled correctly (pause on user feedback nodes)
✅ Error handling covers checkpoint failures
✅ Conversation history persists all events
✅ Observability tracks all graph operations

---

## Next Steps After Phase 5

**Phase 6: Testing & Validation**
- End-to-end workflow testing
- Load testing
- Error scenario testing
- Documentation updates