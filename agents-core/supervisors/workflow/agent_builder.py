"""
Workflow Agent Builder - Pure Strands GraphBuilder Pattern with Supervisor Orchestration

Constructs the Strands Graph for the Workflow Supervisor using GraphBuilder.
The supervisor node acts as the central orchestrator, analyzing state and routing to sub-agents.

CRITICAL ARCHITECTURE:
- Entry Point: supervisor node (orchestrator)
- Pattern: Hub-and-Spoke (all nodes route through supervisor)
- Supervisor analyzes state and decides next action
- All sub-agents return control to supervisor after execution

Graph Flow (Supervisor-Centric):
Entry → supervisor → initialize → supervisor
     → supervisor → parser → supervisor
     → supervisor → analysis → supervisor
     → supervisor → await_feedback → supervisor (user interaction)
     → supervisor → content → supervisor
     → supervisor → compliance → supervisor (validation loop)
     → supervisor → qa → supervisor (validation loop)
     → supervisor → await_review → supervisor (user interaction)
     → supervisor → export → supervisor
     → supervisor → comms → supervisor (optional)
     → supervisor → submission → supervisor (optional)
     → supervisor → complete (terminal)

Supervisor Decision Logic:
- Analyzes completed tasks in state.results
- Determines next node based on workflow progress
- Handles feedback loops (reparse, reanalyze, retry content)
- Manages user interaction checkpoints
- Coordinates error recovery
"""

from typing import Dict, Any
from datetime import datetime
from strands.multiagent import GraphBuilder

from core.observability import log_agent_action
from core.error_handling import AgentError, ErrorCode, ErrorSeverity
from models.workflow_models import WorkflowExecutionStatus

# Import ALL node implementations from graph_nodes (including supervisor)
from supervisors.workflow.graph_nodes import (
    supervisor_node,
    initialize_workflow_node,
    parser_agent_node,
    analysis_agent_node,
    content_agent_node,
    compliance_agent_node,
    qa_agent_node,
    comms_agent_node,
    submission_agent_node,
    await_analysis_feedback_node,
    await_artifact_review_node,
    await_comms_permission_node,
    await_submission_permission_node,
    export_artifacts_node,
    complete_workflow_node
)
from supervisors.workflow.state_models import WorkflowGraphState


