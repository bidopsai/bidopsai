"""
Supervisor implementations package.

This package contains supervisor agents that orchestrate workflows:
- Workflow Supervisor: Main bid processing orchestrator (StateGraph)
- AI Assistant Supervisor: Conversational AI assistant (Intent Router)
"""

from supervisors.workflow.agent_builder import build_workflow_graph, get_workflow_graph
from supervisors.workflow.agent_executor import app as workflow_app

__all__ = [
    "build_workflow_graph",
    "get_workflow_graph",
    "workflow_app",
]