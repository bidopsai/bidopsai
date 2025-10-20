"""
Configuration loader with SSM Parameter Store and Secrets Manager integration.

This module provides:
- Environment-based configuration (development vs production)
- SSM Parameter Store integration for agent configs
- AWS Secrets Manager integration for credentials
- Local .env fallback for development
- Configuration caching
"""

import os
import json
import logging
from typing import Optional, Any
from functools import lru_cache
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Try to import AWS SDK (optional for local dev)
try:
    import boto3
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
    logger.warning("boto3 not available - using local config only")


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env.development",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # App settings
    app_name: str = Field(default="bidopsai-agents", alias="APP_NAME")
    app_version_workflow: str = Field(default="0.1.0", alias="APP_VERSION_WORKFLOW")
    app_version_ai_assistant: str = Field(default="0.1.0", alias="APP_VERSION_AI_ASSISTANT")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # Database settings
    database_url: str = Field(..., alias="DATABASE_URL")
    db_pool_min_size: int = Field(default=5, alias="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=20, alias="DB_POOL_MAX_SIZE")
    db_connection_timeout: float = Field(default=10.0, alias="DB_CONNECTION_TIMEOUT")
    db_command_timeout: float = Field(default=60.0, alias="DB_COMMAND_TIMEOUT")
    
    # AWS settings
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    
    # S3 settings
    s3_bucket_documents: str = Field(..., alias="S3_BUCKET_DOCUMENTS")
    s3_bucket_artifacts: str = Field(..., alias="S3_BUCKET_ARTIFACTS")
    s3_bucket_bda_output: str = Field(..., alias="S3_BUCKET_BDA_OUTPUT")
    s3_endpoint_url: Optional[str] = Field(default=None, alias="S3_ENDPOINT_URL")  # For LocalStack
    
    # Bedrock settings
    bedrock_region: str = Field(default="us-east-1", alias="BEDROCK_REGION")
    bedrock_model_id: str = Field(default="anthropic.claude-3-5-sonnet-20241022-v2:0", alias="BEDROCK_MODEL_ID")
    bedrock_model_kb_id: str = Field(default="anthropic.claude-3-haiku-20240307-v1:0", alias="BEDROCK_MODEL_KB_ID")
    
    # AgentCore settings
    agentcore_runtime_url_workflow: Optional[str] = Field(default=None, alias="AGENTCORE_RUNTIME_URL_WORKFLOW")
    agentcore_runtime_url_ai_assistant: Optional[str] = Field(default=None, alias="AGENTCORE_RUNTIME_URL_AI_ASSISTANT")
    agentcore_identity_pool_id: Optional[str] = Field(default=None, alias="AGENTCORE_IDENTITY_POOL_ID")
    
    # AgentCore Memory settings
    agentcore_memory_enabled: bool = Field(default=True, alias="AGENTCORE_MEMORY_ENABLED")
    agentcore_memory_name: str = Field(default="BidOpsAI_Memory", alias="AGENTCORE_MEMORY_NAME")
    agentcore_memory_resource_id: Optional[str] = Field(default=None, alias="AGENTCORE_MEMORY_RESOURCE_ID")
    agentcore_memory_strategy: str = Field(default="USER_PREFERENCE", alias="AGENTCORE_MEMORY_STRATEGY")
    agentcore_memory_strategy_name: str = Field(default="AgentPreferences", alias="AGENTCORE_MEMORY_STRATEGY_NAME")
    agentcore_memory_namespace_pattern: str = Field(default="bidops/{actorId}/preferences", alias="AGENTCORE_MEMORY_NAMESPACE_PATTERN")
    agentcore_memory_event_expiry_days: int = Field(default=7, alias="AGENTCORE_MEMORY_EVENT_EXPIRY_DAYS")
    agentcore_memory_hooks_enabled: bool = Field(default=True, alias="AGENTCORE_MEMORY_HOOKS_ENABLED")
    agentcore_memory_auto_save: bool = Field(default=True, alias="AGENTCORE_MEMORY_AUTO_SAVE")
    agentcore_memory_batch_size: int = Field(default=10, alias="AGENTCORE_MEMORY_BATCH_SIZE")
    
    # MCP settings
    mcp_gateway_endpoint: Optional[str] = Field(default=None, alias="MCP_GATEWAY_ENDPOINT")
    mcp_slack_enabled: bool = Field(default=False, alias="MCP_SLACK_ENABLED")
    
    # Observability settings - LangFuse
    langfuse_enabled: bool = Field(default=False, alias="LANGFUSE_ENABLED")
    langfuse_public_key: Optional[str] = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: Optional[str] = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", alias="LANGFUSE_HOST")
    
    # Observability settings - OpenTelemetry (OTEL)
    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_endpoint: Optional[str] = Field(default=None, alias="OTEL_ENDPOINT")
    otel_service_name: str = Field(default="bidopsai-agent-core", alias="OTEL_SERVICE_NAME")
    otel_export_interval_ms: int = Field(default=30000, alias="OTEL_EXPORT_INTERVAL_MS")
    
    # CloudWatch settings (for OTEL export)
    cloudwatch_namespace: str = Field(default="BidOpsAI/AgentCore", alias="CLOUDWATCH_NAMESPACE")
    cloudwatch_log_group: str = Field(default="/aws/agentcore/bidopsai", alias="CLOUDWATCH_LOG_GROUP")
    
    # SSM/Secrets Manager settings
    ssm_parameter_prefix: str = Field(default="/bidopsai/agents", alias="SSM_PARAMETER_PREFIX")
    secrets_manager_enabled: bool = Field(default=False, alias="SECRETS_MANAGER_ENABLED")
    
    # Agent settings defaults (overridden by SSM in production)
    agent_temperature: float = Field(default=0.7, alias="AGENT_TEMPERATURE")
    agent_max_tokens: int = Field(default=4096, alias="AGENT_MAX_TOKENS")
    agent_timeout_seconds: int = Field(default=300, alias="AGENT_TIMEOUT_SECONDS")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() in ["production", "prod"]
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment.lower() in ["development", "dev"]


class AgentConfiguration(BaseModel):
    """Agent-specific configuration from SSM Parameter Store."""
    agent_type: str
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: dict[str, Any]
    additional_parameters: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    cache_expires_at: datetime


class ConfigLoader:
    """
    Configuration loader with caching and AWS integration.
    
    Features:
    - Load from environment variables (.env files)
    - Fetch agent configs from SSM Parameter Store
    - Fetch secrets from AWS Secrets Manager
    - Cache configurations with TTL
    - Fallback to local config in development
    """
    
    def __init__(self):
        self._app_config: Optional[AppConfig] = None
        self._agent_configs: dict[str, AgentConfiguration] = {}
        self._ssm_client = None
        self._secrets_client = None
        
        if AWS_AVAILABLE:
            self._init_aws_clients()
    
    def _init_aws_clients(self):
        """Initialize AWS clients for SSM and Secrets Manager."""
        try:
            config = self.get_app_config()
            
            session_kwargs = {"region_name": config.aws_region}
            
            if config.aws_access_key_id and config.aws_secret_access_key:
                session_kwargs.update({
                    "aws_access_key_id": config.aws_access_key_id,
                    "aws_secret_access_key": config.aws_secret_access_key
                })
            
            self._ssm_client = boto3.client('ssm', **session_kwargs)
            self._secrets_client = boto3.client('secretsmanager', **session_kwargs)
            
            logger.info("AWS clients initialized for SSM and Secrets Manager")
            
        except Exception as e:
            logger.warning(f"Failed to initialize AWS clients: {e}")
            self._ssm_client = None
            self._secrets_client = None
    
    @lru_cache(maxsize=1)
    def get_app_config(self) -> AppConfig:
        """
        Get application configuration.
        
        Returns:
            AppConfig instance loaded from environment
        """
        if self._app_config is None:
            self._app_config = AppConfig()
            logger.info(f"Loaded app config for environment: {self._app_config.environment}")
        
        return self._app_config
    
    async def get_agent_config(
        self,
        agent_type: str,
        use_cache: bool = True
    ) -> AgentConfiguration:
        """
        Get agent configuration from SSM Parameter Store or cache.
        
        Args:
            agent_type: Agent type (parser, analysis, content, etc.)
            use_cache: Whether to use cached config (default: True)
            
        Returns:
            AgentConfiguration instance
        """
        # Check cache first
        if use_cache and agent_type in self._agent_configs:
            cached = self._agent_configs[agent_type]
            if cached.cache_expires_at > datetime.now():
                logger.debug(f"Using cached config for agent: {agent_type}")
                return cached
        
        config = self.get_app_config()
        
        # Try to load from SSM in production
        if config.is_production and self._ssm_client:
            try:
                agent_config = await self._load_agent_config_from_ssm(agent_type)
                self._agent_configs[agent_type] = agent_config
                return agent_config
                
            except Exception as e:
                logger.error(f"Failed to load agent config from SSM: {e}")
                # Fall through to defaults
        
        # Use defaults from environment
        logger.info(f"Using default config for agent: {agent_type}")
        return AgentConfiguration(
            agent_type=agent_type,
            model_name=config.bedrock_model_id,
            temperature=config.agent_temperature,
            max_tokens=config.agent_max_tokens,
            system_prompt={},  # Will be loaded from prompts/ directory
            additional_parameters={},
            enabled=True,
            cache_expires_at=datetime.now() + timedelta(hours=1)
        )
    
    async def _load_agent_config_from_ssm(self, agent_type: str) -> AgentConfiguration:
        """Load agent configuration from SSM Parameter Store."""
        config = self.get_app_config()
        parameter_name = f"{config.ssm_parameter_prefix}/{agent_type}/config"
        
        try:
            response = self._ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=True
            )
            
            param_value = json.loads(response['Parameter']['Value'])
            
            return AgentConfiguration(
                agent_type=agent_type,
                model_name=param_value.get('model_name', config.bedrock_model_id),
                temperature=param_value.get('temperature', 0.7),
                max_tokens=param_value.get('max_tokens', 4096),
                system_prompt=param_value.get('system_prompt', {}),
                additional_parameters=param_value.get('additional_parameters', {}),
                enabled=param_value.get('enabled', True),
                cache_expires_at=datetime.now() + timedelta(hours=1)
            )
            
        except Exception as e:
            logger.error(f"Failed to load SSM parameter {parameter_name}: {e}")
            raise
    
    async def get_secret(self, secret_name: str) -> dict[str, Any]:
        """
        Get secret from AWS Secrets Manager.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Secret value as dictionary
        """
        config = self.get_app_config()
        
        if not config.secrets_manager_enabled or not self._secrets_client:
            logger.warning(f"Secrets Manager not enabled, cannot fetch: {secret_name}")
            return {}
        
        try:
            response = self._secrets_client.get_secret_value(SecretId=secret_name)
            
            if 'SecretString' in response:
                return json.loads(response['SecretString'])
            else:
                logger.error(f"Secret {secret_name} is not a string")
                return {}
                
        except Exception as e:
            logger.error(f"Failed to get secret {secret_name}: {e}")
            return {}
    
    def clear_cache(self):
        """Clear all cached configurations."""
        self._agent_configs.clear()
        self.get_app_config.cache_clear()
        logger.info("Configuration cache cleared")


# Global config loader instance
_config_loader = ConfigLoader()


def get_config() -> AppConfig:
    """Get application configuration."""
    return _config_loader.get_app_config()


async def get_agent_config(agent_type: str, use_cache: bool = True) -> AgentConfiguration:
    """Get agent-specific configuration."""
    return await _config_loader.get_agent_config(agent_type, use_cache)


async def get_secret(secret_name: str) -> dict[str, Any]:
    """Get secret from AWS Secrets Manager."""
    return await _config_loader.get_secret(secret_name)


def clear_config_cache():
    """Clear configuration cache."""
    _config_loader.clear_cache()