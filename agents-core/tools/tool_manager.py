"""
Tool Manager for BidOpsAI AgentCore.

Centralized management of tools available to agents, including:
- Custom Python function tools (database, S3, email)
- MCP (Model Context Protocol) tools (Slack, Bedrock Data Automation)
- Tool registration and configuration
- Tool execution with error handling and retry logic
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from core.error_handling import (
    ErrorCode,
    ErrorSeverity,
    ErrorRecoveryStrategy,
    RetryableError,
    handle_error,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)


class ToolDefinition:
    """Definition of a tool available to agents."""
    
    def __init__(
        self,
        name: str,
        description: str,
        function: Callable,
        parameters: Dict[str, Any],
        category: str = "custom",
        requires_approval: bool = False,
        retry_on_failure: bool = True,
        timeout_seconds: int = 60,
    ):
        """
        Initialize tool definition.
        
        Args:
            name: Tool name (unique identifier)
            description: Human-readable description of what tool does
            function: Callable function to execute
            parameters: JSON schema for tool parameters
            category: Tool category (database/storage/communication/mcp)
            requires_approval: Whether tool requires human approval
            retry_on_failure: Whether to retry on transient failures
            timeout_seconds: Execution timeout
        """
        self.name = name
        self.description = description
        self.function = function
        self.parameters = parameters
        self.category = category
        self.requires_approval = requires_approval
        self.retry_on_failure = retry_on_failure
        self.timeout_seconds = timeout_seconds
        self.enabled = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for LLM function calling (legacy)."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
    
    def to_strands_tool(self) -> Any:
        """
        Convert to Strands Agent tool format.
        
        Returns a tool object that Strands Agent can use directly.
        For custom Python functions, this wraps the function in a format
        compatible with Strands tooling system.
        
        Returns:
            Tool object for Strands Agent
        """
        from strands.tools import Tool
        
        return Tool(
            name=self.name,
            description=self.description,
            function=self.function,
            parameters=self.parameters,
        )


class ToolExecutionResult:
    """Result from tool execution."""
    
    def __init__(
        self,
        success: bool,
        output: Any = None,
        error: Optional[str] = None,
        error_code: Optional[str] = None,
        execution_time_seconds: float = 0.0,
        retry_count: int = 0,
    ):
        self.success = success
        self.output = output
        self.error = error
        self.error_code = error_code
        self.execution_time_seconds = execution_time_seconds
        self.retry_count = retry_count
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "error_code": self.error_code,
            "execution_time_seconds": self.execution_time_seconds,
            "retry_count": self.retry_count,
        }


class ToolManager:
    """
    Centralized tool manager for agent toolkit.
    
    Manages registration, configuration, and execution of all tools
    available to agents (custom functions and MCP tools).
    """
    
    _instance: Optional["ToolManager"] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize tool manager."""
        if not hasattr(self, "_initialized"):
            self._tools: Dict[str, ToolDefinition] = {}
            self._mcp_clients: Dict[str, Any] = {}  # MCP client connections
            self._mcp_tool_lists: Dict[str, List[Any]] = {}  # MCP client -> native tool lists
            self._agent_tool_mappings: Dict[str, Set[str]] = {}  # agent -> tool names
            self._agent_mcp_mappings: Dict[str, Dict[str, Any]] = {}  # agent -> MCP config
            self._initialized = True
            logger.info("ToolManager initialized")
    
    def register_tool(
        self,
        name: str,
        description: str,
        function: Callable,
        parameters: Dict[str, Any],
        category: str = "custom",
        **kwargs
    ) -> None:
        """
        Register a new tool.
        
        Args:
            name: Unique tool name
            description: Tool description
            function: Callable function
            parameters: JSON schema for parameters
            category: Tool category
            **kwargs: Additional tool configuration
        """
        if name in self._tools:
            logger.warning(f"Tool '{name}' already registered, overwriting")
        
        tool = ToolDefinition(
            name=name,
            description=description,
            function=function,
            parameters=parameters,
            category=category,
            **kwargs
        )
        
        self._tools[name] = tool
        logger.info(f"Registered tool: {name} (category: {category})")
    
    async def initialize_mcp_client(
        self,
        client_name: str,
        server_params: StdioServerParameters,
    ) -> None:
        """
        Initialize an MCP client and retrieve its native tool list.
        
        This method connects to an MCP server, retrieves the list of available tools,
        and stores them for direct use by agents (no Python wrappers needed).
        
        Args:
            client_name: Name of MCP client (e.g., 'slack_mcp', 'bedrock_da_mcp')
            server_params: MCP server connection parameters
            
        Example:
            ```python
            # Initialize Slack MCP via AgentCore Gateway
            slack_params = StdioServerParameters(
                command="aws",
                args=["bedrock-agentcore", "gateway", "mcp", "invoke",
                      "--mcp-server-name", "slack-server"],
                env={"AWS_REGION": "us-east-1"}
            )
            await tool_manager.initialize_mcp_client("slack_mcp", slack_params)
            ```
        """
        try:
            logger.info(f"Initializing MCP client: {client_name}")
            
            # Create MCP client session
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the session
                    await session.initialize()
                    
                    # List available tools from MCP server
                    tools_result = await session.list_tools()
                    native_tools = tools_result.tools
                    
                    # Store the session and tool list
                    self._mcp_clients[client_name] = session
                    self._mcp_tool_lists[client_name] = native_tools
                    
                    logger.info(
                        f"MCP client '{client_name}' initialized with "
                        f"{len(native_tools)} native tools"
                    )
                    
                    # Log tool names for debugging
                    tool_names = [t.name for t in native_tools]
                    logger.debug(f"Available tools from '{client_name}': {tool_names}")
                    
        except Exception as e:
            logger.error(
                f"Failed to initialize MCP client '{client_name}': {e}",
                exc_info=True
            )
            raise RetryableError(
                f"MCP client initialization failed: {str(e)}",
                error_code=ErrorCode.TOOL_INITIALIZATION_ERROR,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.RESET_AND_RETRY,
                original_exception=e,
            )
    
    def register_mcp_client(self, client_name: str, client: Any) -> None:
        """
        Register an MCP client (legacy method - prefer initialize_mcp_client).
        
        Args:
            client_name: Name of MCP client (e.g., 'slack', 'bedrock_da')
            client: MCP client instance
        """
        self._mcp_clients[client_name] = client
        logger.info(f"Registered MCP client: {client_name}")
    
    def configure_agent_mcp_access(
        self,
        agent_name: str,
        mcp_clients: List[str],
        mode: Optional[str] = None,
    ) -> None:
        """
        Configure which MCP clients an agent can access.
        
        This allows agents to use native MCP tools directly without Python wrappers.
        
        Args:
            agent_name: Name of the agent
            mcp_clients: List of MCP client names the agent can access
            mode: Optional mode specifier (e.g., "workflow", "ai_assistant")
            
        Example:
            ```python
            # Configure Comms Agent with Slack MCP access
            tool_manager.configure_agent_mcp_access(
                agent_name="comms",
                mcp_clients=["slack_mcp"],
                mode="workflow"
            )
            ```
        """
        # Filter to only valid MCP clients (may not be initialized yet in dev)
        valid_clients = [c for c in mcp_clients if c in self._mcp_clients]
        invalid_clients = [c for c in mcp_clients if c not in self._mcp_clients]
        
        if invalid_clients:
            logger.debug(
                f"Agent '{agent_name}': MCP clients not yet initialized: {invalid_clients} "
                "(will be available once MCP servers start)"
            )
        
        # Store MCP configuration (even if clients not initialized yet)
        config_key = f"{agent_name}_{mode}" if mode else agent_name
        self._agent_mcp_mappings[config_key] = {
            "clients": mcp_clients,  # Store all, not just valid
            "mode": mode,
        }
        
        logger.info(
            f"Configured {len(mcp_clients)} MCP clients for agent '{agent_name}'"
            + (f" in mode '{mode}'" if mode else "")
            + (f" ({len(valid_clients)} initialized)" if invalid_clients else "")
        )
    
    def configure_agent_tools(
        self,
        agent_name: str,
        tool_names: List[str]
    ) -> None:
        """
        Configure which tools an agent can use.
        
        Note: This method stores tool names for agents. Tools decorated with @tool
        from Strands are passed directly to agents and don't need to be registered
        in ToolManager. Only custom tools that need ToolManager's execution wrapper
        (retry logic, approval, etc.) should be registered via register_tool().
        
        Args:
            agent_name: Name of the agent
            tool_names: List of tool names available to agent (includes Strands tools)
        """
        # Store all tool names (Strands tools + registered custom tools)
        # We don't validate here because many tools are Strands-native
        self._agent_tool_mappings[agent_name] = set(tool_names)
        
        # Count registered vs unregistered (likely Strands) tools
        registered_count = len([t for t in tool_names if t in self._tools])
        strands_count = len(tool_names) - registered_count
        
        logger.info(
            f"Configured {len(tool_names)} tools for agent '{agent_name}' "
            f"({registered_count} registered + {strands_count} Strands-native)"
        )
    
    def get_agent_tools(
        self,
        agent_name: str,
        mode: str = "workflow"
    ) -> List[Any]:
        """
        Get tools available to an agent (custom + native MCP tools).
        
        This method returns a combined list of:
        1. Custom Python function tools (converted to Strands tool format)
        2. Native MCP tools (passed directly, no wrappers)
        
        Args:
            agent_name: Name of the agent
            mode: Agent mode ("workflow" or "ai_assistant")
            
        Returns:
            List of tool objects for Strands Agent
        """
        tools = []
        
        # Get custom tool names for agent
        tool_names = self._agent_tool_mappings.get(agent_name, set())
        
        # Filter tools by mode if mode-specific mappings exist
        mode_key = f"{agent_name}_{mode}"
        if mode_key in self._agent_tool_mappings:
            tool_names = self._agent_tool_mappings[mode_key]
        
        # Add custom Python function tools
        for tool_name in tool_names:
            tool = self._tools.get(tool_name)
            if tool and tool.enabled:
                # Convert to Strands tool format
                tools.append(tool.to_strands_tool())
        
        # Add native MCP tools
        mcp_config = self._agent_mcp_mappings.get(mode_key, {})
        if not mcp_config:
            mcp_config = self._agent_mcp_mappings.get(agent_name, {})
        
        if mcp_config:
            for client_name in mcp_config.get("clients", []):
                if client_name in self._mcp_tool_lists:
                    native_tools = self._mcp_tool_lists[client_name]
                    tools.extend(native_tools)
                    logger.debug(
                        f"Added {len(native_tools)} native MCP tools from "
                        f"'{client_name}' for agent '{agent_name}'"
                    )
        
        logger.info(
            f"Retrieved {len(tools)} total tools for agent '{agent_name}' "
            f"in mode '{mode}' (custom + MCP)"
        )
        
        return tools
    
    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        return self._tools.get(tool_name)
    
    def get_mcp_client(self, client_name: str) -> Optional[Any]:
        """Get MCP client by name."""
        return self._mcp_clients.get(client_name)
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        agent_name: Optional[str] = None,
        require_approval: bool = False,
    ) -> ToolExecutionResult:
        """
        Execute a tool with error handling and retry logic.
        
        Args:
            tool_name: Name of tool to execute
            parameters: Tool parameters
            agent_name: Name of agent executing tool (for permission check)
            require_approval: Override tool's approval requirement
            
        Returns:
            ToolExecutionResult with output or error
        """
        import time
        start_time = time.time()
        retry_count = 0
        
        try:
            # Get tool definition
            tool = self.get_tool(tool_name)
            if not tool:
                return ToolExecutionResult(
                    success=False,
                    error=f"Tool '{tool_name}' not found",
                    error_code=ErrorCode.TOOL_NOT_FOUND,
                    execution_time_seconds=time.time() - start_time,
                )
            
            # Check if tool is enabled
            if not tool.enabled:
                return ToolExecutionResult(
                    success=False,
                    error=f"Tool '{tool_name}' is disabled",
                    error_code=ErrorCode.TOOL_DISABLED,
                    execution_time_seconds=time.time() - start_time,
                )
            
            # Check agent permissions
            if agent_name and agent_name in self._agent_tool_mappings:
                allowed_tools = self._agent_tool_mappings[agent_name]
                if tool_name not in allowed_tools:
                    return ToolExecutionResult(
                        success=False,
                        error=f"Agent '{agent_name}' not authorized for tool '{tool_name}'",
                        error_code=ErrorCode.TOOL_UNAUTHORIZED,
                        execution_time_seconds=time.time() - start_time,
                    )
            
            # Check approval requirement
            if tool.requires_approval or require_approval:
                logger.warning(
                    f"Tool '{tool_name}' requires approval (not implemented in this execution)"
                )
                # TODO: Implement approval workflow via SSE
            
            # Execute with retry if enabled
            if tool.retry_on_failure:
                @retry_with_backoff(max_retries=3)
                async def execute_with_retry():
                    nonlocal retry_count
                    retry_count += 1
                    return await self._execute_tool_function(
                        tool, parameters, tool.timeout_seconds
                    )
                
                output = await execute_with_retry()
            else:
                output = await self._execute_tool_function(
                    tool, parameters, tool.timeout_seconds
                )
            
            execution_time = time.time() - start_time
            
            logger.info(
                f"Tool '{tool_name}' executed successfully "
                f"(time: {execution_time:.2f}s, retries: {retry_count})"
            )
            
            return ToolExecutionResult(
                success=True,
                output=output,
                execution_time_seconds=execution_time,
                retry_count=retry_count,
            )
        
        except RetryableError as e:
            execution_time = time.time() - start_time
            logger.error(f"Tool '{tool_name}' failed after retries: {e}")
            return ToolExecutionResult(
                success=False,
                error=str(e),
                error_code=e.error_code,
                execution_time_seconds=execution_time,
                retry_count=retry_count,
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Tool '{tool_name}' execution error: {e}", exc_info=True)
            return ToolExecutionResult(
                success=False,
                error=str(e),
                error_code=ErrorCode.TOOL_EXECUTION_ERROR,
                execution_time_seconds=execution_time,
                retry_count=retry_count,
            )
    
    async def _execute_tool_function(
        self,
        tool: ToolDefinition,
        parameters: Dict[str, Any],
        timeout_seconds: int,
    ) -> Any:
        """
        Execute tool function with timeout.
        
        Args:
            tool: Tool definition
            parameters: Tool parameters
            timeout_seconds: Execution timeout
            
        Returns:
            Tool output
            
        Raises:
            asyncio.TimeoutError: If execution times out
            Exception: If tool execution fails
        """
        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(tool.function):
                result = await asyncio.wait_for(
                    tool.function(**parameters),
                    timeout=timeout_seconds
                )
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: tool.function(**parameters)
                    ),
                    timeout=timeout_seconds
                )
            
            return result
        
        except asyncio.TimeoutError:
            raise RetryableError(
                f"Tool execution timed out after {timeout_seconds}s",
                error_code=ErrorCode.TOOL_TIMEOUT,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.RESET_AND_RETRY,
            )
        
        except Exception as e:
            # Wrap in RetryableError for retry logic
            raise RetryableError(
                f"Tool execution failed: {str(e)}",
                error_code=ErrorCode.TOOL_EXECUTION_ERROR,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.RESET_AND_RETRY,
                original_exception=e,
            )
    
    def list_tools(
        self,
        category: Optional[str] = None,
        enabled_only: bool = True
    ) -> List[str]:
        """
        List available tool names.
        
        Args:
            category: Filter by category
            enabled_only: Only return enabled tools
            
        Returns:
            List of tool names
        """
        tools = []
        for name, tool in self._tools.items():
            if category and tool.category != category:
                continue
            if enabled_only and not tool.enabled:
                continue
            tools.append(name)
        
        return sorted(tools)
    
    def enable_tool(self, tool_name: str) -> bool:
        """Enable a tool."""
        tool = self.get_tool(tool_name)
        if tool:
            tool.enabled = True
            logger.info(f"Enabled tool: {tool_name}")
            return True
        return False
    
    def disable_tool(self, tool_name: str) -> bool:
        """Disable a tool."""
        tool = self.get_tool(tool_name)
        if tool:
            tool.enabled = False
            logger.info(f"Disabled tool: {tool_name}")
            return True
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get tool manager statistics."""
        return {
            "total_tools": len(self._tools),
            "enabled_tools": len([t for t in self._tools.values() if t.enabled]),
            "disabled_tools": len([t for t in self._tools.values() if not t.enabled]),
            "mcp_clients": len(self._mcp_clients),
            "configured_agents": len(self._agent_tool_mappings),
            "tools_by_category": {
                category: len([
                    t for t in self._tools.values()
                    if t.category == category
                ])
                for category in set(t.category for t in self._tools.values())
            },
        }


# Singleton instance
def get_tool_manager() -> ToolManager:
    """Get singleton ToolManager instance."""
    return ToolManager()