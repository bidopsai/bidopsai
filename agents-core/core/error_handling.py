"""
Error handling utilities with recovery logic and error codes.

This module provides:
- Structured error types with error codes
- Retry policies with exponential backoff
- Error recovery strategies
- Error logging and reporting
"""

import asyncio
import logging
from enum import Enum
from typing import Optional, Callable, Any, TypeVar
from datetime import datetime
from functools import wraps

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorCode(str, Enum):
    """Standard error codes for the system"""
    
    # Database errors (1xxx)
    DATABASE_CONNECTION_ERROR = "DB_1001"
    DATABASE_QUERY_ERROR = "DB_1002"
    DATABASE_TIMEOUT = "DB_1003"
    
    # LLM errors (2xxx)
    LLM_TIMEOUT = "LLM_2001"
    LLM_RATE_LIMIT = "LLM_2002"
    LLM_INVALID_RESPONSE = "LLM_2003"
    LLM_CONTEXT_LENGTH_EXCEEDED = "LLM_2004"
    LLM_MODEL_NOT_FOUND = "LLM_2005"
    
    # S3 errors (3xxx)
    S3_UPLOAD_FAILED = "S3_3001"
    S3_DOWNLOAD_FAILED = "S3_3002"
    S3_BUCKET_NOT_FOUND = "S3_3003"
    S3_ACCESS_DENIED = "S3_3004"
    S3_THROTTLING = "S3_3005"
    
    # Agent errors (4xxx)
    AGENT_EXECUTION_FAILED = "AGENT_4001"
    AGENT_TIMEOUT = "AGENT_4002"
    AGENT_INVALID_INPUT = "AGENT_4003"
    AGENT_INVALID_OUTPUT = "AGENT_4004"
    
    # Workflow errors (5xxx)
    WORKFLOW_EXECUTION_FAILED = "WORKFLOW_5001"
    WORKFLOW_STATE_INVALID = "WORKFLOW_5002"
    WORKFLOW_TIMEOUT = "WORKFLOW_5003"
    
    # Integration errors (6xxx)
    MCP_CONNECTION_FAILED = "MCP_6001"
    MCP_TOOL_EXECUTION_FAILED = "MCP_6002"
    SLACK_API_ERROR = "SLACK_6003"
    EMAIL_SEND_FAILED = "EMAIL_6004"
    BEDROCK_DA_ERROR = "BEDROCK_DA_6005"
    
    # Validation errors (7xxx)
    VALIDATION_ERROR = "VAL_7001"
    SCHEMA_VALIDATION_ERROR = "VAL_7002"
    
    # General errors (9xxx)
    UNKNOWN_ERROR = "ERR_9001"
    CONFIGURATION_ERROR = "ERR_9002"
    PERMISSION_DENIED = "ERR_9003"


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    CRITICAL = "critical"  # System failure, requires immediate action
    HIGH = "high"          # Agent failure, requires intervention
    MEDIUM = "medium"      # Recoverable error, automatic retry possible
    LOW = "low"            # Warning, doesn't block execution


class AgentError(Exception):
    """
    Base exception for agent system errors.
    
    Attributes:
        error_code: Standardized error code
        message: Human-readable error message
        severity: Error severity level
        recoverable: Whether error is recoverable via retry
        retry_after_seconds: Suggested retry delay
        context: Additional error context
    """
    
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recoverable: bool = True,
        retry_after_seconds: Optional[int] = None,
        **context
    ):
        self.error_code = error_code
        self.message = message
        self.severity = severity
        self.recoverable = recoverable
        self.retry_after_seconds = retry_after_seconds
        self.context = context
        self.timestamp = datetime.now()
        
        super().__init__(message)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "severity": self.severity.value,
            "recoverable": self.recoverable,
            "retry_after_seconds": self.retry_after_seconds,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context
        }


class RetryPolicy(BaseModel):
    """Retry policy configuration"""
    max_retries: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0     # seconds
    exponential_base: float = 2.0
    jitter: bool = True


class RetryableError(AgentError):
    """Error that should trigger automatic retry"""
    
    def __init__(self, error_code: ErrorCode, message: str, **context):
        super().__init__(
            error_code=error_code,
            message=message,
            severity=ErrorSeverity.MEDIUM,
            recoverable=True,
            **context
        )


