"""
Strands-compatible tools for BidOps AI agents.

This module provides @tool decorated functions for use with Strands Agents.
All tools follow Strands tool patterns with proper type hints and documentation.
"""

from .database_tools import (
    get_project_documents,
    update_project_document,
    get_next_incomplete_task,
    update_agent_task,
    create_workflow_execution,
    update_workflow_execution,
    create_agent_tasks,
    get_agent_task,
    create_artifact,
    create_artifact_version,
    get_artifacts,
    update_project_progress
)

from .storage_tools import (
    read_s3_file,
    write_s3_file,
    export_artifact_to_s3,
    generate_s3_presigned_url
)

from .mcp_tools import (
    process_document_bedrock_da,
    query_knowledge_base,
    send_slack_notification,
    create_slack_channel
)

__all__ = [
    # Database tools
    "get_project_documents",
    "update_project_document",
    "get_next_incomplete_task",
    "update_agent_task",
    "create_workflow_execution",
    "update_workflow_execution",
    "create_agent_tasks",
    "get_agent_task",
    "create_artifact",
    "create_artifact_version",
    "get_artifacts",
    "update_project_progress",
    
    # Storage tools
    "read_s3_file",
    "write_s3_file",
    "export_artifact_to_s3",
    "generate_s3_presigned_url",
    
    # MCP tools
    "process_document_bedrock_da",
    "query_knowledge_base",
    "send_slack_notification",
    "create_slack_channel"
]