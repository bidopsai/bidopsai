# Model Configuration Guide

This document explains how to configure LLM models for agents in the BidOpsAI AgentCore system using the Strands Agents framework.

## Overview

The BidOpsAI AgentCore uses a centralized **ModelFactory** that provides flexible, configuration-driven model management across multiple LLM providers:

- **AWS Bedrock** (default)
- **OpenAI**
- **Anthropic**
- **Google Gemini**

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Initialization                      │
│  (ParserAgent, AnalysisAgent, ContentAgent, etc.)           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      ModelFactory                            │
│  • Reads environment configuration                           │
│  • Creates provider-specific model instances                 │
│  • Applies default parameters with overrides                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Strands Agent Model                       │
│  (BedrockModel, OpenAIModel, AnthropicModel, GeminiModel)   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Strands Agent                           │
│  Agent(model=model, tools=[...])                            │
└─────────────────────────────────────────────────────────────┘
```

## Environment Configuration

### Local Development (`.env.development`)

```bash
# Default provider for all agents
DEFAULT_LLM_PROVIDER=bedrock

# Provider-specific default models
DEFAULT_BEDROCK_MODEL=us.amazon.nova-premier-v1:0
DEFAULT_OPENAI_MODEL=gpt-4o
DEFAULT_ANTHROPIC_MODEL=claude-sonnet-4-20250514
DEFAULT_GEMINI_MODEL=gemini-1.5-pro

# Default model parameters (applied to all providers)
DEFAULT_TEMPERATURE=0.7
DEFAULT_MAX_TOKENS=4096
DEFAULT_TOP_P=0.9

# API Keys (required for non-Bedrock providers)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

### Production (SSM Parameter Store / Secrets Manager)

In production, sensitive values like API keys should be stored in AWS Secrets Manager:

```python
# Secrets Manager secret structure
{
    "DEFAULT_LLM_PROVIDER": "bedrock",
    "DEFAULT_BEDROCK_MODEL": "us.amazon.nova-premier-v1:0",
    "OPENAI_API_KEY": "sk-...",
    "ANTHROPIC_API_KEY": "sk-ant-...",
    "DEFAULT_TEMPERATURE": "0.7",
    "DEFAULT_MAX_TOKENS": "4096"
}
```

Non-sensitive configuration goes in SSM Parameter Store:
```
/bidopsai/prod/llm/default_provider = bedrock
/bidopsai/prod/llm/default_bedrock_model = us.amazon.nova-premier-v1:0
/bidopsai/prod/llm/default_temperature = 0.7
```

## Usage Patterns

### Pattern 1: Use Environment Defaults (Recommended)

```python
from agents_core.agents.parser_agent import create_parser_agent

# Uses DEFAULT_LLM_PROVIDER and provider's default model from env
agent = create_parser_agent(
    mode="workflow",
    session_id="session-123"
)
```

**Environment determines everything:**
- Provider: `DEFAULT_LLM_PROVIDER` (e.g., "bedrock")
- Model: `DEFAULT_BEDROCK_MODEL` (e.g., "us.amazon.nova-premier-v1:0")
- Parameters: `DEFAULT_TEMPERATURE`, `DEFAULT_MAX_TOKENS`, `DEFAULT_TOP_P`

### Pattern 2: Override Provider

```python
# Use OpenAI instead of default Bedrock
agent = create_parser_agent(
    mode="workflow",
    provider="openai",  # Override provider
    session_id="session-123"
)

# Uses DEFAULT_OPENAI_MODEL from environment
```

### Pattern 3: Override Model and Parameters

```python
# Use specific model and custom parameters
agent = create_parser_agent(
    mode="workflow",
    provider="anthropic",
    model_id="claude-3-opus-20240229",
    temperature=0.5,
    max_tokens=8192,
    session_id="session-123"
)
```

### Pattern 4: Direct ModelFactory Usage

For advanced scenarios where you need direct control:

```python
from agents_core.llm.model_factory import ModelFactory
from strands_agents import Agent

# Create model directly
model = ModelFactory.create_bedrock_model(
    model_id="us.amazon.nova-premier-v1:0",
    temperature=0.3,
    max_tokens=2048
)

# Create agent with model
agent = Agent(
    model=model,
    tools=[calculator_tool, database_tool]
)
```