def build_workflow_graph():
    """
    Build and compile the Workflow Supervisor Graph using pure Strands GraphBuilder.
    
    CRITICAL ARCHITECTURE:
    - Entry point: supervisor_node function (not a simple Agent)
    - All nodes are async functions from graph_nodes.py
    - Supervisor analyzes state and stores next_node decision
    - Conditional edges check supervisor's decision for routing
    - Hub-and-spoke: all nodes return to supervisor
    
    Graph Structure:
    1. supervisor (entry) → analyzes state → decides next node
    2. supervisor → [node based on decision] → executes task
    3. [node] → supervisor → analyzes again → next decision
    4. Repeat until workflow complete
    
    Returns:
        Compiled Strands Graph with supervisor orchestration
    """
    log_agent_action(
        agent_name="workflow_supervisor",
        action="building_graph",
        details={"pattern": "Pure Strands GraphBuilder with Supervisor Node Orchestration"}
    )
    
    # Initialize GraphBuilder
    builder = GraphBuilder()
    
    # ========================================
    # Add Nodes - Using Actual Node Functions
    # ========================================
    
    # Supervisor orchestrator node (entry point)
    builder.add_node(supervisor_node, "supervisor")
    
    # Workflow execution nodes (from graph_nodes.py)
    builder.add_node(initialize_workflow_node, "initialize")
    builder.add_node(parser_agent_node, "parser")
    builder.add_node(analysis_agent_node, "analysis")
    builder.add_node(content_agent_node, "content")
    builder.add_node(compliance_agent_node, "compliance")
    builder.add_node(qa_agent_node, "qa")
    builder.add_node(comms_agent_node, "comms")
    builder.add_node(submission_agent_node, "submission")
    
    # User interaction nodes (from graph_nodes.py)
    builder.add_node(await_analysis_feedback_node, "await_analysis_feedback")
    builder.add_node(await_artifact_review_node, "await_artifact_review")
    builder.add_node(await_comms_permission_node, "await_comms_permission")
    builder.add_node(await_submission_permission_node, "await_submission_permission")
    
    # Finalization nodes (from graph_nodes.py)
    builder.add_node(export_artifacts_node, "export_artifacts")
    builder.add_node(complete_workflow_node, "complete")
    
    # ========================================
    # Set Entry Point
    # ========================================
    
    builder.set_entry_point("supervisor")
    
    # ========================================
    # Add Conditional Edges - Supervisor Routes TO Nodes
    # ========================================
    
    def _route_to(target_node: str):
        """Create condition function for routing to target node"""
        def condition(state: WorkflowGraphState) -> bool:
            supervisor_output = state.task_outputs.get("supervisor", {})
            next_node = supervisor_output.get("next_node", "")
            return next_node == target_node
        return condition
    
    # Supervisor routes to all nodes based on decision
    builder.add_edge("supervisor", "initialize", condition=_route_to("initialize"))
    builder.add_edge("supervisor", "parser", condition=_route_to("parser"))
    builder.add_edge("supervisor", "analysis", condition=_route_to("analysis"))
    builder.add_edge("supervisor", "await_analysis_feedback", condition=_route_to("await_analysis_feedback"))
    builder.add_edge("supervisor", "content", condition=_route_to("content"))
    builder.add_edge("supervisor", "compliance", condition=_route_to("compliance"))
    builder.add_edge("supervisor", "qa", condition=_route_to("qa"))
    builder.add_edge("supervisor", "await_artifact_review", condition=_route_to("await_artifact_review"))
    builder.add_edge("supervisor", "export_artifacts", condition=_route_to("export_artifacts"))
    builder.add_edge("supervisor", "await_comms_permission", condition=_route_to("await_comms_permission"))
    builder.add_edge("supervisor", "comms", condition=_route_to("comms"))
    builder.add_edge("supervisor", "await_submission_permission", condition=_route_to("await_submission_permission"))
    builder.add_edge("supervisor", "submission", condition=_route_to("submission"))
    builder.add_edge("supervisor", "complete", condition=_route_to("complete"))
    
    # ========================================
    # Add Return Edges - All Nodes Return TO Supervisor
    # ========================================
    
    # All execution nodes return control to supervisor
    builder.add_edge("initialize", "supervisor")
    builder.add_edge("parser", "supervisor")
    builder.add_edge("analysis", "supervisor")
    builder.add_edge("await_analysis_feedback", "supervisor")
    builder.add_edge("content", "supervisor")
    builder.add_edge("compliance", "supervisor")
    builder.add_edge("qa", "supervisor")
    builder.add_edge("await_artifact_review", "supervisor")
    builder.add_edge("export_artifacts", "supervisor")
    builder.add_edge("await_comms_permission", "supervisor")
    builder.add_edge("comms", "supervisor")
    builder.add_edge("await_submission_permission", "supervisor")
    builder.add_edge("submission", "supervisor")
    
    # Complete is terminal - no return to supervisor
    
    # ========================================
    # Build Graph
    # ========================================
    
    graph = builder.build()
    
    log_agent_action(
        agent_name="workflow_supervisor",
        action="graph_compiled",
        details={
            "total_nodes": 15,
            "supervisor_node": 1,
            "agent_execution_nodes": 7,
            "user_interaction_nodes": 4,
            "finalization_nodes": 2,
            "orchestration_nodes": 1,
            "pattern": "Hub-and-Spoke with Supervisor Orchestration",
            "entry_point": "supervisor",
            "uses_graph_nodes": True
        }
    )
    
    return graph


def get_workflow_graph():
    """
    Get compiled workflow graph (singleton pattern).
    
    Returns:
        Compiled Strands Graph instance
    """
    return build_workflow_graph()