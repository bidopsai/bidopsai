"""
Tool configuration mapping for agents.

Defines which tools are available to each agent based on their role and mode.
This allows agents to be reusable across different supervisors (workflow vs AI assistant)
with different tool access patterns.
"""

from typing import Dict, List, Set

from tools.tool_manager import get_tool_manager


# ==============================================================================
# TOOL DEFINITIONS BY CATEGORY
# ==============================================================================

DATABASE_TOOLS = [
    "get_project",
    "update_project",
    "get_project_documents",
    "update_project_document",
    "create_workflow_execution",
    "get_workflow_execution",
    "update_workflow_execution",
    "create_agent_task",
    "get_agent_task",
    "get_agent_tasks_by_workflow",
    "update_agent_task",
    "create_artifact",
    "get_artifact",
    "get_artifacts_by_project",
    "create_artifact_version",
    "get_latest_artifact_version",
    "save_conversation_message",
    "get_conversation_history",
]

STORAGE_TOOLS = [
    "upload_file_to_s3",
    "download_file_from_s3",
    "generate_s3_presigned_url",
    "list_s3_objects",
    "copy_s3_object",
]

DOCUMENT_PROCESSING_TOOLS = [
    "parse_document",
    "extract_tables",
    "extract_text",
]

COMMUNICATION_TOOLS = [
    "create_slack_channel",
    "send_slack_message",
    "add_users_to_slack_channel",
    "send_email",
    "send_email_with_s3_attachments",
    "create_email_draft",
]

# ==============================================================================
# AGENT TOOL MAPPINGS (Workflow Mode)
# ==============================================================================

WORKFLOW_AGENT_TOOLS: Dict[str, List[str]] = {
    "parser": [
        # Database access
        "get_project",
        "get_project_documents",
        "update_project_document",
        "get_agent_task",
        "update_agent_task",
        # Storage
        "download_file_from_s3",
        "upload_file_to_s3",
        # Document processing
        "parse_document",
        "extract_tables",
        "extract_text",
    ],
    
    "analysis": [
        # Database access
        "get_project",
        "get_project_documents",
        "get_agent_task",
        "get_agent_tasks_by_workflow",
        "update_agent_task",
        # Storage
        "download_file_from_s3",
    ],
    
    "content": [
        # Database access
        "get_project",
        "get_agent_task",
        "get_agent_tasks_by_workflow",
        "update_agent_task",
        "create_artifact",
        "create_artifact_version",
        # Storage
        "download_file_from_s3",
        "upload_file_to_s3",
    ],
    
    "knowledge": [
        # Database access (for context)
        "get_project",
        "get_conversation_history",
        # No direct tool access - used by content agent
    ],
    
    "compliance": [
        # Database access
        "get_project",
        "get_artifact",
        "get_artifacts_by_project",
        "get_latest_artifact_version",
        "get_agent_task",
        "update_agent_task",
    ],
    
    "qa": [
        # Database access
        "get_project",
        "get_artifact",
        "get_artifacts_by_project",
        "get_latest_artifact_version",
        "get_agent_task",
        "get_agent_tasks_by_workflow",
        "update_agent_task",
    ],
    
    "comms": [
        # Database access
        "get_project",
        "get_artifact",
        "get_latest_artifact_version",
        "get_agent_task",
        "update_agent_task",
        # Communication
        "create_slack_channel",
        "send_slack_message",
        "add_users_to_slack_channel",
    ],
    
    "submission": [
        # Database access
        "get_project",
        "get_artifact",
        "get_artifacts_by_project",
        "get_latest_artifact_version",
        "get_agent_task",
        "get_agent_tasks_by_workflow",
        "update_agent_task",
        # Storage
        "download_file_from_s3",
        "generate_s3_presigned_url",
        # Communication
        "send_email",
        "send_email_with_s3_attachments",
        "create_email_draft",
    ],
}


# ==============================================================================
# AGENT TOOL MAPPINGS (AI Assistant Mode)
# ==============================================================================

AI_ASSISTANT_AGENT_TOOLS: Dict[str, List[str]] = {
    "parser": WORKFLOW_AGENT_TOOLS["parser"],  # Same as workflow
    
    "analysis": WORKFLOW_AGENT_TOOLS["analysis"] + [
        "save_conversation_message",  # Can save analysis to conversation
    ],
    
    "content": WORKFLOW_AGENT_TOOLS["content"] + [
        "get_conversation_history",  # Can reference past conversations
    ],
    
    "knowledge": [
        "get_project",
        "get_conversation_history",
        "save_conversation_message",
    ],
    
    "compliance": WORKFLOW_AGENT_TOOLS["compliance"],
    
    "qa": WORKFLOW_AGENT_TOOLS["qa"],
    
    "comms": WORKFLOW_AGENT_TOOLS["comms"],
    
    "submission": WORKFLOW_AGENT_TOOLS["submission"],
}


# ==============================================================================
# SUPERVISOR TOOL MAPPINGS
# ==============================================================================

SUPERVISOR_TOOLS: Dict[str, List[str]] = {
    "workflow_supervisor": [
        # Full database access
        *DATABASE_TOOLS,
        # Storage access
        "upload_file_to_s3",
        "download_file_from_s3",
        "generate_s3_presigned_url",
        "copy_s3_object",
        # Can save conversations
        "save_conversation_message",
        "get_conversation_history",
    ],
    
    "ai_assistant_supervisor": [
        # Database access (same as workflow)
        *DATABASE_TOOLS,
        # Storage
        "download_file_from_s3",
        "generate_s3_presigned_url",
        # Conversation management
        "save_conversation_message",
        "get_conversation_history",
    ],
}


