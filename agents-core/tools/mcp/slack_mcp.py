"""
Slack MCP Integration - Direct MCP Client Access

This module provides MCP client initialization for Slack integration
via Amazon Bedrock AgentCore MCP Gateway. NO WRAPPERS - agents receive
native MCP tools directly.

Architecture Pattern (CORRECT):
1. Initialize MCP client during startup
2. Retrieve native tool list from MCP server
3. Pass native tools directly to agents
4. Agents invoke MCP tools natively (no Python function calls)

Reference:
https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/02-AgentCore-gateway

Usage:
    ```python
    from tools.mcp.slack_mcp import initialize_slack_mcp
    from tools.tool_manager import get_tool_manager
    
    # Initialize Slack MCP client
    await initialize_slack_mcp()
    
    # Tools are now available via tool_manager
    tool_manager = get_tool_manager()
    comms_tools = tool_manager.get_agent_tools("comms", mode="workflow")
    # comms_tools will include native Slack MCP tools
    ```
"""

import logging
from typing import Optional

from mcp import StdioServerParameters

from core.config import get_config
from core.error_handling import AgentError, ErrorCode, ErrorSeverity
from core.observability import log_agent_action
from tools.tool_manager import get_tool_manager

logger = logging.getLogger(__name__)


async def initialize_slack_mcp() -> None:
    """
    Initialize Slack MCP client via AgentCore MCP Gateway.
    
    This function:
    1. Creates MCP client connection to AgentCore Gateway
    2. Retrieves native Slack tool list (conversations.create, chat.postMessage, etc.)
    3. Stores tools in ToolManager for agent access
    
    Agents will receive these tools natively - NO Python wrapper functions.
    
    Raises:
        AgentError: If initialization fails
    """
    log_agent_action(
        agent_name="system",
        action="slack_mcp_init_start",
        details={"client": "slack_mcp"}
    )
    
    try:
        config = get_config()
        
        # Get AgentCore Gateway configuration
        gateway_region = config.get("aws.region", "us-east-1")
        slack_server_name = config.get(
            "agentcore.mcp.slack_server_name",
            "slack-workspace-server"
        )
        
        # Create MCP server parameters for AgentCore Gateway
        # The gateway acts as an MCP server, exposing Slack tools
        server_params = StdioServerParameters(
            command="aws",
            args=[
                "bedrock-agentcore",
                "gateway",
                "mcp",
                "invoke",
                "--mcp-server-name", slack_server_name,
            ],
            env={
                "AWS_REGION": gateway_region,
                # AgentCore Gateway handles Slack auth via IAM
            }
        )
        
        # Initialize MCP client and retrieve native tools
        tool_manager = get_tool_manager()
        await tool_manager.initialize_mcp_client(
            client_name="slack_mcp",
            server_params=server_params
        )
        
        log_agent_action(
            agent_name="system",
            action="slack_mcp_init_success",
            details={
                "client": "slack_mcp",
                "server": slack_server_name
            }
        )
        
        logger.info(
            f"Slack MCP client initialized successfully via AgentCore Gateway "
            f"(server: {slack_server_name})"
        )
        
    except Exception as e:
        log_agent_action(
            agent_name="system",
            action="slack_mcp_init_failed",
            details={"error": str(e)},
            level="error"
        )
        
        logger.error(f"Failed to initialize Slack MCP: {e}", exc_info=True)
        
        raise AgentError(
            code=ErrorCode.TOOL_INITIALIZATION_ERROR,
            message=f"Failed to initialize Slack MCP client: {str(e)}",
            severity=ErrorSeverity.HIGH,
            details={"error": str(e)}
        ) from e


def get_slack_mcp_system_prompt() -> str:
    """
    Get system prompt instructions for using Slack MCP tools.
    
    This prompt teaches agents how to use native Slack MCP tools correctly.
    Include this in agent system prompts when they have Slack access.
    
    Returns:
        System prompt text for Slack MCP tool usage
    """
    return """
## Slack Communication Tools

You have access to native Slack MCP tools via AgentCore Gateway. Use these tools to:
- Create channels for project collaboration
- Send notifications to team members
- Invite users to project channels

### Available Slack Tools

1. **conversations.create** - Create a new Slack channel
   - Use for: Creating project-specific channels
   - Required: name (channel name, lowercase, no spaces)
   - Optional: is_private (default: false)
   
2. **chat.postMessage** - Send a message to a channel
   - Use for: Posting notifications, updates, artifacts links
   - Required: channel (channel ID from create), text (message content)
   - Optional: blocks (for rich formatting)

3. **conversations.invite** - Invite users to a channel
   - Use for: Adding project members to channels
   - Required: channel (channel ID), users (comma-separated user IDs)

### Slack Usage Pattern

**Step 1: Create Channel**
```
Call: conversations.create
Args: {
  "name": "project-rfp-acme-corp",
  "is_private": false
}
Result: { "ok": true, "channel": { "id": "C12345" } }
```

**Step 2: Send Notification**
```
Call: chat.postMessage
Args: {
  "channel": "C12345",
  "text": "Project artifacts ready for review: [links]"
}
```

**Step 3: Invite Team Members**
```
Call: conversations.invite
Args: {
  "channel": "C12345",
  "users": "U111,U222,U333"
}
```

### Channel Naming Rules

- Lowercase only
- Use hyphens instead of spaces
- Max 80 characters
- Only alphanumeric and hyphens
- Pattern: `project-{sanitized_project_name}`

### Error Handling

If tool calls fail:
1. Check channel/user IDs are valid
2. Verify channel name follows Slack rules
3. Ensure users exist in workspace
4. Report error to user for resolution
"""


# Legacy compatibility - mark deprecated
def get_slack_client():
    """
    DEPRECATED: Direct Slack client access removed.
    
    Agents now receive native MCP tools directly from ToolManager.
    Use tool_manager.get_agent_tools() instead.
    """
    raise NotImplementedError(
        "Direct Slack client access is deprecated. "
        "Agents receive native MCP tools via ToolManager. "
        "Use: tool_manager.get_agent_tools(agent_name, mode)"
    )


async def create_slack_channel(*args, **kwargs):
    """DEPRECATED: Wrapper functions removed. Use native MCP tools."""
    raise NotImplementedError(
        "Python wrapper functions are deprecated. "
        "Agents use native MCP tool 'conversations.create' directly."
    )


async def send_slack_message(*args, **kwargs):
    """DEPRECATED: Wrapper functions removed. Use native MCP tools."""
    raise NotImplementedError(
        "Python wrapper functions are deprecated. "
        "Agents use native MCP tool 'chat.postMessage' directly."
    )


async def invite_users_to_channel(*args, **kwargs):
    """DEPRECATED: Wrapper functions removed. Use native MCP tools."""
    raise NotImplementedError(
        "Python wrapper functions are deprecated. "
        "Agents use native MCP tool 'conversations.invite' directly."
    )