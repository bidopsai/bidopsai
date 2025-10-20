"""
Base Agent Module

Provides abstract base class for all BidOpsAI agents following OOP principles.
All agent implementations must inherit from BaseAgent to ensure consistent
interface and behavior.

Design Principles:
- Encapsulation: Agent configuration stored as instance variables
- Inheritance: Common functionality in base class, specifics in subclasses
- Abstraction: Abstract methods define contract for subclasses
- Composition: Dependencies injected, not accessed globally
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from strands import Agent

from core.memory import get_memory_manager, MemoryConfig

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all BidOpsAI agents.
    
    Provides common initialization, configuration management, and agent lifecycle
    methods. All concrete agent classes must inherit from this base class and
    implement required abstract methods.
    
    The base class implements the Template Method pattern for agent creation,
    allowing subclasses to customize specific steps while maintaining a consistent
    overall process.
    
    Attributes:
        _mode: Agent operating mode (workflow/ai_assistant)
        _provider: LLM provider identifier
        _model_id: Model identifier
        _temperature: LLM temperature setting
        _config: Additional configuration parameters
        _agent: Cached Strands Agent instance (lazy initialization)
        _tools: Cached tools list
        _model: Cached LLM model instance
        _system_prompt: Cached system prompt string
        _memory_config: Memory configuration for this agent
        _session_manager: AgentCore memory session manager
    
    Example:
        ```python
        class MyAgent(BaseAgent):
            def _get_agent_specific_config(self) -> Dict[str, Any]:
                return {"max_tool_iterations": 20}
        
        # Create instance
        agent = MyAgent(mode="workflow", provider="bedrock")
        
        # Get Strands Agent (lazy initialization)
        strands_agent = agent.get_agent()
        
        # Invoke agent
        result = await agent.ainvoke(input_data)
        ```
    """
    
    def __init__(
        self,
        mode: str = "workflow",
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        temperature: Optional[float] = None,
        memory_config: Optional[MemoryConfig] = None,
        session_manager: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize base agent with common configuration.
        
        Args:
            mode: Agent mode (workflow/ai_assistant)
            provider: LLM provider (bedrock/openai/anthropic/gemini)
                     Defaults to environment DEFAULT_LLM_PROVIDER
            model_id: Model identifier - defaults to provider's default from env
            temperature: LLM temperature (0.0-1.0)
            memory_config: Optional memory configuration for AgentCore Memory
            session_manager: Optional pre-configured session manager
            **kwargs: Additional configuration parameters
            
        Raises:
            ValueError: If mode is invalid
        """
        # Store configuration as instance variables (encapsulation)
        self._mode = mode
        self._provider = provider
        self._model_id = model_id
        self._temperature = temperature
        self._config = kwargs
        
        # Initialize component caches (lazy loading)
        self._agent: Optional[Agent] = None
        self._tools: Optional[List] = None
        self._model = None
        self._system_prompt: Optional[str] = None
        
        # Memory configuration
        self._memory_config = memory_config
        self._session_manager = session_manager
        
        # Validate configuration
        self._validate_config()
        
        logger.debug(
            f"BaseAgent initialized: {self.__class__.__name__} "
            f"(mode={mode}, provider={provider}, memory_enabled={memory_config is not None})"
        )
    
    @property
    def mode(self) -> str:
        """Get agent operating mode."""
        return self._mode
    
    @property
    def provider(self) -> Optional[str]:
        """Get LLM provider."""
        return self._provider
    
    @property
    def model_id(self) -> Optional[str]:
        """Get model identifier."""
        return self._model_id
    
    @property
    def temperature(self) -> Optional[float]:
        """Get LLM temperature."""
        return self._temperature
    
    @property
    def agent_name(self) -> str:
        """
        Get agent name derived from class name.
        
        Returns:
            Lowercase agent name (e.g., "parser", "analysis", "supervisor")
            
        Example:
            ParserAgent -> "parser"
            AnalysisAgent -> "analysis"
            SupervisorAgent -> "supervisor"
        """
        class_name = self.__class__.__name__
        # Remove "Agent" suffix and convert to lowercase
        if class_name.endswith("Agent"):
            return class_name[:-5].lower()
        return class_name.lower()
    
    @abstractmethod
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """
        Get agent-specific configuration.
        
        Subclasses must implement this method to provide agent-specific
        settings that will be passed to the Strands Agent constructor.
        
        Returns:
            Dictionary with agent-specific configuration parameters
            
        Example:
            ```python
            def _get_agent_specific_config(self) -> Dict[str, Any]:
                return {
                    "max_tool_iterations": 20,
                    "require_tool_approval": False
                }
            ```
        """
        pass
    
    def _validate_config(self) -> None:
        """
        Validate agent configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        valid_modes = ["workflow", "ai_assistant"]
        if self._mode not in valid_modes:
            raise ValueError(
                f"Invalid mode: {self._mode}. "
                f"Must be one of: {', '.join(valid_modes)}"
            )
    
    def _load_tools(self) -> List:
        """
        Load tools for this agent from tool manager.
        
        Returns:
            List of tools configured for this agent and mode
            
        Note:
            This method accesses the tool manager to retrieve agent-specific
            tools. Subclasses can override to customize tool loading.
        """
        from tools.tool_manager import get_tool_manager
        
        tool_manager = get_tool_manager()
        tools = tool_manager.get_agent_tools(self.agent_name, self._mode)
        
        logger.debug(
            f"{self.__class__.__name__}: Loaded {len(tools)} tools "
            f"(mode={self._mode})"
        )
        
        return tools
    
    def _load_system_prompt(self) -> str:
        """
        Load system prompt for this agent from prompt manager.
        
        Returns:
            System prompt string customized for this agent and mode
            
        Note:
            This method accesses the prompt manager to retrieve agent-specific
            prompts. Subclasses can override to customize prompt loading.
        """
        from prompts.prompt_manager import get_agent_prompt
        
        system_prompt = get_agent_prompt(self.agent_name, self._mode)
        
        logger.debug(
            f"{self.__class__.__name__}: Loaded system prompt "
            f"({len(system_prompt)} chars, mode={self._mode})"
        )
        
        return system_prompt
    
    def _create_model(self):
        """
        Create LLM model instance for this agent.
        
        Returns:
            Configured LLM model instance
            
        Note:
            Uses ModelFactory to create model with provider-specific settings.
            Subclasses can override to customize model creation.
        """
        from llm.model_factory import ModelFactory
        
        model = ModelFactory.create_model(
            provider=self._provider,
            model_id=self._model_id,
            temperature=self._temperature
        )
        
        logger.debug(
            f"{self.__class__.__name__}: Created model "
            f"(provider={self._provider}, model_id={self._model_id})"
        )
        
        return model
    
    def _build_agent(self) -> Agent:
        """
        Build Strands Agent instance using Template Method pattern.
        
        This is the core template method that orchestrates agent creation.
        It coordinates the loading of tools, system prompt, model creation,
        and memory integration, then assembles them into a Strands Agent instance.
        
        Subclasses can override specific steps (_load_tools, _load_system_prompt,
        _create_model) while maintaining the overall creation process.
        
        Returns:
            Configured Strands Agent ready for use
            
        Note:
            This method is called by get_agent() on first access (lazy init).
        """
        logger.info(f"Building {self.__class__.__name__}...")
        
        # Load tools (step 1)
        if self._tools is None:
            self._tools = self._load_tools()
        
        # Load system prompt (step 2)
        if self._system_prompt is None:
            self._system_prompt = self._load_system_prompt()
        
        # Create model (step 3)
        if self._model is None:
            self._model = self._create_model()
        
        # Get agent-specific configuration (step 4)
        agent_config = self._get_agent_specific_config()
        
        # Add memory session manager if configured (step 5)
        if self._session_manager is not None:
            agent_config["memory"] = self._session_manager
            logger.info(
                f"{self.__class__.__name__}: Memory enabled "
                f"(config={self._memory_config.memory_id if self._memory_config else 'pre-configured'})"
            )
        
        # Create Strands Agent (step 6)
        agent = Agent(
            name=self.agent_name,
            model=self._model,
            system_prompt=self._system_prompt,
            tools=self._tools,
            **agent_config
        )
        
        logger.info(
            f"{self.__class__.__name__} built successfully "
            f"(tools={len(self._tools)}, mode={self._mode}, memory={self._session_manager is not None})"
        )
        
        return agent
    
    def get_agent(self) -> Agent:
        """
        Get Strands Agent instance with lazy initialization.
        
        On first call, builds the agent using _build_agent(). Subsequent calls
        return the cached instance.
        
        Returns:
            Configured Strands Agent ready for invocation
            
        Example:
            ```python
            agent_wrapper = AnalysisAgent(mode="workflow")
            strands_agent = agent_wrapper.get_agent()
            result = await strands_agent.ainvoke(input_data)
            ```
        """
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent
    
    async def ainvoke(self, input_data: Any) -> Any:
        """
        Invoke agent asynchronously.
        
        Convenience method that gets the Strands Agent and invokes it with
        the provided input data.
        
        Args:
            input_data: Input for agent (format depends on agent type)
            
        Returns:
            Agent execution result
            
        Example:
            ```python
            agent = ParserAgent(mode="workflow")
            result = await agent.ainvoke({
                "project_id": "uuid",
                "user_id": "uuid"
            })
            ```
        """
        agent = self.get_agent()
        return await agent.ainvoke(input_data)
    
    def with_memory(
        self,
        memory_config: MemoryConfig,
        session_id: str,
        user_id: str,
    ) -> "BaseAgent":
        """
        Create a new agent instance with memory configuration.
        
        This method creates a new instance of the agent with memory enabled,
        allowing agents to maintain context across invocations.
        
        Args:
            memory_config: Memory configuration for this agent
            session_id: Session identifier for memory context
            user_id: User identifier (actor_id for memory)
            
        Returns:
            New agent instance with memory configured
            
        Example:
            ```python
            # Create agent without memory
            agent = ParserAgent(mode="workflow")
            
            # Add memory configuration
            memory_config = get_memory_manager().create_workflow_memory_config(
                project_id="uuid",
                session_id="uuid"
            )
            
            agent_with_memory = agent.with_memory(
                memory_config=memory_config,
                session_id="uuid",
                user_id="uuid"
            )
            ```
        """
        # Create session manager
        memory_manager = get_memory_manager()
        session_manager = memory_manager.create_session_manager(
            config=memory_config,
            session_id=session_id,
            user_id=user_id,
        )
        
        # Create new instance with memory
        return self.__class__(
            mode=self._mode,
            provider=self._provider,
            model_id=self._model_id,
            temperature=self._temperature,
            memory_config=memory_config,
            session_manager=session_manager,
            **self._config
        )
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"mode={self._mode}, "
            f"provider={self._provider}, "
            f"model_id={self._model_id}, "
            f"memory={self._session_manager is not None}"
            f")"
        )
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self.__class__.__name__}[{self._mode}]"


__all__ = ["BaseAgent"]