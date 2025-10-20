"""
Observability setup with LangFuse, OpenTelemetry, and AgentCore tracing integration.

This module provides:
- LangFuse trace logging for LLM calls
- OpenTelemetry (OTEL) metrics to CloudWatch
- AgentCore runtime observability integration
- Structured logging with context
- Performance metrics tracking
- Custom agent metrics and traces
"""

import logging
import time
import functools
from typing import Optional, Any, Callable
from datetime import datetime
from uuid import UUID, uuid4
from contextlib import contextmanager

from pydantic import BaseModel, Field

from core.config import get_config

logger = logging.getLogger(__name__)

# Try to import LangFuse (optional)
try:
    from langfuse import Langfuse
    from langfuse.decorators import observe, langfuse_context
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    logger.warning("LangFuse not available - tracing disabled")
    
    # Mock decorators if LangFuse not available
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if args and callable(args[0]) else decorator
    
    class MockLangfuseContext:
        def update_current_trace(self, **kwargs): pass
        def update_current_observation(self, **kwargs): pass
        def flush(self): pass
    
    langfuse_context = MockLangfuseContext()

# Try to import OpenTelemetry (optional)
try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("OpenTelemetry not available - metrics/tracing disabled")


class TraceMetadata(BaseModel):
    """Metadata for a trace"""
    workflow_execution_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    agent_name: Optional[str] = None
    task_id: Optional[UUID] = None


