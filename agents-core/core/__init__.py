"""
Core utilities for the BidOpsAI agent system.

This module provides essential infrastructure:
- Database connection pooling
- SSE event streaming
- Configuration management
- Memory management
- Observability and tracing
- Error handling and retry logic
"""

from core.database import (
    db_pool,
    init_database,
    close_database,
    transaction,
    DatabaseConnectionError
)

from core.sse_manager import (
    sse_manager,
    create_sse_response,
    SSEEvent
)

from core.config import (
    get_config,
    get_agent_config,
    get_secret,
    clear_config_cache,
    AppConfig,
    AgentConfiguration
)

from core.memory import (
    MemoryScope,
    MemoryType,
    MemoryConfig,
    MemoryManager,
    get_memory_manager
)

from core.observability import (
    observability,
    init_observability,
    trace_workflow,
    trace_agent,
    log_with_context,
    TraceMetadata,
    PerformanceMetrics
)

from core.error_handling import (
    AgentError,
    RetryableError,
    NonRetryableError,
    ErrorCode,
    ErrorSeverity,
    RetryPolicy,
    retry_with_backoff,
    with_retry,
    handle_error,
    ErrorRecoveryStrategy,
    database_error,
    llm_error,
    validation_error
)

__all__ = [
    # Database
    "db_pool",
    "init_database",
    "close_database",
    "transaction",
    "DatabaseConnectionError",
    
    # SSE
    "sse_manager",
    "create_sse_response",
    "SSEEvent",
    
    # Config
    "get_config",
    "get_agent_config",
    "get_secret",
    "clear_config_cache",
    "AppConfig",
    "AgentConfiguration",
    
    # Memory (Phase 4 - AWS AgentCore Memory)
    "MemoryScope",
    "MemoryType",
    "MemoryConfig",
    "MemoryManager",
    "get_memory_manager",
    
    # Observability
    "observability",
    "init_observability",
    "trace_workflow",
    "trace_agent",
    "log_with_context",
    "TraceMetadata",
    "PerformanceMetrics",
    
    # Error Handling
    "AgentError",
    "RetryableError",
    "NonRetryableError",
    "ErrorCode",
    "ErrorSeverity",
    "RetryPolicy",
    "retry_with_backoff",
    "with_retry",
    "handle_error",
    "ErrorRecoveryStrategy",
    "database_error",
    "llm_error",
    "validation_error",
]