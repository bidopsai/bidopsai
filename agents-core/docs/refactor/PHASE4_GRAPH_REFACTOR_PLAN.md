# REFACTOR Phase 4: Graph Building - Strands Graph Pattern

## Status: IN PROGRESS

## Objective
Refactor graph implementation to properly integrate with Phase 3 refactored agents (factory functions returning pure Strands `Agent` instances). Current graph nodes call `.execute()` method which doesn't exist on pure agents.

## Current State Analysis

### Issues Identified

1. **Agent Node Functions Call `.execute()` Method**
   - Location: `supervisors/workflow/graph_nodes.py` lines 183-191, 252-263, etc.
   - Problem: Agents are now pure `Agent` instances without `.execute()` method
   - Example:
     ```python
     parser = create_parser_agent(...)
     result = await parser.execute(...)  # ❌ WRONG - Agent has no .execute()
     ```

2. **Missing Comms & Submission Agent Nodes**
   - Graph only has 5 agent nodes (parser, analysis, content, compliance, qa)
   - Requirements specify 7 agents total (missing comms, submission)
   - Per requirements: Comms/Submission handled separately after main workflow

3. **State Model Field Mismatches**
   - `state_models.py` has fields that don't align with Phase 3 patterns
   - Need: `feedback_intent`, `user_feedback`, `content_edits`

4. **Supervisor Not in Graph**
   - Current graph doesn't include supervisor as entry node
   - Requirements: Supervisor should orchestrate all agents

## Correct Strands Graph Pattern

### How Strands Agents Work in Graphs

```python
# ❌ WRONG - Old pattern with wrapper classes
class ParserAgentNode:
    def __init__(self):
        self.agent = Agent(...)
    async def execute(self, **kwargs):
        # Hardcoded orchestration
        return result

# ✅ CORRECT - Strands Graph with pure agents
def build_graph():
    graph = StateGraph(State)
    
    # Agents are created once
    parser_agent = create_parser_agent(mode="workflow")
    
    # Node function invokes agent via Strands
    async def parser_node(state: State):
        # Agent uses LLM + tools autonomously
        result = await parser_agent.ainvoke({
            "messages": state.messages,
            "context": state.context
        })
        state.update(result)
        return state
    
    graph.add_node("parser", parser_node)
    return graph.compile()
```

### Key Principles

1. **Agent Invocation**: Use `agent.ainvoke(input_dict)` or `agent.invoke(input_dict)`
2. **Input Structure**: Agents expect `{"messages": [...], "context": {...}}`
3. **Output Structure**: Agents return structured output based on system prompt
4. **State Management**: Node functions update state with agent results
5. **Tool Access**: Agents use tools autonomously via LLM decisions

## Refactoring Strategy

### Step 1: Update State Models (state_models.py)

**Changes Needed**:
- Add `feedback_intent` field (for analysis routing)
- Add `user_feedback` field (raw user text)
- Add `content_edits` field (artifact edits)
- Ensure all fields match graph routing logic

**Files to Update**:
- `supervisors/workflow/state_models.py`

### Step 2: Refactor Graph Node Functions (graph_nodes.py)

**For Each Agent Node**:

```python
# Before (calls .execute())
async def parser_agent_node(state: WorkflowGraphState) -> WorkflowGraphState:
    parser = create_parser_agent(...)
    result = await parser.execute(...)  # ❌ Wrong
    state.mark_task_complete("parser", result)
    return state

# After (invokes agent via Strands)
async def parser_agent_node(state: WorkflowGraphState) -> WorkflowGraphState:
    # Create agent
    parser = create_parser_agent(
        mode="workflow",
        provider="bedrock",
        session_id=state.session_id
    )
    
    # Prepare input for agent
    input_data = {
        "messages": [
            {"role": "system", "content": "Process documents for project"},
            {"role": "user", "content": f"Project ID: {state.project_id}"}
        ],
        "context": {
            "workflow_execution_id": str(state.workflow_execution_id),
            "project_id": str(state.project_id),
            "user_id": str(state.user_id),
            "previous_outputs": state.task_outputs
        }
    }
    
    # Invoke agent via Strands
    result = await parser.ainvoke(input_data)
    
    # Extract structured output from agent response
    output_data = _extract_agent_output(result)
    
    # Update state
    state.mark_task_complete("parser", output_data)
    return state
```

