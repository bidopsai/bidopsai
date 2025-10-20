"""
Enhanced Error Recovery System for Phase 8.

This module extends the base error_handling.py with:
- Idempotency patterns for DB and S3 operations
- Workflow timeout enforcement
- Manual intervention flows
- Enhanced error event emission
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, TypeVar
from uuid import UUID
from functools import wraps

from core.error_handling import (
    AgentError,
    ErrorCode,
    ErrorSeverity,
    retry_with_backoff,
    RetryPolicy,
    is_transient_error
)
from core.sse_manager import sse_manager
from core.database import db_pool

logger = logging.getLogger(__name__)

T = TypeVar('T')


class WorkflowTimeoutError(AgentError):
    """Raised when workflow exceeds maximum execution time."""
    
    def __init__(self, workflow_id: UUID, elapsed_minutes: float):
        super().__init__(
            error_code=ErrorCode.WORKFLOW_TIMEOUT,
            message=f"Workflow {workflow_id} exceeded 60-minute timeout (elapsed: {elapsed_minutes:.1f}m)",
            severity=ErrorSeverity.HIGH,
            recoverable=False,
            workflow_id=str(workflow_id),
            elapsed_minutes=elapsed_minutes
        )


class IdempotencyManager:
    """
    Manages idempotent operations to prevent duplicate executions.
    
    Uses operation keys and database locking to ensure operations
    execute exactly once even with retries.
    """
    
    @staticmethod
    async def with_idempotency(
        operation_key: str,
        func: Callable,
        *args,
        ttl_seconds: int = 3600,
        **kwargs
    ) -> Any:
        """
        Execute function with idempotency guarantee.
        
        Args:
            operation_key: Unique key for this operation
            func: Function to execute
            *args: Function arguments
            ttl_seconds: Time-to-live for idempotency record
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or cached result if already executed
        """
        # Check if operation already completed
        cached_result = await IdempotencyManager._get_cached_result(operation_key)
        
        if cached_result is not None:
            logger.info(f"Idempotency: Operation {operation_key} already completed, returning cached result")
            return cached_result
        
        # Acquire lock to prevent concurrent execution
        lock_acquired = await IdempotencyManager._acquire_lock(operation_key, ttl_seconds)
        
        if not lock_acquired:
            # Another process is executing, wait and retry
            logger.warning(f"Idempotency: Lock already held for {operation_key}, waiting...")
            await asyncio.sleep(1)
            return await IdempotencyManager.with_idempotency(
                operation_key, func, *args, ttl_seconds=ttl_seconds, **kwargs
            )
        
        try:
            # Execute operation
            result = await func(*args, **kwargs)
            
            # Cache result
            await IdempotencyManager._cache_result(operation_key, result, ttl_seconds)
            
            return result
            
        finally:
            # Release lock
            await IdempotencyManager._release_lock(operation_key)
    
    @staticmethod
    async def _get_cached_result(operation_key: str) -> Optional[Any]:
        """Get cached result for operation."""
        try:
            query = """
                SELECT result_data, expires_at
                FROM idempotency_cache
                WHERE operation_key = $1
            """
            row = await db_pool.fetchrow(query, operation_key)
            
            if row:
                # Check expiration
                if row['expires_at'] and row['expires_at'] < datetime.utcnow():
                    # Expired, delete
                    await db_pool.execute(
                        "DELETE FROM idempotency_cache WHERE operation_key = $1",
                        operation_key
                    )
                    return None
                
                return row['result_data']
            
        except Exception as e:
            # Table might not exist or other error, continue without cache
            logger.debug(f"Idempotency cache query failed: {e}")
        
        return None
    
    @staticmethod
    async def _cache_result(operation_key: str, result: Any, ttl_seconds: int) -> None:
        """Cache operation result."""
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            
            query = """
                INSERT INTO idempotency_cache (operation_key, result_data, expires_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (operation_key) DO UPDATE
                SET result_data = EXCLUDED.result_data,
                    expires_at = EXCLUDED.expires_at,
                    updated_at = NOW()
            """
            await db_pool.execute(query, operation_key, result, expires_at)
            
        except Exception as e:
            # Non-critical, log and continue
            logger.warning(f"Failed to cache result for {operation_key}: {e}")
    
    @staticmethod
    async def _acquire_lock(operation_key: str, ttl_seconds: int) -> bool:
        """Acquire distributed lock for operation."""
        try:
            # Use PostgreSQL advisory locks or simple row locks
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            
            query = """
                INSERT INTO operation_locks (operation_key, expires_at)
                VALUES ($1, $2)
                ON CONFLICT (operation_key) DO NOTHING
                RETURNING operation_key
            """
            result = await db_pool.fetchrow(query, operation_key, expires_at)
            
            return result is not None
            
        except Exception as e:
            logger.warning(f"Failed to acquire lock for {operation_key}: {e}")
            return False
    
    @staticmethod
    async def _release_lock(operation_key: str) -> None:
        """Release distributed lock."""
        try:
            await db_pool.execute(
                "DELETE FROM operation_locks WHERE operation_key = $1",
                operation_key
            )
        except Exception as e:
            logger.warning(f"Failed to release lock for {operation_key}: {e}")


class WorkflowTimeoutManager:
    """Manages workflow execution timeouts."""
    
    MAX_WORKFLOW_DURATION_MINUTES = 60
    
    @staticmethod
    async def check_timeout(
        workflow_execution_id: UUID,
        started_at: datetime
    ) -> None:
        """
        Check if workflow has exceeded timeout.
        
        Args:
            workflow_execution_id: Workflow ID
            started_at: When workflow started
            
        Raises:
            WorkflowTimeoutError: If timeout exceeded
        """
        elapsed = datetime.utcnow() - started_at
        elapsed_minutes = elapsed.total_seconds() / 60
        
        if elapsed_minutes > WorkflowTimeoutManager.MAX_WORKFLOW_DURATION_MINUTES:
            raise WorkflowTimeoutError(workflow_execution_id, elapsed_minutes)
        
        # Log warning at 50 minutes
        if elapsed_minutes > 50 and elapsed_minutes < 51:
            logger.warning(
                f"Workflow {workflow_execution_id} approaching timeout "
                f"({elapsed_minutes:.1f}/{WorkflowTimeoutManager.MAX_WORKFLOW_DURATION_MINUTES} minutes)"
            )
    
    @staticmethod
    def with_timeout(timeout_minutes: int = 60):
        """
        Decorator to enforce timeout on async functions.
        
        Usage:
            @with_timeout(60)
            async def execute_workflow():
                ...
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout_minutes * 60
                    )
                except asyncio.TimeoutError as e:
                    raise WorkflowTimeoutError(
                        workflow_id=UUID(int=0),  # Will be set by caller
                        elapsed_minutes=timeout_minutes
                    ) from e
            return wrapper
        return decorator


