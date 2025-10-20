"""
Model Factory for Strands Agents

This module provides a centralized way to create and configure LLM models
for Strands Agents across different providers (Bedrock, OpenAI, Anthropic, etc.).

The factory loads default configurations from environment variables and
allows per-agent customization.
"""

import os
from typing import Optional, Dict, Any
from strands import Agent
from strands.models import (
    BedrockModel,
    OpenAIModel,
    AnthropicModel,
    GeminiModel
)


class ModelFactory:
    """
    Factory for creating Strands Agent model instances.
    
    Supports multiple providers with sensible defaults from environment variables.
    """
    
    # Default models per provider (can be overridden by env vars)
    DEFAULT_MODELS = {
        "bedrock": "us.amazon.nova-premier-v1:0",
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-20250514",
        "gemini": "gemini-1.5-pro"
    }
    
    # Default parameters
    DEFAULT_PARAMS = {
        "temperature": 0.7,
        "max_tokens": 4096,
        "top_p": 0.9
    }
    
    @classmethod
    def get_default_provider(cls) -> str:
        """
        Get default provider from environment.
        
        Returns:
            Provider name (defaults to 'bedrock')
        """
        return os.getenv("DEFAULT_LLM_PROVIDER", "bedrock").lower()
    
    @classmethod
    def get_default_model(cls, provider: Optional[str] = None) -> str:
        """
        Get default model for a provider from environment or defaults.
        
        Args:
            provider: Provider name (uses default if None)
            
        Returns:
            Model ID
        """
        provider = provider or cls.get_default_provider()
        env_key = f"DEFAULT_{provider.upper()}_MODEL"
        return os.getenv(env_key, cls.DEFAULT_MODELS.get(provider, cls.DEFAULT_MODELS["bedrock"]))
    
    @classmethod
    def get_model_params(cls, **overrides) -> Dict[str, Any]:
        """
        Get model parameters with optional overrides.
        
        Args:
            **overrides: Parameter overrides
            
        Returns:
            Model parameters dict
        """
        params = cls.DEFAULT_PARAMS.copy()
        
        # Load from environment
        if temp := os.getenv("DEFAULT_TEMPERATURE"):
            params["temperature"] = float(temp)
        if max_tokens := os.getenv("DEFAULT_MAX_TOKENS"):
            params["max_tokens"] = int(max_tokens)
        if top_p := os.getenv("DEFAULT_TOP_P"):
            params["top_p"] = float(top_p)
        
        # Apply overrides
        params.update(overrides)
        
        return params
    
    @classmethod
    def create_bedrock_model(
        cls,
        model_id: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        **kwargs
    ) -> BedrockModel:
        """
        Create a Bedrock model instance.
        
        Args:
            model_id: Model ID (uses default if None)
            temperature: Temperature parameter
            max_tokens: Max tokens parameter
            top_p: Top P parameter
            **kwargs: Additional model parameters
            
        Returns:
            BedrockModel instance
        """
        model_id = model_id or cls.get_default_model("bedrock")
        
        # Build params
        params = {}
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if top_p is not None:
            params["top_p"] = top_p
        
        # Get default params and merge
        default_params = cls.get_model_params()
        final_params = {**default_params, **params, **kwargs}
        
        return BedrockModel(
            model_id=model_id,
            temperature=final_params.get("temperature", 0.7),
            top_p=final_params.get("top_p", 0.9),
            max_tokens=final_params.get("max_tokens", 4096)
        )
    
    @classmethod
    def create_openai_model(
        cls,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> OpenAIModel:
        """
        Create an OpenAI model instance.
        
        Args:
            model_id: Model ID (uses default if None)
            api_key: OpenAI API key (uses env var if None)
            temperature: Temperature parameter
            max_tokens: Max tokens parameter
            **kwargs: Additional model parameters
            
        Returns:
            OpenAIModel instance
        """
        model_id = model_id or cls.get_default_model("openai")
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError("OpenAI API key not provided and OPENAI_API_KEY env var not set")
        
        # Build params
        params = {}
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        
        # Get default params and merge
        default_params = cls.get_model_params()
        final_params = {**default_params, **params, **kwargs}
        
        return OpenAIModel(
            client_args={
                "api_key": api_key
            },
            model_id=model_id,
            params={
                "temperature": final_params.get("temperature", 0.7),
                "max_tokens": final_params.get("max_tokens", 4096)
            }
        )
    
    @classmethod
    def create_anthropic_model(
        cls,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AnthropicModel:
        """
        Create an Anthropic model instance.
        
        Args:
            model_id: Model ID (uses default if None)
            api_key: Anthropic API key (uses env var if None)
            temperature: Temperature parameter
            max_tokens: Max tokens parameter
            **kwargs: Additional model parameters
            
        Returns:
            AnthropicModel instance
        """
        model_id = model_id or cls.get_default_model("anthropic")
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        
        if not api_key:
            raise ValueError("Anthropic API key not provided and ANTHROPIC_API_KEY env var not set")
        
        # Build params
        params = {}
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        
        # Get default params and merge
        default_params = cls.get_model_params()
        final_params = {**default_params, **params, **kwargs}
        
        return AnthropicModel(
            client_args={
                "api_key": api_key
            },
            model_id=model_id,
            max_tokens=final_params.get("max_tokens", 4096),
            params={
                "temperature": final_params.get("temperature", 0.7)
            }
        )
    
    @classmethod
    def create_gemini_model(
        cls,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> GeminiModel:
        """
        Create a Gemini model instance.
        
        Args:
            model_id: Model ID (uses default if None)
            api_key: Google API key (uses env var if None)
            temperature: Temperature parameter
            max_tokens: Max tokens parameter
            **kwargs: Additional model parameters
            
        Returns:
            GeminiModel instance
        """
        model_id = model_id or cls.get_default_model("gemini")
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            raise ValueError("Google API key not provided and GOOGLE_API_KEY env var not set")
        
        # Build params
        params = {}
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_output_tokens"] = max_tokens
        
        # Get default params and merge
        default_params = cls.get_model_params()
        final_params = {**default_params, **params, **kwargs}
        
        return GeminiModel(
            client_args={
                "api_key": api_key
            },
            model_id=model_id,
            params={
                "temperature": final_params.get("temperature", 0.7),
                "max_output_tokens": final_params.get("max_tokens", 4096)
            }
        )
    
    @classmethod
    def create_model(
        cls,
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        **kwargs
    ):
        """
        Create a model instance for any provider.
        
        Args:
            provider: Provider name (uses default if None)
            model_id: Model ID (uses provider default if None)
            **kwargs: Additional model parameters
            
        Returns:
            Model instance for the specified provider
            
        Raises:
            ValueError: If provider is not supported
        """
        provider = (provider or cls.get_default_provider()).lower()
        
        if provider == "bedrock":
            return cls.create_bedrock_model(model_id=model_id, **kwargs)
        elif provider == "openai":
            return cls.create_openai_model(model_id=model_id, **kwargs)
        elif provider == "anthropic":
            return cls.create_anthropic_model(model_id=model_id, **kwargs)
        elif provider == "gemini":
            return cls.create_gemini_model(model_id=model_id, **kwargs)
        else:
            raise ValueError(f"Unsupported provider: {provider}. Supported: bedrock, openai, anthropic, gemini")


# Convenience function for creating agents with models
def create_agent_with_model(
    provider: Optional[str] = None,
    model_id: Optional[str] = None,
    tools: Optional[list] = None,
    **model_kwargs
) -> Agent:
    """
    Create a Strands Agent with a configured model.
    
    Args:
        provider: LLM provider (bedrock, openai, anthropic, gemini)
        model_id: Model ID (uses provider default if None)
        tools: List of tools for the agent
        **model_kwargs: Additional model parameters
        
    Returns:
        Configured Agent instance
        
    Example:
        >>> agent = create_agent_with_model(
        ...     provider="bedrock",
        ...     model_id="us.amazon.nova-premier-v1:0",
        ...     temperature=0.5,
        ...     tools=[calculator_tool]
        ... )
    """
    model = ModelFactory.create_model(
        provider=provider,
        model_id=model_id,
        **model_kwargs
    )
    
    return Agent(model=model, tools=tools or [])