**Node Functions to Update**:
1. `parser_agent_node` (line 138)
2. `analysis_agent_node` (line 206)
3. `content_agent_node` (line 278)
4. `compliance_agent_node` (line 359)
5. `qa_agent_node` (line 440)

**New Node Functions to Add**:
6. `comms_agent_node` (new)
7. `submission_agent_node` (new)

### Step 3: Update Graph Builder (agent_builder.py)

**Add Missing Nodes**:
```python
# Add comms and submission nodes
workflow.add_node("comms", graph_nodes.comms_agent_node)
workflow.add_node("submission", graph_nodes.submission_agent_node)

# Add edges
workflow.add_edge("export_artifacts", "await_comms_permission")
workflow.add_conditional_edges(
    "await_comms_permission",
    _should_proceed_to_comms,
    {"proceed": "comms", "skip": "complete"}
)
workflow.add_edge("comms", "await_submission_permission")
workflow.add_conditional_edges(
    "await_submission_permission",
    _should_proceed_to_submission,
    {"proceed": "submission", "skip": "complete"}
)
workflow.add_edge("submission", "complete")
```

**Conditional Functions to Add**:
- `_should_proceed_to_comms` (user permission)
- `_should_proceed_to_submission` (user permission)

### Step 4: Add Helper Functions

**Output Extraction Helper**:
```python
def _extract_agent_output(agent_result: Any) -> AgentTaskOutput:
    """
    Extract structured output from Strands Agent result.
    
    Args:
        agent_result: Raw result from agent.ainvoke()
        
    Returns:
        Structured AgentTaskOutput
    """
    # Agent returns AIMessage with tool_calls and content
    if hasattr(agent_result, "content"):
        # Parse JSON from content if structured output used
        try:
            parsed = json.loads(agent_result.content)
            return AgentTaskOutput(**parsed)
        except:
            # Fallback: wrap raw content
            return AgentTaskOutput(
                status="completed",
                output_data={"raw_output": agent_result.content}
            )
    
    # Fallback for other formats
    return AgentTaskOutput(
        status="completed",
        output_data={"result": str(agent_result)}
    )
```

## Implementation Plan

### Task Breakdown

1. **✅ Create Phase 4 Plan Document** (this file)

2. **⏳ Update State Models**
   - File: `supervisors/workflow/state_models.py`
   - Add missing fields: `feedback_intent`, `user_feedback`, `content_edits`
   - Validate field types match routing logic

3. **⏳ Refactor Agent Node Functions**
   - File: `supervisors/workflow/graph_nodes.py`
   - Update 5 existing agent nodes (parser, analysis, content, compliance, qa)
   - Add 2 new agent nodes (comms, submission)
   - Add helper function `_extract_agent_output()`

4. **⏳ Update Graph Builder**
   - File: `supervisors/workflow/agent_builder.py`
   - Add comms and submission nodes
   - Add permission nodes (await_comms_permission, await_submission_permission)
   - Add conditional routing functions
   - Update edges and flow

5. **⏳ Test Graph Compilation**
   - Verify graph compiles without errors
   - Check all nodes are connected
   - Validate conditional routing logic

6. **⏳ Create Phase 4 Completion Report**
   - Document all changes
   - Provide before/after comparisons
   - List remaining work for Phase 5

## Expected Outcomes

After Phase 4 completion:

1. ✅ All agent nodes invoke pure Strands agents via `.ainvoke()`
2. ✅ No `.execute()` method calls anywhere
3. ✅ Graph includes all 7 agents (parser, analysis, content, compliance, qa, comms, submission)
4. ✅ State model has all required fields
5. ✅ Graph compiles successfully
6. ✅ Conditional routing covers all decision points
7. ✅ Ready for Phase 5 FastAPI integration

## Files to Modify

1. `supervisors/workflow/state_models.py` - Update state fields
2. `supervisors/workflow/graph_nodes.py` - Refactor all node functions
3. `supervisors/workflow/agent_builder.py` - Update graph structure

## Notes

- **Don't remove SSE events** - Keep all event emissions for frontend
- **Don't remove DB updates** - Keep database persistence logic
- **Focus on agent invocation** - Main change is how agents are called
- **Preserve error handling** - Keep try/catch blocks and error tracking
- **Keep observability** - Maintain log_agent_action calls

## Next Steps

Starting with Task 2: Update State Models