async def emit_error_event(
    error: AgentError,
    workflow_execution_id: UUID,
    project_id: UUID,
    session_id: str,
    agent_name: Optional[str] = None
) -> None:
    """
    Emit detailed error SSE event with recovery options.
    
    Args:
        error: The error that occurred
        workflow_execution_id: Workflow ID
        project_id: Project ID
        session_id: Session ID for SSE
        agent_name: Name of agent where error occurred
    """
    # Determine recovery actions
    recovery_actions = []
    
    if error.recoverable:
        recovery_actions.append("retry")
    
    if error.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
        recovery_actions.append("escalate_to_human")
    
    if is_transient_error(error):
        recovery_actions.append("wait_and_retry")
    
    # Build error event data
    event_data = {
        "error_code": error.error_code.value,
        "error_message": error.message,
        "severity": error.severity.value,
        "is_recoverable": error.recoverable,
        "recovery_actions": recovery_actions,
        "affected_component": agent_name or "workflow_supervisor",
        "retry_after_seconds": error.retry_after_seconds,
        "context": error.context,
        "timestamp": error.timestamp.isoformat()
    }
    
    # Send error event via SSE
    await sse_manager.send_event(
        event_type="error_occurred",
        data=event_data,
        workflow_execution_id=workflow_execution_id,
        project_id=project_id,
        session_id=session_id,
        persist=True
    )
    
    logger.error(
        f"Error event emitted: {error.error_code.value} - {error.message}",
        extra={
            "workflow_id": str(workflow_execution_id),
            "error_details": error.to_dict()
        }
    )