### Pattern 5: Different Models per Agent

```python
# Parser uses fast, cheap model
parser_agent = create_parser_agent(
    mode="workflow",
    provider="bedrock",
    model_id="us.amazon.nova-lite-v1:0",  # Cheaper model
    temperature=0.3
)

# Analysis uses powerful model
analysis_agent = create_analysis_agent(
    mode="workflow",
    provider="anthropic",
    model_id="claude-sonnet-4-20250514",  # More capable
    temperature=0.7
)
```

## Agent Implementation Example

Here's how agents should be implemented with the new pattern:

```python
from typing import Optional
from strands_agents import Agent
from agents_core.llm.model_factory import ModelFactory
from agents_core.tools.tool_manager import get_tool_manager
from agents_core.prompts.prompt_manager import get_agent_prompt

class MyCustomAgent:
    def __init__(
        self,
        mode: str = "workflow",
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **model_kwargs
    ):
        """
        Initialize agent.
        
        Args:
            mode: Operating mode
            provider: LLM provider (uses env DEFAULT_LLM_PROVIDER if None)
            model_id: Model ID (uses provider default if None)
            session_id: Session ID for tracking
            **model_kwargs: Additional model params (temperature, max_tokens, etc.)
        """
        self.mode = mode
        self.session_id = session_id
        self.agent_name = "my_custom_agent"
        
        # Get tool manager and agent prompt
        self.tool_manager = get_tool_manager()
        self.system_prompt = get_agent_prompt(
            agent_name=self.agent_name,
            mode=self.mode
        )
        
        # Create model using factory
        self.model = ModelFactory.create_model(
            provider=provider,
            model_id=model_id,
            **model_kwargs
        )
        
        # Create Strands Agent with model and tools
        self.agent = Agent(
            model=self.model,
            tools=self.tool_manager.get_tools_for_agent(
                self.agent_name,
                self.mode
            )
        )
    
    async def execute(self, **kwargs):
        """Execute agent logic using self.agent"""
        # Use self.agent for LLM calls
        result = await self.agent.run(
            input_message="Process this task",
            system_prompt=self.system_prompt
        )
        return result


# Factory function
def create_my_custom_agent(
    mode: str = "workflow",
    provider: Optional[str] = None,
    model_id: Optional[str] = None,
    session_id: Optional[str] = None,
    **model_kwargs
) -> MyCustomAgent:
    """Factory function to create agent instance."""
    return MyCustomAgent(
        mode=mode,
        provider=provider,
        model_id=model_id,
        session_id=session_id,
        **model_kwargs
    )
```

## Provider-Specific Configuration

### AWS Bedrock

```python
# Uses AWS credentials from environment or IAM role
agent = create_parser_agent(
    mode="workflow",
    provider="bedrock",
    model_id="us.amazon.nova-premier-v1:0",
    temperature=0.7,
    top_p=0.9,
    max_tokens=4096
)
```

**Supported Models:**
- `us.amazon.nova-premier-v1:0` (Most capable)
- `us.amazon.nova-lite-v1:0` (Fast and cheap)
- `us.amazon.nova-micro-v1:0` (Fastest, cheapest)
- `anthropic.claude-3-5-sonnet-20241022-v2:0`
- `anthropic.claude-3-5-haiku-20241022-v1:0`

### OpenAI

```python
# Requires OPENAI_API_KEY in environment
agent = create_parser_agent(
    mode="workflow",
    provider="openai",
    model_id="gpt-4o",
    temperature=0.7,
    max_tokens=4096
)
```

**Supported Models:**
- `gpt-4o` (Latest GPT-4 Omni)
- `gpt-4o-mini` (Faster, cheaper)
- `gpt-4-turbo-preview`
- `gpt-3.5-turbo`

### Anthropic

```python
# Requires ANTHROPIC_API_KEY in environment
agent = create_parser_agent(
    mode="workflow",
    provider="anthropic",
    model_id="claude-sonnet-4-20250514",
    temperature=0.7,
    max_tokens=4096
)
```

**Supported Models:**
- `claude-sonnet-4-20250514` (Latest Sonnet)
- `claude-3-5-sonnet-20241022`
- `claude-3-opus-20240229` (Most capable)
- `claude-3-haiku-20240307` (Fast and cheap)