class PerformanceMetrics(BaseModel):
    """Performance metrics for operations"""
    operation: str
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservabilityManager:
    """
    Manages observability with LangFuse, OpenTelemetry, and AgentCore integration.
    
    Features:
    - LangFuse trace creation and logging
    - OpenTelemetry metrics to CloudWatch
    - Performance metrics collection
    - Structured logging with context
    - AgentCore runtime integration
    - Custom agent metrics (workflow duration, agent task duration, error rates)
    """
    
    def __init__(self):
        self._langfuse_client: Optional[Any] = None
        self._otel_tracer: Optional[Any] = None
        self._otel_meter: Optional[Any] = None
        self._initialized = False
        self._metrics: list[PerformanceMetrics] = []
        
        # OTEL metric instruments
        self._workflow_duration: Optional[Any] = None
        self._agent_task_duration: Optional[Any] = None
        self._agent_error_counter: Optional[Any] = None
        self._llm_token_counter: Optional[Any] = None
    
    def initialize(self):
        """Initialize observability clients."""
        if self._initialized:
            return
        
        config = get_config()
        
        # Initialize LangFuse if enabled
        if config.langfuse_enabled and LANGFUSE_AVAILABLE:
            try:
                self._langfuse_client = Langfuse(
                    public_key=config.langfuse_public_key,
                    secret_key=config.langfuse_secret_key,
                    host=config.langfuse_host
                )
                logger.info("LangFuse observability initialized")
            except Exception as e:
                logger.error(f"Failed to initialize LangFuse: {e}")
                self._langfuse_client = None
        else:
            logger.info("LangFuse observability disabled")
        
        # Initialize OpenTelemetry if enabled
        if config.otel_enabled and OTEL_AVAILABLE:
            try:
                self._initialize_otel(config)
                logger.info("OpenTelemetry observability initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenTelemetry: {e}")
        else:
            logger.info("OpenTelemetry observability disabled")
        
        self._initialized = True
    
    def _initialize_otel(self, config):
        """Initialize OpenTelemetry tracing and metrics."""
        # Create resource with service information
        resource = Resource.create({
            "service.name": "bidopsai-agent-core",
            "service.version": "1.0.0",
            "deployment.environment": config.environment
        })
        
        # Initialize Tracer Provider
        tracer_provider = TracerProvider(resource=resource)
        
        if config.otel_endpoint:
            # Add OTLP exporter for CloudWatch
            otlp_exporter = OTLPSpanExporter(
                endpoint=config.otel_endpoint,
                insecure=config.environment == "development"
            )
            tracer_provider.add_span_processor(
                BatchSpanProcessor(otlp_exporter)
            )
        
        trace.set_tracer_provider(tracer_provider)
        self._otel_tracer = trace.get_tracer("bidopsai.agent_core")
        
        # Initialize Meter Provider
        metric_reader = None
        if config.otel_endpoint:
            metric_exporter = OTLPMetricExporter(
                endpoint=config.otel_endpoint,
                insecure=config.environment == "development"
            )
            metric_reader = PeriodicExportingMetricReader(
                metric_exporter,
                export_interval_millis=30000  # Export every 30 seconds
            )
        
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader] if metric_reader else []
        )
        metrics.set_meter_provider(meter_provider)
        self._otel_meter = metrics.get_meter("bidopsai.agent_core")
        
        # Create metric instruments
        self._workflow_duration = self._otel_meter.create_histogram(
            name="workflow.duration",
            description="Workflow execution duration in seconds",
            unit="s"
        )
        
        self._agent_task_duration = self._otel_meter.create_histogram(
            name="agent.task.duration",
            description="Agent task execution duration in seconds",
            unit="s"
        )
        
        self._agent_error_counter = self._otel_meter.create_counter(
            name="agent.errors",
            description="Count of agent errors by type",
            unit="1"
        )
        
        self._llm_token_counter = self._otel_meter.create_counter(
            name="llm.tokens",
            description="LLM token usage",
            unit="1"
        )
        
        logger.info("OpenTelemetry metrics instruments created")
    
    def create_trace(
        self,
        name: str,
        metadata: Optional[TraceMetadata] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[list[str]] = None
    ) -> str:
        """
        Create a new trace for workflow/agent execution.
        
        Args:
            name: Trace name (e.g., "workflow_execution", "agent_task")
            metadata: Trace metadata
            user_id: User ID
            session_id: Session ID
            tags: List of tags
            
        Returns:
            Trace ID
        """
        trace_id = str(uuid4())
        
        if self._langfuse_client:
            try:
                meta_dict = metadata.model_dump() if metadata else {}
                
                self._langfuse_client.trace(
                    id=trace_id,
                    name=name,
                    user_id=user_id,
                    session_id=session_id,
                    metadata=meta_dict,
                    tags=tags or []
                )
                
                logger.debug(f"Created trace: {name} (id: {trace_id})")
            except Exception as e:
                logger.error(f"Failed to create trace: {e}")
        
        return trace_id
    
    def update_trace(
        self,
        trace_id: str,
        output: Optional[Any] = None,
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None
    ):
        """Update an existing trace."""
        if self._langfuse_client:
            try:
                langfuse_context.update_current_trace(
                    output=output,
                    metadata=metadata,
                    tags=tags
                )
            except Exception as e:
                logger.error(f"Failed to update trace {trace_id}: {e}")
    
    def log_llm_call(
        self,
        model: str,
        input_text: str,
        output_text: str,
        metadata: Optional[dict] = None,
        usage: Optional[dict] = None
    ):
        """
        Log LLM generation call.
        
        Args:
            model: Model name
            input_text: Input prompt
            output_text: Generated output
            metadata: Additional metadata
            usage: Token usage info (prompt_tokens, completion_tokens, total_tokens)
        """
        if self._langfuse_client:
            try:
                self._langfuse_client.generation(
                    name="llm_call",
                    model=model,
                    model_parameters={
                        **(metadata or {})
                    },
                    input=input_text,
                    output=output_text,
                    usage=usage
                )
                logger.debug(f"Logged LLM call: {model}")
            except Exception as e:
                logger.error(f"Failed to log LLM call: {e}")
    
    def track_metric(self, metric: PerformanceMetrics):
        """Track a performance metric."""
        self._metrics.append(metric)
        
        # Log to structured logs
        logger.info(
            f"Performance: {metric.operation}",
            extra={
                "operation": metric.operation,
                "duration_seconds": metric.duration_seconds,
                "success": metric.success,
                "metadata": metric.metadata
            }
        )
    
    @contextmanager
    def track_operation(self, operation: str, metadata: Optional[dict] = None):
        """
        Context manager to track operation performance.
        
        Usage:
            with observability.track_operation("parse_document"):
                # Your code here
                pass
        """
        metric = PerformanceMetrics(
            operation=operation,
            metadata=metadata or {}
        )
        
        start = time.time()
        
        try:
            yield metric
            metric.success = True
        except Exception as e:
            metric.success = False
            metric.error_message = str(e)
            raise
        finally:
            metric.end_time = datetime.now()
            metric.duration_seconds = time.time() - start
            self.track_metric(metric)
    
    def get_metrics(self, operation: Optional[str] = None) -> list[PerformanceMetrics]:
        """
        Get collected metrics.
        
        Args:
            operation: Optional filter by operation name
            
        Returns:
            List of metrics
        """
        if operation:
            return [m for m in self._metrics if m.operation == operation]
        return self._metrics.copy()
    
    def clear_metrics(self):
        """Clear collected metrics."""
        self._metrics.clear()
    
    def flush(self):
        """Flush any pending traces to LangFuse."""
        if self._langfuse_client:
            try:
                langfuse_context.flush()
                logger.debug("Flushed LangFuse traces")
            except Exception as e:
                logger.error(f"Failed to flush LangFuse: {e}")
    
    def record_workflow_duration(
        self,
        duration_seconds: float,
        workflow_id: str,
        status: str,
        agent_count: int = 0
    ):
        """
        Record workflow execution duration to CloudWatch.
        
        Args:
            duration_seconds: Workflow duration
            workflow_id: Workflow execution ID
            status: Workflow status (completed, failed, etc.)
            agent_count: Number of agents executed
        """
        if self._workflow_duration:
            try:
                self._workflow_duration.record(
                    duration_seconds,
                    attributes={
                        "workflow.id": workflow_id,
                        "workflow.status": status,
                        "workflow.agent_count": agent_count
                    }
                )
                logger.debug(f"Recorded workflow duration: {duration_seconds}s")
            except Exception as e:
                logger.error(f"Failed to record workflow duration: {e}")
    
    def record_agent_task_duration(
        self,
        duration_seconds: float,
        agent_name: str,
        status: str,
        task_id: str
    ):
        """
        Record agent task execution duration to CloudWatch.
        
        Args:
            duration_seconds: Task duration
            agent_name: Name of the agent
            status: Task status
            task_id: Task ID
        """
        if self._agent_task_duration:
            try:
                self._agent_task_duration.record(
                    duration_seconds,
                    attributes={
                        "agent.name": agent_name,
                        "agent.status": status,
                        "agent.task_id": task_id
                    }
                )
                logger.debug(f"Recorded agent task duration: {agent_name} - {duration_seconds}s")
            except Exception as e:
                logger.error(f"Failed to record agent task duration: {e}")
    
    def record_agent_error(
        self,
        agent_name: str,
        error_type: str,
        error_code: str
    ):
        """
        Record agent error to CloudWatch.
        
        Args:
            agent_name: Name of the agent
            error_type: Type of error
            error_code: Error code
        """
        if self._agent_error_counter:
            try:
                self._agent_error_counter.add(
                    1,
                    attributes={
                        "agent.name": agent_name,
                        "error.type": error_type,
                        "error.code": error_code
                    }
                )
                logger.debug(f"Recorded agent error: {agent_name} - {error_type}")
            except Exception as e:
                logger.error(f"Failed to record agent error: {e}")
    
    def record_llm_tokens(
        self,
        token_count: int,
        token_type: str,
        model: str
    ):
        """
        Record LLM token usage to CloudWatch.
        
        Args:
            token_count: Number of tokens
            token_type: Type of tokens (prompt, completion, total)
            model: Model name
        """
        if self._llm_token_counter:
            try:
                self._llm_token_counter.add(
                    token_count,
                    attributes={
                        "llm.token_type": token_type,
                        "llm.model": model
                    }
                )
                logger.debug(f"Recorded LLM tokens: {model} - {token_type}: {token_count}")
            except Exception as e:
                logger.error(f"Failed to record LLM tokens: {e}")
    
    def start_span(self, name: str, attributes: Optional[dict] = None):
        """
        Start an OTEL span for distributed tracing.
        
        Args:
            name: Span name
            attributes: Optional span attributes
        
        Returns:
            Span context manager or None
        """
        if self._otel_tracer:
            try:
                return self._otel_tracer.start_as_current_span(
                    name,
                    attributes=attributes or {}
                )
            except Exception as e:
                logger.error(f"Failed to start span: {e}")
        return contextmanager(lambda: (yield None))()


