"""
Workflow Supervisor Package

Modular implementation of the Workflow Supervisor using Strands StateGraph pattern.

Package Structure:
- agent_executor.py: FastAPI application with /invocations endpoint
- agent_builder.py: StateGraph construction and conditional routing
- graph_nodes.py: Individual node implementations (parser, analysis, etc.)
- state_models.py: Pydantic models for graph state
- config.py: Configuration and settings

Usage:
    # Run FastAPI app
    from supervisors.workflow.agent_executor import app
    
    # Or build graph directly
    from supervisors.workflow.agent_builder import get_workflow_graph
    
    graph = get_workflow_graph()
    result = await graph.ainvoke(initial_state, config)

Design Pattern:
    Follows modular StateGraph pattern with:
    - Separation of concerns (nodes, builder, executor)
    - Reusable node functions
    - Configurable routing logic
    - Clean FastAPI integration
"""

from supervisors.workflow.agent_executor import app
from supervisors.workflow.agent_builder import build_workflow_graph, get_workflow_graph
from supervisors.workflow.state_models import WorkflowGraphState
from supervisors.workflow.config import WorkflowConfig

__all__ = [
    "app",
    "build_workflow_graph",
    "get_workflow_graph",
    "WorkflowGraphState",
    "WorkflowConfig",
]