### Google Gemini

```python
# Requires GOOGLE_API_KEY in environment
agent = create_parser_agent(
    mode="workflow",
    provider="gemini",
    model_id="gemini-1.5-pro",
    temperature=0.7,
    max_output_tokens=4096
)
```

**Supported Models:**
- `gemini-1.5-pro` (Most capable)
- `gemini-1.5-flash` (Fast and cheap)
- `gemini-pro`

## Best Practices

### 1. Use Environment Defaults for Consistency

```python
# ✅ Good: Uses environment configuration
agent = create_parser_agent(mode="workflow")

# ❌ Avoid: Hardcoding provider/model
agent = create_parser_agent(
    mode="workflow",
    provider="bedrock",
    model_id="specific-model-id"
)
```

### 2. Override Only When Necessary

```python
# ✅ Good: Override for specific reason (cheaper model for parsing)
parser_agent = create_parser_agent(
    mode="workflow",
    model_id="us.amazon.nova-lite-v1:0"  # Cheaper for simple task
)

# ✅ Good: Override for specific reason (more powerful for analysis)
analysis_agent = create_analysis_agent(
    mode="workflow",
    provider="anthropic",
    model_id="claude-sonnet-4-20250514"  # More capable for complex analysis
)
```

### 3. Store Sensitive Data Securely

```python
# ✅ Good: API keys in Secrets Manager (production)
# ✅ Good: API keys in .env.development (local)

# ❌ Never: Hardcode API keys
OPENAI_API_KEY = "sk-..."  # NEVER DO THIS
```

### 4. Document Model Choices

```python
# ✅ Good: Clear documentation
def create_parser_agent(...):
    """
    Create Parser Agent.
    
    Recommended models:
    - Bedrock: us.amazon.nova-lite-v1:0 (fast, cheap for document parsing)
    - OpenAI: gpt-4o-mini (if using OpenAI)
    """
    pass
```

### 5. Test with Multiple Providers

```python
import pytest

@pytest.mark.parametrize("provider", ["bedrock", "openai", "anthropic"])
async def test_agent_with_providers(provider):
    """Test agent works with different providers."""
    agent = create_parser_agent(mode="workflow", provider=provider)
    result = await agent.execute(...)
    assert result["success"]
```

## Troubleshooting

### Issue: "Provider not supported"

**Cause:** Invalid provider name

**Solution:**
```python
# Valid providers: bedrock, openai, anthropic, gemini
agent = create_parser_agent(provider="bedrock")  # Not "aws" or "amazon"
```

### Issue: "API key not found"

**Cause:** API key not in environment for non-Bedrock providers

**Solution:**
```bash
# Add to .env.development
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

### Issue: "Model not found"

**Cause:** Invalid model ID for provider

**Solution:** Use supported models (see provider-specific sections above)

### Issue: "Bedrock permission denied"

**Cause:** AWS credentials don't have Bedrock permissions

**Solution:**
```bash
# Ensure AWS credentials have bedrock:InvokeModel permission
aws configure list
```

## Migration from Old Pattern

### Old Pattern (❌ Don't use)

```python
class MyAgent:
    def __init__(self, mode, llm_provider="bedrock", model=None):
        self.llm_provider = llm_provider
        self.model = model or self._get_default_model()
        # Manual model configuration
        
    def _get_default_model(self):
        return "anthropic.claude-3-5-sonnet-20241022-v2:0"
```

### New Pattern (✅ Use this)

```python
from agents_core.llm.model_factory import ModelFactory

class MyAgent:
    def __init__(self, mode, provider=None, model_id=None, **model_kwargs):
        # Use ModelFactory
        self.model = ModelFactory.create_model(
            provider=provider,
            model_id=model_id,
            **model_kwargs
        )
        
        # Create Strands Agent
        self.agent = Agent(model=self.model, tools=[...])
```

## Additional Resources

- [Strands Agents Documentation](https://strandsagents.com/latest/documentation/)
- [AWS Bedrock Models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)
- [OpenAI Models](https://platform.openai.com/docs/models)
- [Anthropic Models](https://docs.anthropic.com/en/docs/models-overview)
- [Google Gemini Models](https://ai.google.dev/models)