class NonRetryableError(AgentError):
    """Error that should not trigger automatic retry"""
    
    def __init__(self, error_code: ErrorCode, message: str, severity: ErrorSeverity = ErrorSeverity.HIGH, **context):
        super().__init__(
            error_code=error_code,
            message=message,
            severity=severity,
            recoverable=False,
            **context
        )


def is_transient_error(error: Exception) -> bool:
    """
    Determine if error is transient and should be retried.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is transient
    """
    # Network/connection errors are typically transient
    transient_errors = (
        "timeout",
        "connection",
        "throttl",
        "rate limit",
        "too many requests",
        "service unavailable",
        "gateway timeout"
    )
    
    error_str = str(error).lower()
    return any(term in error_str for term in transient_errors)


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    policy: Optional[RetryPolicy] = None,
    **kwargs
) -> T:
    """
    Execute function with exponential backoff retry.
    
    Args:
        func: Async function to execute
        *args: Function arguments
        policy: Retry policy (uses default if None)
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
        
    Raises:
        Last exception if all retries exhausted
    """
    if policy is None:
        policy = RetryPolicy()
    
    last_exception = None
    delay = policy.initial_delay
    
    for attempt in range(policy.max_retries + 1):
        try:
            return await func(*args, **kwargs)
            
        except Exception as e:
            last_exception = e
            
            # Check if error is retryable
            if isinstance(e, NonRetryableError):
                logger.error(f"Non-retryable error: {e}")
                raise
            
            if attempt >= policy.max_retries:
                logger.error(
                    f"Max retries ({policy.max_retries}) exhausted for {func.__name__}",
                    extra={"error": str(e)}
                )
                raise
            
            # Check if error is transient
            if not (isinstance(e, RetryableError) or is_transient_error(e)):
                logger.warning(f"Error doesn't appear transient, not retrying: {e}")
                raise
            
            # Calculate delay with jitter
            if policy.jitter:
                import random
                jitter_delay = delay * (0.5 + random.random())
            else:
                jitter_delay = delay
            
            logger.warning(
                f"Attempt {attempt + 1}/{policy.max_retries + 1} failed for {func.__name__}. "
                f"Retrying in {jitter_delay:.2f}s...",
                extra={"error": str(e), "attempt": attempt + 1}
            )
            
            await asyncio.sleep(jitter_delay)
            
            # Exponential backoff
            delay = min(delay * policy.exponential_base, policy.max_delay)
    
    # Should never reach here, but just in case
    raise last_exception  # type: ignore