# Global observability manager
_observability_instance = None


def get_observability_manager() -> ObservabilityManager:
    """Get singleton observability manager instance."""
    global _observability_instance
    if _observability_instance is None:
        _observability_instance = ObservabilityManager()
    return _observability_instance


def initialize_observability():
    """Initialize global observability manager."""
    manager = get_observability_manager()
    manager.initialize()


# Backwards compatibility
observability = get_observability_manager()
init_observability = initialize_observability


def trace_workflow(func: Callable) -> Callable:
    """
    Decorator to trace workflow execution.
    
    Usage:
        @trace_workflow
        async def execute_workflow(state):
            ...
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract workflow info from args/kwargs
        workflow_name = func.__name__
        
        trace_id = observability.create_trace(
            name=f"workflow:{workflow_name}",
            tags=["workflow"]
        )
        
        try:
            result = await func(*args, **kwargs)
            observability.update_trace(
                trace_id,
                output={"status": "success"},
                metadata={"workflow": workflow_name}
            )
            return result
        except Exception as e:
            observability.update_trace(
                trace_id,
                output={"status": "failed", "error": str(e)},
                metadata={"workflow": workflow_name}
            )
            raise
        finally:
            observability.flush()
    
    return wrapper


def trace_agent(agent_name: str):
    """
    Decorator to trace agent execution.
    
    Usage:
        @trace_agent("parser")
        async def execute_parser(input_data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            trace_id = observability.create_trace(
                name=f"agent:{agent_name}",
                tags=["agent", agent_name]
            )
            
            with observability.track_operation(f"agent_{agent_name}"):
                try:
                    result = await func(*args, **kwargs)
                    observability.update_trace(
                        trace_id,
                        output={"status": "success"},
                        metadata={"agent": agent_name}
                    )
                    return result
                except Exception as e:
                    observability.update_trace(
                        trace_id,
                        output={"status": "failed", "error": str(e)},
                        metadata={"agent": agent_name}
                    )
                    raise
                finally:
                    observability.flush()
        
        return wrapper
    return decorator


def track_agent_performance(agent_name: str):
    """
    Decorator to track agent performance metrics.
    
    Usage:
        @track_agent_performance(agent_name="workflow_executor")
        async def invoke_workflow(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            obs = get_observability_manager()
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Record successful execution
                obs.record_agent_task_duration(
                    duration_seconds=duration,
                    agent_name=agent_name,
                    status="completed",
                    task_id=str(uuid4())
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # Record failed execution
                obs.record_agent_task_duration(
                    duration_seconds=duration,
                    agent_name=agent_name,
                    status="failed",
                    task_id=str(uuid4())
                )
                
                # Record error
                obs.record_agent_error(
                    agent_name=agent_name,
                    error_type=type(e).__name__,
                    error_code=getattr(e, 'code', 'UNKNOWN')
                )
                
                raise
        
        return wrapper
    return decorator


def log_agent_action(
    agent_name: str,
    action: str,
    details: Optional[dict] = None,
    level: str = "info"
):
    """
    Log agent action with structured context.
    
    Args:
        agent_name: Name of the agent
        action: Action being performed
        details: Additional details
        level: Log level (info, warning, error)
    """
    log_with_context(
        level=level,
        message=f"[{agent_name}] {action}",
        agent_name=agent_name,
        action=action,
        **(details or {})
    )


# Structured logging helpers
def log_with_context(
    level: str,
    message: str,
    workflow_execution_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    agent_name: Optional[str] = None,
    **extra_fields
):
    """
    Log message with structured context.
    
    Args:
        level: Log level (INFO, WARNING, ERROR, etc.)
        message: Log message
        workflow_execution_id: Optional workflow ID
        project_id: Optional project ID
        agent_name: Optional agent name
        **extra_fields: Additional structured fields
    """
    context = {
        "workflow_execution_id": str(workflow_execution_id) if workflow_execution_id else None,
        "project_id": str(project_id) if project_id else None,
        "agent_name": agent_name,
        **extra_fields
    }
    
    # Remove None values
    context = {k: v for k, v in context.items() if v is not None}
    
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, extra=context)