"""
AgentCore Memory Integration Module

Provides memory management for AWS AgentCore runtime integration with Strands agents.
Implements both short-term (session-based) and long-term (persistent insights) memory
using AWS AgentCore Memory service.

Memory Types:
- Workflow Memory: Execution context across agent handoffs
- Project Memory: Artifacts and documents for project lifecycle  
- User Preference Memory: User feedback patterns and preferences
- Agent Learning Memory: Compliance/QA patterns for improvement

Architecture:
- Uses AgentCoreMemorySessionManager for Strands integration
- Implements built-in memory strategies (summaries, preferences, facts)
- Supports both short-term (events) and long-term (records) memory
- Provides graceful fallback when memory service unavailable

Reference:
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/best-practices.html
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class MemoryScope(str, Enum):
    """Memory scope determines memory lifecycle and access patterns."""
    SESSION = "session"  # Short-term, tied to session_id
    PROJECT = "project"  # Medium-term, tied to project_id
    USER = "user"  # Long-term, tied to user_id
    AGENT = "agent"  # Long-term, tied to agent_name
    GLOBAL = "global"  # System-wide insights


class MemoryType(str, Enum):
    """Memory type determines storage strategy."""
    WORKFLOW = "workflow"  # Workflow execution context
    PROJECT = "project"  # Project artifacts and documents
    USER_PREFERENCE = "user_preference"  # User feedback patterns
    AGENT_LEARNING = "agent_learning"  # Agent performance insights


class MemoryConfig:
    """
    Configuration for AgentCore Memory integration.
    
    Attributes:
        memory_id: Unique identifier for memory store
        scope: Memory lifecycle scope (session/project/user/agent/global)
        memory_type: Type of memory (workflow/project/user_preference/agent_learning)
        ttl_seconds: Time-to-live in seconds (None = no expiration)
        enable_summaries: Enable automatic summarization strategy
        enable_preferences: Enable preference extraction strategy
        enable_facts: Enable fact extraction strategy
    """
    
    def __init__(
        self,
        memory_id: str,
        scope: MemoryScope = MemoryScope.SESSION,
        memory_type: MemoryType = MemoryType.WORKFLOW,
        ttl_seconds: Optional[int] = None,
        enable_summaries: bool = True,
        enable_preferences: bool = False,
        enable_facts: bool = False,
    ):
        self.memory_id = memory_id
        self.scope = scope
        self.memory_type = memory_type
        self.ttl_seconds = ttl_seconds
        self.enable_summaries = enable_summaries
        self.enable_preferences = enable_preferences
        self.enable_facts = enable_facts
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            "memory_id": self.memory_id,
            "scope": self.scope.value,
            "memory_type": self.memory_type.value,
            "ttl_seconds": self.ttl_seconds,
            "enable_summaries": self.enable_summaries,
            "enable_preferences": self.enable_preferences,
            "enable_facts": self.enable_facts,
        }


class MemoryManager:
    """
    Manages AgentCore Memory for all agents in the system.
    
    Provides factory methods for creating memory configurations and session managers
    for different memory types and scopes.
    
    Usage:
        ```python
        # Initialize memory manager
        manager = MemoryManager()
        
        # Create workflow memory config
        config = manager.create_workflow_memory_config(
            project_id="uuid",
            session_id="uuid"
        )
        
        # Create session manager for agent
        session_manager = manager.create_session_manager(
            config=config,
            session_id="uuid",
            user_id="uuid"
        )
        ```
    """
    
    def __init__(self, enable_memory: bool = True):
        """
        Initialize memory manager.
        
        Args:
            enable_memory: Enable/disable memory service integration
        """
        self._enable_memory = enable_memory
        self._memory_client = None
        
        if self._enable_memory:
            self._initialize_memory_client()
    
    def _initialize_memory_client(self) -> None:
        """
        Initialize AgentCore Memory client.
        
        Note:
            This method attempts to import and initialize the AgentCore Memory client.
            If unavailable, logs warning and disables memory features.
        """
        try:
            # Import AgentCore Memory SDK components
            from strands.memory import AgentCoreMemoryClient
            
            self._memory_client = AgentCoreMemoryClient()
            logger.info("AgentCore Memory client initialized successfully")
            
        except ImportError as e:
            logger.warning(
                f"AgentCore Memory SDK not available: {e}. "
                "Memory features will be disabled."
            )
            self._enable_memory = False
        except Exception as e:
            logger.error(
                f"Failed to initialize AgentCore Memory client: {e}. "
                "Memory features will be disabled."
            )
            self._enable_memory = False
    
    def is_memory_enabled(self) -> bool:
        """Check if memory service is enabled and available."""
        return self._enable_memory and self._memory_client is not None
    
    def create_workflow_memory_config(
        self,
        project_id: str,
        session_id: str,
        ttl_hours: int = 24,
    ) -> MemoryConfig:
        """
        Create memory configuration for workflow execution.
        
        Workflow memory stores:
        - Agent execution history and handoffs
        - Task statuses and outputs
        - User feedback and decisions
        - Error logs and recovery actions
        
        Args:
            project_id: Unique project identifier
            session_id: Session identifier for this workflow execution
            ttl_hours: Time-to-live in hours (default: 24 hours)
            
        Returns:
            MemoryConfig for workflow execution
        """
        memory_id = f"workflow_{project_id}_{session_id}"
        
        return MemoryConfig(
            memory_id=memory_id,
            scope=MemoryScope.SESSION,
            memory_type=MemoryType.WORKFLOW,
            ttl_seconds=ttl_hours * 3600,
            enable_summaries=True,  # Summarize workflow progress
            enable_preferences=False,
            enable_facts=True,  # Extract key decisions and outcomes
        )
    
    def create_project_memory_config(
        self,
        project_id: str,
        ttl_days: int = 90,
    ) -> MemoryConfig:
        """
        Create memory configuration for project lifecycle.
        
        Project memory stores:
        - Artifact metadata and locations
        - Document processing results
        - Compliance and QA feedback history
        - Project stakeholder information
        
        Args:
            project_id: Unique project identifier
            ttl_days: Time-to-live in days (default: 90 days)
            
        Returns:
            MemoryConfig for project lifecycle
        """
        memory_id = f"project_{project_id}"
        
        return MemoryConfig(
            memory_id=memory_id,
            scope=MemoryScope.PROJECT,
            memory_type=MemoryType.PROJECT,
            ttl_seconds=ttl_days * 86400,
            enable_summaries=True,  # Summarize project artifacts
            enable_preferences=False,
            enable_facts=True,  # Extract key project details
        )
    
    def create_user_preference_memory_config(
        self,
        user_id: str,
        ttl_days: int = 365,
    ) -> MemoryConfig:
        """
        Create memory configuration for user preferences.
        
        User preference memory stores:
        - Feedback patterns and preferences
        - Common edit types and styles
        - Approval/rejection patterns
        - Communication preferences
        
        Args:
            user_id: Unique user identifier
            ttl_days: Time-to-live in days (default: 365 days)
            
        Returns:
            MemoryConfig for user preferences
        """
        memory_id = f"user_pref_{user_id}"
        
        return MemoryConfig(
            memory_id=memory_id,
            scope=MemoryScope.USER,
            memory_type=MemoryType.USER_PREFERENCE,
            ttl_seconds=ttl_days * 86400,
            enable_summaries=False,
            enable_preferences=True,  # Extract user preferences
            enable_facts=True,  # Extract preference facts
        )
    
    def create_agent_learning_memory_config(
        self,
        agent_name: str,
        ttl_days: Optional[int] = None,
    ) -> MemoryConfig:
        """
        Create memory configuration for agent learning.
        
        Agent learning memory stores:
        - Compliance check patterns and rules
        - QA check patterns and common issues
        - Successful artifact structures
        - Error patterns and resolutions
        
        Args:
            agent_name: Name of the agent (parser, analysis, compliance, qa, etc.)
            ttl_days: Time-to-live in days (None = no expiration for learning data)
            
        Returns:
            MemoryConfig for agent learning
        """
        memory_id = f"agent_learning_{agent_name}"
        
        return MemoryConfig(
            memory_id=memory_id,
            scope=MemoryScope.AGENT,
            memory_type=MemoryType.AGENT_LEARNING,
            ttl_seconds=ttl_days * 86400 if ttl_days else None,
            enable_summaries=True,  # Summarize learning patterns
            enable_preferences=False,
            enable_facts=True,  # Extract learned facts
        )
    
    def create_session_manager(
        self,
        config: MemoryConfig,
        session_id: str,
        user_id: str,
    ):
        """
        Create AgentCoreMemorySessionManager for Strands agent integration.
        
        Args:
            config: Memory configuration
            session_id: Session identifier
            user_id: User identifier (actor_id)
            
        Returns:
            AgentCoreMemorySessionManager instance or None if memory disabled
            
        Example:
            ```python
            config = manager.create_workflow_memory_config(project_id, session_id)
            session_manager = manager.create_session_manager(config, session_id, user_id)
            
            # Pass to Strands Agent
            agent = Agent(
                name="parser",
                model=model,
                system_prompt=prompt,
                tools=tools,
                memory=session_manager
            )
            ```
        """
        if not self.is_memory_enabled():
            logger.warning(
                f"Memory disabled - cannot create session manager for {config.memory_id}"
            )
            return None
        
        try:
            from strands.memory import AgentCoreMemorySessionManager
            
            # Create memory strategies based on config
            strategies = []
            
            if config.enable_summaries:
                from strands.memory.strategies import SummaryStrategy
                strategies.append(SummaryStrategy())
            
            if config.enable_preferences:
                from strands.memory.strategies import PreferenceStrategy
                strategies.append(PreferenceStrategy())
            
            if config.enable_facts:
                from strands.memory.strategies import FactStrategy
                strategies.append(FactStrategy())
            
            # Create session manager
            session_manager = AgentCoreMemorySessionManager(
                memory_id=config.memory_id,
                session_id=session_id,
                actor_id=user_id,
                client=self._memory_client,
                strategies=strategies,
                ttl_seconds=config.ttl_seconds,
            )
            
            logger.info(
                f"Created session manager: {config.memory_id} "
                f"(scope={config.scope.value}, type={config.memory_type.value})"
            )
            
            return session_manager
            
        except Exception as e:
            logger.error(
                f"Failed to create session manager for {config.memory_id}: {e}"
            )
            return None
    
    def create_multi_scope_session_managers(
        self,
        project_id: str,
        session_id: str,
        user_id: str,
        agent_name: str,
    ) -> Dict[str, Any]:
        """
        Create multiple session managers for different memory scopes.
        
        This is useful for agents that need to access multiple memory types
        simultaneously (e.g., workflow context + project artifacts + user preferences).
        
        Args:
            project_id: Unique project identifier
            session_id: Session identifier
            user_id: User identifier
            agent_name: Name of the agent
            
        Returns:
            Dictionary with session managers for each scope
            
        Example:
            ```python
            managers = memory_manager.create_multi_scope_session_managers(
                project_id="uuid",
                session_id="uuid",
                user_id="uuid",
                agent_name="analysis"
            )
            
            # Access specific memory types
            workflow_memory = managers["workflow"]
            project_memory = managers["project"]
            user_memory = managers["user_preference"]
            agent_memory = managers["agent_learning"]
            ```
        """
        managers = {}
        
        # Workflow memory (session scope)
        workflow_config = self.create_workflow_memory_config(project_id, session_id)
        managers["workflow"] = self.create_session_manager(
            workflow_config, session_id, user_id
        )
        
        # Project memory (project scope)
        project_config = self.create_project_memory_config(project_id)
        managers["project"] = self.create_session_manager(
            project_config, session_id, user_id
        )
        
        # User preference memory (user scope)
        user_config = self.create_user_preference_memory_config(user_id)
        managers["user_preference"] = self.create_session_manager(
            user_config, session_id, user_id
        )
        
        # Agent learning memory (agent scope)
        agent_config = self.create_agent_learning_memory_config(agent_name)
        managers["agent_learning"] = self.create_session_manager(
            agent_config, session_id, user_id
        )
        
        logger.info(
            f"Created multi-scope session managers for {agent_name}: "
            f"{list(managers.keys())}"
        )
        
        return managers


# Global memory manager instance (singleton pattern)
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """
    Get global memory manager instance (singleton).
    
    Returns:
        MemoryManager instance
        
    Example:
        ```python
        from core.memory import get_memory_manager
        
        manager = get_memory_manager()
        config = manager.create_workflow_memory_config(project_id, session_id)
        ```
    """
    global _memory_manager
    
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    
    return _memory_manager


__all__ = [
    "MemoryScope",
    "MemoryType",
    "MemoryConfig",
    "MemoryManager",
    "get_memory_manager",
]