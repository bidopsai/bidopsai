"""
Pydantic models for BidOpsAI AgentCore.

This module provides all data models used throughout the agentic system,
including base models, workflow models, request/response models, SSE events,
artifacts, and LLM structured outputs.
"""

# Base models
from .base import (
    ConfigurableModel,
    ErrorResponse,
    IdentifiedModel,
    PaginatedResponse,
    SuccessResponse,
    TimestampedModel,
)

# Workflow models
from .workflow_models import (
    AgentTask,
    AgentTaskConfig,
    AgentTaskInput,
    AgentTaskOutput,
    ErrorLog,
    Project,
    ProjectDocument,
    WorkflowConfig,
    WorkflowExecution,
    WorkflowProgress,
)

# Request/Response models
from .request_models import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    ArtifactExportRequest,
    ArtifactExportResponse,
    BatchOperationRequest,
    BatchOperationResponse,
    ConversationHistoryRequest,
    ConversationHistoryResponse,
    ConversationMessage,
    ConversationMessageRequest,
    HealthCheckResponse,
    InvocationRequest,
    InvocationResponse,
    MetricsRequest,
    MetricsResponse,
    UserInput,
    WorkflowCancellationRequest,
    WorkflowCancellationResponse,
)

# SSE event models
from .sse_models import (
    AgentCompletedEventData,
    AgentFailedEventData,
    AgentStartedEventData,
    ArtifactsExportedEventData,
    ArtifactsReadyEventData,
    AwaitingFeedbackEventData,
    EmailDraftEventData,
    ErrorEventData,
    PermissionRequestEventData,
    ProgressUpdateEventData,
    SSEEvent,
    SSEEventData,
    SSEEventLog,
    SSEEventType,
    WorkflowCompletedEventData,
    WorkflowCreatedEventData,
)

# Artifact models
from .artifact_models import (
    Artifact,
    ArtifactContent,
    ArtifactExport,
    ArtifactFeedback,
    ArtifactMetadata,
    ArtifactTile,
    ArtifactVersion,
    ArtifactWithVersion,
    ComplianceFeedback,
    QAFeedback,
    QAndAContent,
    QAndAItem,
    TableContent,
    TableRow,
    TipTapContent,
)

# LLM output models
from .llm_output_models import (
    AnalysisOutput,
    ClientInfo,
    ComplianceCheck,
    ComplianceOutput,
    ContentGenerationPlan,
    DocumentInfo,
    EmailDraft,
    IntentClassification,
    MissingArtifact,
    NotificationPlan,
    QACheckResult,
    QAOutput,
    RequiredDocument,
    Stakeholder,
    SubmissionMethod,
)

# Parser Agent output models
from .parser_output_model import (
    ParserOutput,
    ProcessedDocument,
)

# Supervisor models
from .supervisor_models import (
    AgentRoutingDecision,
    ErrorSeverity,
    FeedbackAnalysis,
    FeedbackType,
    PermissionRequest,
    PermissionType,
    SupervisorDecisionType,
    ValidationAnalysis,
    ValidationStatus,
    WorkflowProgressAssessment,
)

__all__ = [
    # Base models
    "TimestampedModel",
    "IdentifiedModel",
    "ConfigurableModel",
    "PaginatedResponse",
    "ErrorResponse",
    "SuccessResponse",
    # Workflow models
    "WorkflowConfig",
    "AgentTaskConfig",
    "AgentTaskInput",
    "AgentTaskOutput",
    "ErrorLog",
    "AgentTask",
    "WorkflowExecution",
    "WorkflowProgress",
    "Project",
    "ProjectDocument",
    # Request/Response models
    "UserInput",
    "InvocationRequest",
    "InvocationResponse",
    "AgentInvocationRequest",
    "AgentInvocationResponse",
    "HealthCheckResponse",
    "ConversationMessageRequest",
    "ConversationMessage",
    "ConversationHistoryRequest",
    "ConversationHistoryResponse",
    "ArtifactExportRequest",
    "ArtifactExportResponse",
    "BatchOperationRequest",
    "BatchOperationResponse",
    "WorkflowCancellationRequest",
    "WorkflowCancellationResponse",
    "MetricsRequest",
    "MetricsResponse",
    # SSE event models
    "SSEEventData",
    "WorkflowCreatedEventData",
    "AgentStartedEventData",
    "AgentCompletedEventData",
    "AgentFailedEventData",
    "AwaitingFeedbackEventData",
    "ArtifactsReadyEventData",
    "ArtifactsExportedEventData",
    "PermissionRequestEventData",
    "EmailDraftEventData",
    "WorkflowCompletedEventData",
    "ProgressUpdateEventData",
    "ErrorEventData",
    "SSEEvent",
    "SSEEventLog",
    "SSEEventType",
    # Artifact models
    "TipTapContent",
    "QAndAItem",
    "QAndAContent",
    "TableRow",
    "TableContent",
    "ArtifactMetadata",
    "ArtifactContent",
    "Artifact",
    "ArtifactVersion",
    "ArtifactWithVersion",
    "ArtifactTile",
    "ComplianceFeedback",
    "QAFeedback",
    "ArtifactFeedback",
    "ArtifactExport",
    # LLM output models
    "DocumentInfo",
    "ClientInfo",
    "Stakeholder",
    "RequiredDocument",
    "SubmissionMethod",
    "AnalysisOutput",
    "ContentGenerationPlan",
    "ComplianceCheck",
    "ComplianceOutput",
    "QACheckResult",
    "MissingArtifact",
    "QAOutput",
    "EmailDraft",
    "NotificationPlan",
    "IntentClassification",
    # Parser Agent output models
    "ParserOutput",
    "ProcessedDocument",
    # Supervisor models
    "SupervisorDecisionType",
    "FeedbackType",
    "ValidationStatus",
    "PermissionType",
    "ErrorSeverity",
    "AgentRoutingDecision",
    "FeedbackAnalysis",
    "ValidationAnalysis",
    "WorkflowProgressAssessment",
    "PermissionRequest",
]