# ==============================================================================
# TOOL CONFIGURATION FUNCTIONS
# ==============================================================================

def get_agent_tools(agent_name: str, mode: str = "workflow") -> List[str]:
    """
    Get tools available to an agent.
    
    Args:
        agent_name: Name of the agent (parser, analysis, content, etc.)
        mode: Execution mode (workflow or ai_assistant)
        
    Returns:
        List of tool names
    """
    if mode == "workflow":
        return WORKFLOW_AGENT_TOOLS.get(agent_name, [])
    elif mode == "ai_assistant":
        return AI_ASSISTANT_AGENT_TOOLS.get(agent_name, [])
    else:
        return []


def get_supervisor_tools(supervisor_type: str) -> List[str]:
    """
    Get tools available to a supervisor.
    
    Args:
        supervisor_type: Supervisor type (workflow_supervisor or ai_assistant_supervisor)
        
    Returns:
        List of tool names
    """
    return SUPERVISOR_TOOLS.get(supervisor_type, [])


async def initialize_all_mcp_clients(tool_manager=None):
    """
    Initialize all MCP clients during application startup.
    
    This connects to MCP servers and retrieves native tool lists.
    Must be called before configuring agent tool mappings.
    
    Args:
        tool_manager: ToolManager instance (optional, uses singleton if not provided)
    """
    if tool_manager is None:
        tool_manager = get_tool_manager()
    
    # Import MCP initialization functions
    from tools.mcp.slack_mcp import initialize_slack_mcp
    from tools.mcp.bedrock_da_mcp import initialize_bedrock_da_mcp
    
    # Initialize Slack MCP (via AgentCore Gateway)
    await initialize_slack_mcp()
    
    # Initialize Bedrock Data Automation MCP
    await initialize_bedrock_da_mcp()
    
    # Configure MCP access for agents
    # Comms Agent gets Slack MCP
    tool_manager.configure_agent_mcp_access(
        agent_name="comms",
        mcp_clients=["slack_mcp"],
        mode="workflow"
    )
    
    # Parser Agent gets Bedrock DA MCP
    tool_manager.configure_agent_mcp_access(
        agent_name="parser",
        mcp_clients=["bedrock_da_mcp"],
        mode="workflow"
    )


def configure_all_tools(tool_manager=None):
    """
    Configure all agent and supervisor tool mappings in the ToolManager.
    
    This should be called during application startup AFTER initializing MCP clients.
    
    Args:
        tool_manager: ToolManager instance (optional, uses singleton if not provided)
    """
    if tool_manager is None:
        tool_manager = get_tool_manager()
    
    # Configure workflow mode agents
    for agent_name, tools in WORKFLOW_AGENT_TOOLS.items():
        tool_manager.configure_agent_tools(f"{agent_name}_workflow", tools)
    
    # Configure AI assistant mode agents
    for agent_name, tools in AI_ASSISTANT_AGENT_TOOLS.items():
        tool_manager.configure_agent_tools(f"{agent_name}_ai_assistant", tools)
    
    # Configure supervisors with mode-based naming
    # Map "supervisor" agent name to supervisor tools based on mode
    tool_manager.configure_agent_tools(
        "supervisor_workflow",
        SUPERVISOR_TOOLS["workflow_supervisor"]
    )
    tool_manager.configure_agent_tools(
        "supervisor_ai_assistant",
        SUPERVISOR_TOOLS["ai_assistant_supervisor"]
    )


def get_all_unique_tools() -> Set[str]:
    """
    Get set of all unique tool names used across all agents.
    
    Returns:
        Set of tool names
    """
    all_tools = set()
    
    for tools in WORKFLOW_AGENT_TOOLS.values():
        all_tools.update(tools)
    
    for tools in AI_ASSISTANT_AGENT_TOOLS.values():
        all_tools.update(tools)
    
    for tools in SUPERVISOR_TOOLS.values():
        all_tools.update(tools)
    
    return all_tools


def validate_tool_configuration() -> Dict[str, List[str]]:
    """
    Validate tool configuration.
    
    Checks for:
    - Tools that are referenced but not defined
    - Agents with no tools
    - Duplicate tool assignments
    
    Returns:
        Dictionary of validation issues
    """
    issues = {
        "undefined_tools": [],
        "agents_with_no_tools": [],
        "warnings": [],
    }
    
    # Get all defined tools
    defined_tools = set(DATABASE_TOOLS + STORAGE_TOOLS + 
                       DOCUMENT_PROCESSING_TOOLS + COMMUNICATION_TOOLS)
    
    # Check all agent tools
    all_agent_tools = {**WORKFLOW_AGENT_TOOLS, **AI_ASSISTANT_AGENT_TOOLS}
    
    for agent_name, tools in all_agent_tools.items():
        if not tools:
            issues["agents_with_no_tools"].append(agent_name)
        
        for tool in tools:
            if tool not in defined_tools:
                if tool not in issues["undefined_tools"]:
                    issues["undefined_tools"].append(tool)
    
    # Check supervisor tools
    for supervisor_type, tools in SUPERVISOR_TOOLS.items():
        for tool in tools:
            if tool not in defined_tools:
                if tool not in issues["undefined_tools"]:
                    issues["undefined_tools"].append(tool)
    
    return issues