def with_retry(policy: Optional[RetryPolicy] = None):
    """
    Decorator to add retry logic to async functions.
    
    Usage:
        @with_retry(RetryPolicy(max_retries=5))
        async def fetch_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(func, *args, policy=policy, **kwargs)
        return wrapper
    return decorator


def handle_error(
    error: Exception,
    agent_name: Optional[str] = None,
    task_id: Optional[str] = None,
    **context
) -> AgentError:
    """
    Convert generic exception to AgentError with appropriate error code.
    
    Args:
        error: Original exception
        agent_name: Name of agent that raised error
        task_id: Task ID
        **context: Additional context
        
    Returns:
        AgentError instance
    """
    error_str = str(error).lower()
    
    # Determine error code and severity
    if "database" in error_str or "psycopg" in error_str:
        if "timeout" in error_str:
            error_code = ErrorCode.DATABASE_TIMEOUT
        elif "connection" in error_str:
            error_code = ErrorCode.DATABASE_CONNECTION_ERROR
        else:
            error_code = ErrorCode.DATABASE_QUERY_ERROR
        severity = ErrorSeverity.HIGH
        recoverable = True
        
    elif "s3" in error_str or "boto" in error_str:
        if "throttl" in error_str or "rate limit" in error_str:
            error_code = ErrorCode.S3_THROTTLING
            severity = ErrorSeverity.MEDIUM
            recoverable = True
        elif "access denied" in error_str or "forbidden" in error_str:
            error_code = ErrorCode.S3_ACCESS_DENIED
            severity = ErrorSeverity.HIGH
            recoverable = False
        else:
            error_code = ErrorCode.S3_UPLOAD_FAILED
            severity = ErrorSeverity.MEDIUM
            recoverable = True
            
    elif "bedrock" in error_str or "llm" in error_str or "model" in error_str:
        if "timeout" in error_str:
            error_code = ErrorCode.LLM_TIMEOUT
            severity = ErrorSeverity.MEDIUM
            recoverable = True
        elif "rate limit" in error_str or "throttl" in error_str:
            error_code = ErrorCode.LLM_RATE_LIMIT
            severity = ErrorSeverity.MEDIUM
            recoverable = True
        elif "context length" in error_str or "token" in error_str:
            error_code = ErrorCode.LLM_CONTEXT_LENGTH_EXCEEDED
            severity = ErrorSeverity.HIGH
            recoverable = False
        else:
            error_code = ErrorCode.LLM_INVALID_RESPONSE
            severity = ErrorSeverity.MEDIUM
            recoverable = True
            
    elif "validation" in error_str or "pydantic" in error_str:
        error_code = ErrorCode.VALIDATION_ERROR
        severity = ErrorSeverity.HIGH
        recoverable = False
        
    else:
        error_code = ErrorCode.UNKNOWN_ERROR
        severity = ErrorSeverity.MEDIUM
        recoverable = True
    
    # Build context
    error_context = {
        "agent_name": agent_name,
        "task_id": task_id,
        "original_error": str(error),
        "error_type": type(error).__name__,
        **context
    }
    
    agent_error = AgentError(
        error_code=error_code,
        message=str(error),
        severity=severity,
        recoverable=recoverable,
        **error_context
    )
    
    # Log error
    log_level = logging.ERROR if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH] else logging.WARNING
    logger.log(
        log_level,
        f"Error handled: {error_code.value} - {str(error)}",
        extra=agent_error.to_dict()
    )
    
    return agent_error


class ErrorRecoveryStrategy:
    """Strategy for recovering from errors"""
    
    @staticmethod
    async def reset_and_retry(
        func: Callable,
        cleanup_func: Optional[Callable] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Reset state and retry operation.
        
        Args:
            func: Function to retry
            cleanup_func: Optional cleanup function to run before retry
            *args: Function arguments
            **kwargs: Function keyword arguments
        """
        if cleanup_func:
            try:
                await cleanup_func()
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")
        
        return await func(*args, **kwargs)
    
    @staticmethod
    async def skip_and_continue(
        error: AgentError,
        default_value: Optional[Any] = None
    ) -> Any:
        """
        Skip failed operation and continue with default value.
        
        Args:
            error: Error that occurred
            default_value: Default value to return
        """
        logger.warning(
            f"Skipping failed operation: {error.error_code}",
            extra=error.to_dict()
        )
        return default_value
    
    @staticmethod
    async def escalate_to_human(
        error: AgentError,
        workflow_execution_id: str,
        project_id: str
    ):
        """
        Escalate error to human for manual intervention.
        
        Args:
            error: Error that occurred
            workflow_execution_id: Workflow execution ID
            project_id: Project ID
        """
        logger.critical(
            f"Escalating to human: {error.error_code}",
            extra={
                **error.to_dict(),
                "workflow_execution_id": workflow_execution_id,
                "project_id": project_id,
                "requires_human_intervention": True
            }
        )
        # In production, send notification via SSE and/or Slack


# Convenience functions for common error scenarios
def database_error(message: str, **context) -> AgentError:
    """Create database error"""
    return AgentError(
        ErrorCode.DATABASE_QUERY_ERROR,
        message,
        severity=ErrorSeverity.HIGH,
        **context
    )


def llm_error(message: str, recoverable: bool = True, **context) -> AgentError:
    """Create LLM error"""
    return AgentError(
        ErrorCode.LLM_INVALID_RESPONSE,
        message,
        severity=ErrorSeverity.MEDIUM,
        recoverable=recoverable,
        **context
    )


def validation_error(message: str, **context) -> AgentError:
    """Create validation error"""
    return NonRetryableError(
        ErrorCode.VALIDATION_ERROR,
        message,
        severity=ErrorSeverity.HIGH,
        **context
    )