async def execute_with_recovery(
    func: Callable,
    *args,
    workflow_execution_id: UUID,
    project_id: UUID,
    session_id: str,
    agent_name: str,
    retry_policy: Optional[RetryPolicy] = None,
    enable_idempotency: bool = True,
    **kwargs
) -> Any:
    """
    Execute function with comprehensive error recovery.
    
    Features:
    - Automatic retry for transient errors
    - Idempotency for DB/S3 operations
    - Error event emission
    - Manual intervention flow for critical errors
    
    Args:
        func: Function to execute
        *args: Function arguments
        workflow_execution_id: Workflow ID
        project_id: Project ID
        session_id: Session ID
        agent_name: Agent name for error tracking
        retry_policy: Retry policy (uses default if None)
        enable_idempotency: Enable idempotency checks
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
    """
    # Generate idempotency key
    operation_key = f"workflow:{workflow_execution_id}:agent:{agent_name}:{func.__name__}"
    
    async def wrapped_execution():
        try:
            # Execute with retry
            return await retry_with_backoff(
                func,
                *args,
                policy=retry_policy,
                **kwargs
            )
            
        except AgentError as e:
            # Emit error event
            await emit_error_event(
                error=e,
                workflow_execution_id=workflow_execution_id,
                project_id=project_id,
                session_id=session_id,
                agent_name=agent_name
            )
            
            # If not recoverable, escalate
            if not e.recoverable or e.severity == ErrorSeverity.CRITICAL:
                await _escalate_to_human(
                    error=e,
                    workflow_execution_id=workflow_execution_id,
                    project_id=project_id,
                    session_id=session_id,
                    agent_name=agent_name
                )
            
            raise
            
        except Exception as e:
            # Convert to AgentError
            from core.error_handling import handle_error
            agent_error = handle_error(
                error=e,
                agent_name=agent_name,
                workflow_id=str(workflow_execution_id)
            )
            
            # Emit error event
            await emit_error_event(
                error=agent_error,
                workflow_execution_id=workflow_execution_id,
                project_id=project_id,
                session_id=session_id,
                agent_name=agent_name
            )
            
            raise agent_error from e
    
    # Execute with or without idempotency
    if enable_idempotency:
        return await IdempotencyManager.with_idempotency(
            operation_key,
            wrapped_execution
        )
    else:
        return await wrapped_execution()


async def _escalate_to_human(
    error: AgentError,
    workflow_execution_id: UUID,
    project_id: UUID,
    session_id: str,
    agent_name: str
) -> None:
    """
    Escalate error to human for manual intervention.
    
    Args:
        error: The error
        workflow_execution_id: Workflow ID
        project_id: Project ID
        session_id: Session ID
        agent_name: Agent name
    """
    event_data = {
        "requires_manual_intervention": True,
        "error_code": error.error_code.value,
        "error_message": error.message,
        "severity": error.severity.value,
        "affected_agent": agent_name,
        "suggested_actions": [
            "Review error details in logs",
            "Check system resources and connections",
            "Contact support if issue persists",
            "Retry workflow from last checkpoint"
        ],
        "support_info": {
            "workflow_id": str(workflow_execution_id),
            "project_id": str(project_id),
            "timestamp": datetime.utcnow().isoformat(),
            "error_context": error.context
        }
    }
    
    # Send escalation event
    await sse_manager.send_event(
        event_type="manual_intervention_required",
        data=event_data,
        workflow_execution_id=workflow_execution_id,
        project_id=project_id,
        session_id=session_id,
        persist=True
    )
    
    logger.critical(
        f"Manual intervention required for workflow {workflow_execution_id}",
        extra={
            "error": error.to_dict(),
            "agent": agent_name
        }
    )


# Convenience decorators
def with_error_recovery(
    agent_name: str,
    retry_policy: Optional[RetryPolicy] = None,
    enable_idempotency: bool = True
):
    """
    Decorator to add error recovery to agent execution methods.
    
    Usage:
        @with_error_recovery(agent_name="parser", enable_idempotency=True)
        async def execute(self, workflow_id, ...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Extract required IDs from kwargs
            workflow_id = kwargs.get('workflow_execution_id')
            project_id = kwargs.get('project_id')
            session_id = getattr(self, 'session_id', None)
            
            if not all([workflow_id, project_id, session_id]):
                # Fall back to basic execution if IDs not available
                logger.warning(
                    f"Error recovery disabled for {agent_name}: missing required IDs"
                )
                return await func(self, *args, **kwargs)
            
            return await execute_with_recovery(
                func,
                self,
                *args,
                workflow_execution_id=workflow_id,
                project_id=project_id,
                session_id=session_id,
                agent_name=agent_name,
                retry_policy=retry_policy,
                enable_idempotency=enable_idempotency,
                **kwargs
            )
        return wrapper
    return decorator