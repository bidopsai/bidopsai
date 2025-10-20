"""
Strands Graph Node Wrapper for Async Functions

Wraps async functions to be compatible with Strands GraphBuilder.
Strands Graph requires nodes to be Agent or MultiAgentBase instances.
This wrapper allows us to use async functions as graph nodes.
"""

from typing import Callable, Awaitable, Any, Dict
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.agent.agent_result import AgentResult
from strands.types.content import ContentBlock, Message

from supervisors.workflow.state_models import WorkflowGraphState
from core.observability import log_agent_action


class GraphNodeWrapper(MultiAgentBase):
    """
    Wrapper to make async functions compatible with Strands GraphBuilder.
    
    Strands Graph requires nodes to extend MultiAgentBase and implement invoke_async().
    This wrapper allows us to use our existing async node functions with Strands Graph.
    
    Example:
        ```python
        async def my_node(state: WorkflowGraphState) -> WorkflowGraphState:
            # Do something
            return state
        
        wrapped_node = GraphNodeWrapper(my_node, "my_node")
        builder.add_node(wrapped_node, "my_node")
        ```
    """
    
    def __init__(
        self,
        func: Callable[[WorkflowGraphState], Awaitable[WorkflowGraphState]],
        name: str
    ):
        """
        Initialize the node wrapper.
        
        Args:
            func: Async function that takes WorkflowGraphState and returns WorkflowGraphState
            name: Name of the node (for logging and identification)
        """
        super().__init__()
        self.func = func
        self.name = name
        
    async def invoke_async(
        self,
        task: Any,
        invocation_state: Dict[str, Any],
        **kwargs
    ) -> MultiAgentResult:
        """
        Execute the wrapped async function.
        
        This method is called by Strands Graph when the node is executed.
        We convert the task/state to WorkflowGraphState, execute our function,
        and wrap the result in MultiAgentResult format.
        
        Args:
            task: Input task (usually a string or WorkflowGraphState)
            invocation_state: Current graph state
            **kwargs: Additional arguments
            
        Returns:
            MultiAgentResult with the node execution result
        """
        log_agent_action(
            agent_name="graph_node_wrapper",
            action=f"executing_{self.name}",
            details={"node_name": self.name}
        )
        
        try:
            # Get the state from invocation_state
            # Strands Graph passes the state through invocation_state
            state = invocation_state.get("workflow_state")
            
            if state is None:
                # If no state in invocation_state, try to use task as state
                if isinstance(task, WorkflowGraphState):
                    state = task
                else:
                    raise ValueError(f"No WorkflowGraphState found in invocation_state or task")
            
            # Convert dict to WorkflowGraphState if needed
            if isinstance(state, dict):
                state = WorkflowGraphState(**state)
            
            # Execute the wrapped async function
            updated_state = await self.func(state)
            
            # Persist state to memory after each node execution
            try:
                from core.memory import get_memory_manager
                import json
                
                memory_manager = get_memory_manager()
                session_id = invocation_state.get('session_id')
                user_id = invocation_state.get('user_id')
                
                if session_id and user_id:
                    memory_key = f"workflow_state_{session_id}"
                    
                    # Serialize state to dict for storage
                    state_dict = updated_state.dict() if hasattr(updated_state, 'dict') else updated_state.__dict__
                    
                    await memory_manager.store(
                        key=memory_key,
                        value=json.dumps(state_dict, default=str),
                        user_id=user_id
                    )
            except Exception as mem_error:
                # Log but don't fail if memory persistence fails
                log_agent_action(
                    agent_name="graph_node_wrapper",
                    action=f"{self.name}_memory_persist_failed",
                    details={"error": str(mem_error)},
                    level="warning"
                )
            
            # Create AgentResult to wrap the state
            # CRITICAL: Store next_node in state for conditional edge functions
            # Strands conditional functions access this via agent_result.state
            agent_result = AgentResult(
                stop_reason="end_turn",
                message=Message(
                    role="assistant",
                    content=[ContentBlock(text=f"Node {self.name} executed successfully")]
                ),
                state={
                    "next_node": getattr(updated_state, 'supervisor_next_node', None),
                    "workflow_state": updated_state.dict() if hasattr(updated_state, 'dict') else {}
                },  # Store routing decision for conditional edges
                metrics={
                    "node_name": self.name,
                    "status": "completed"
                }
            )
            
            # Create NodeResult
            # NodeResult constructor takes positional args: (result)
            # node_id, execution_time_ms, error are optional and must be passed positionally
            node_result = NodeResult(
                agent_result  # Only pass result, Strands will handle the rest
            )
            
            # Return MultiAgentResult with updated state
            # Store updated state back in invocation_state for next node
            invocation_state["workflow_state"] = updated_state
            
            return MultiAgentResult(
                status=Status.COMPLETED,
                results={self.name: node_result}
            )
            
        except Exception as e:
            log_agent_action(
                agent_name="graph_node_wrapper",
                action=f"{self.name}_failed",
                details={
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                level="error"
            )
            
            # Create failed AgentResult
            agent_result = AgentResult(
                stop_reason="error",
                message=Message(
                    role="assistant",
                    content=[ContentBlock(text=f"Node {self.name} failed: {str(e)}")]
                ),
                state={},  # Required parameter for AgentResult
                metrics={
                    "node_name": self.name,
                    "status": "failed",
                    "error": str(e)
                }
            )
            
            # Create failed NodeResult
            # NodeResult constructor takes positional args: (result)
            node_result = NodeResult(
                agent_result  # Only pass result, Strands will handle the rest
            )
            
            # Return failed MultiAgentResult
            return MultiAgentResult(
                status=Status.FAILED,
                results={self.name: node_result}
            )