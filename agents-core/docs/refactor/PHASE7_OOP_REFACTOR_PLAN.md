# Phase 7: OOP Class Refactor Plan

## Overview

Refactor all agent factory functions to use proper OOP classes following object-oriented design principles. This addresses feedback about using global variables and functions instead of proper class-based architecture.

**Status**: 🔄 In Progress  
**Goal**: Convert all 9 agent factory functions to proper OOP classes with encapsulation, inheritance, and abstraction

---

## Current Issues

### 1. Factory Functions Instead of Classes ❌
```python
# Current (factory function)
def create_analysis_agent(mode, provider, model_id):
    tool_manager = get_tool_manager()  # Global call
    tools = tool_manager.get_agent_tools("analysis", mode)
    system_prompt = get_agent_prompt("analysis", mode)  # Global call
    model = ModelFactory.create_model(provider, model_id)
    return Agent(...)

# Usage
agent = create_analysis_agent(mode="workflow")
```

**Problems**:
- No encapsulation of agent state
- Global function calls scattered throughout
- No reusability or inheritance
- Can't easily extend or customize behavior
- State management is external

### 2. No Base Class ❌
- Each agent reimplements similar initialization logic
- No common interface or contract
- Difficult to add common functionality
- Code duplication across agents

### 3. Limited Configuration Management ❌
- Parameters passed directly without validation
- No default value management
- No configuration persistence

---

## Proposed OOP Architecture

### Class Hierarchy

```
BaseAgent (Abstract Base Class)
│
├── SupervisorAgent
│
├── ParserAgent
│
├── AnalysisAgent
│
├── ContentAgent
│   └── Uses: KnowledgeAgent (composition)
│
├── KnowledgeAgent
│
├── ComplianceAgent
│
├── QAAgent
│
├── CommsAgent
│
└── SubmissionAgent
```

---

## Design Principles

### 1. **Encapsulation** ✅
- All agent configuration stored as instance variables
- Private methods for internal operations
- Public methods for external interface

### 2. **Inheritance** ✅
- Base class provides common initialization
- Subclasses override specific behavior
- Template method pattern for agent creation

### 3. **Abstraction** ✅
- Abstract base class defines contract
- Concrete implementations provide specifics
- Clear separation of concerns

### 4. **Composition** ✅
- Tools injected via dependency injection
- Model factory used for LLM creation
- Prompt manager integrated properly

---

## Implementation Plan

### Step 1: Create Base Agent Class ✅

**File**: `agents-core/agents/base_agent.py`

```python
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from strands_agents import Agent

class BaseAgent(ABC):
    """
    Abstract base class for all BidOpsAI agents.
    
    Provides common initialization, configuration management,
    and agent lifecycle methods.
    
    All concrete agent classes must inherit from this base class.
    """
    
    def __init__(
        self,
        mode: str = "workflow",
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs
    ):
        """
        Initialize base agent with common configuration.
        
        Args:
            mode: Agent mode (workflow/ai_assistant)
            provider: LLM provider
            model_id: Model identifier
            temperature: LLM temperature
            **kwargs: Additional configuration
        """
        # Store configuration as instance variables
        self._mode = mode
        self._provider = provider
        self._model_id = model_id
        self._temperature = temperature
        self._config = kwargs
        
        # Initialize components (lazy loading)
        self._agent: Optional[Agent] = None
        self._tools: Optional[List] = None
        self._model = None
        self._system_prompt: Optional[str] = None
        
        # Validate configuration
        self._validate_config()
        
    @property
    def mode(self) -> str:
        """Get agent mode."""
        return self._mode
    
    @property
    def agent_name(self) -> str:
        """Get agent name (implemented by subclasses)."""
        return self.__class__.__name__.replace("Agent", "").lower()
    
    @abstractmethod
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """
        Get agent-specific configuration.
        
        Subclasses must implement to provide agent-specific settings.
        """
        pass
    
    def _validate_config(self) -> None:
        """Validate agent configuration."""
        if self._mode not in ["workflow", "ai_assistant"]:
            raise ValueError(f"Invalid mode: {self._mode}")
    
    def _load_tools(self) -> List:
        """Load tools for this agent."""
        from agents_core.tools.tool_manager import get_tool_manager
        tool_manager = get_tool_manager()
        return tool_manager.get_agent_tools(self.agent_name, self._mode)
    
    def _load_system_prompt(self) -> str:
        """Load system prompt for this agent."""
        from agents_core.prompts.prompt_manager import get_agent_prompt
        return get_agent_prompt(self.agent_name, self._mode)
    
    def _create_model(self):
        """Create LLM model for this agent."""
        from agents_core.llm.model_factory import ModelFactory
        return ModelFactory.create_model(
            provider=self._provider,
            model_id=self._model_id,
            temperature=self._temperature
        )
    
    def _build_agent(self) -> Agent:
        """
        Build Strands Agent instance (Template Method).
        
        This is the core template method that orchestrates agent creation.
        Subclasses can override specific steps if needed.
        """
        # Load tools
        if self._tools is None:
            self._tools = self._load_tools()
        
        # Load system prompt
        if self._system_prompt is None:
            self._system_prompt = self._load_system_prompt()
        
        # Create model
        if self._model is None:
            self._model = self._create_model()
        
        # Get agent-specific configuration
        agent_config = self._get_agent_specific_config()
        
        # Create Strands Agent
        return Agent(
            name=self.agent_name,
            model=self._model,
            system_prompt=self._system_prompt,
            tools=self._tools,
            **agent_config
        )
    
    def get_agent(self) -> Agent:
        """
        Get Strands Agent instance (lazy initialization).
        
        Returns:
            Configured Strands Agent ready for use
        """
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent
    
    async def ainvoke(self, input_data: Any) -> Any:
        """
        Invoke agent asynchronously.
        
        Args:
            input_data: Input for agent
            
        Returns:
            Agent execution result
        """
        agent = self.get_agent()
        return await agent.ainvoke(input_data)
    
    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(mode={self._mode})"
```

### Step 2: Refactor Each Agent to OOP Class ✅

#### 2.1 ParserAgent
**File**: `agents-core/agents/parser_agent.py`

```python
from typing import Optional, Dict, Any
from agents_core.agents.base_agent import BaseAgent

class ParserAgent(BaseAgent):
    """
    Parser Agent - Document Processing Specialist.
    
    Processes documents using Bedrock Data Automation MCP tools.
    """
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """Parser-specific configuration."""
        return {
            "max_tool_iterations": 20,
            "require_tool_approval": False
        }

# Factory function for backward compatibility
def create_parser_agent(
    mode: str = "workflow",
    provider: Optional[str] = None,
    model_id: Optional[str] = None
) -> ParserAgent:
    """Factory function for creating ParserAgent (backward compatibility)."""
    return ParserAgent(mode=mode, provider=provider, model_id=model_id)
```

#### 2.2 AnalysisAgent
**File**: `agents-core/agents/analysis_agent.py`

```python
from typing import Optional, Dict, Any
from agents_core.agents.base_agent import BaseAgent

class AnalysisAgent(BaseAgent):
    """
    Analysis Agent - Document Analysis Specialist.
    
    Analyzes RFP/Bid documents to extract structured information.
    """
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """Analysis-specific configuration."""
        return {
            "max_tool_iterations": 30,
            "require_tool_approval": False
        }

# Factory function for backward compatibility
def create_analysis_agent(
    mode: str = "workflow",
    provider: Optional[str] = None,
    model_id: Optional[str] = None
) -> AnalysisAgent:
    """Factory function for creating AnalysisAgent (backward compatibility)."""
    return AnalysisAgent(mode=mode, provider=provider, model_id=model_id)
```

#### 2.3 KnowledgeAgent
**File**: `agents-core/agents/knowledge_agent.py`

```python
from typing import Optional, Dict, Any
from agents_core.agents.base_agent import BaseAgent

class KnowledgeAgent(BaseAgent):
    """
    Knowledge Agent - Knowledge Base Query Specialist.
    
    Queries AWS Bedrock Knowledge Bases for historical information.
    """
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """Knowledge-specific configuration."""
        return {
            "max_tool_iterations": 10,
            "require_tool_approval": False
        }

# Factory function for backward compatibility
def create_knowledge_agent(
    mode: str = "workflow",
    provider: Optional[str] = None,
    model_id: Optional[str] = None
) -> KnowledgeAgent:
    """Factory function for creating KnowledgeAgent (backward compatibility)."""
    return KnowledgeAgent(mode=mode, provider=provider, model_id=model_id)
```

#### 2.4 ContentAgent (with Composition)
**File**: `agents-core/agents/content_agent.py`

```python
from typing import Optional, Dict, Any, List
from agents_core.agents.base_agent import BaseAgent
from agents_core.agents.knowledge_agent import KnowledgeAgent

class ContentAgent(BaseAgent):
    """
    Content Agent - Artifact Generation Specialist.
    
    Generates bid artifacts using historical data and structured outputs.
    Uses KnowledgeAgent via composition for KB queries.
    """
    
    def __init__(
        self,
        mode: str = "workflow",
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        **kwargs
    ):
        """Initialize ContentAgent with embedded KnowledgeAgent."""
        super().__init__(mode, provider, model_id, **kwargs)
        
        # Composition: ContentAgent contains KnowledgeAgent
        self._knowledge_agent = KnowledgeAgent(
            mode=mode,
            provider=provider,
            model_id=model_id
        )
    
    def _load_tools(self) -> List:
        """Load tools including Knowledge Agent."""
        tools = super()._load_tools()
        
        # Add Knowledge Agent as a tool
        tools.append({
            "name": "query_knowledge_agent",
            "description": "Query Knowledge Agent for historical content",
            "agent": self._knowledge_agent.get_agent()
        })
        
        return tools
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """Content-specific configuration."""
        return {
            "max_tool_iterations": 40,
            "require_tool_approval": False
        }
    
    @property
    def knowledge_agent(self) -> KnowledgeAgent:
        """Get embedded Knowledge Agent."""
        return self._knowledge_agent

# Factory function for backward compatibility
def create_content_agent(
    mode: str = "workflow",
    provider: Optional[str] = None,
    model_id: Optional[str] = None
) -> ContentAgent:
    """Factory function for creating ContentAgent (backward compatibility)."""
    return ContentAgent(mode=mode, provider=provider, model_id=model_id)
```

#### 2.5 ComplianceAgent
**File**: `agents-core/agents/compliance_agent.py`

```python
from typing import Optional, Dict, Any
from agents_core.agents.base_agent import BaseAgent

class ComplianceAgent(BaseAgent):
    """
    Compliance Agent - Standards Verification Specialist.
    
    Verifies artifacts against compliance requirements and standards.
    """
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """Compliance-specific configuration."""
        return {
            "max_tool_iterations": 25,
            "require_tool_approval": False
        }

# Factory function for backward compatibility
def create_compliance_agent(
    mode: str = "workflow",
    provider: Optional[str] = None,
    model_id: Optional[str] = None
) -> ComplianceAgent:
    """Factory function for creating ComplianceAgent (backward compatibility)."""
    return ComplianceAgent(mode=mode, provider=provider, model_id=model_id)
```

#### 2.6 QAAgent
**File**: `agents-core/agents/qa_agent.py`

```python
from typing import Optional, Dict, Any
from agents_core.agents.base_agent import BaseAgent

class QAAgent(BaseAgent):
    """
    QA Agent - Quality Assurance Specialist.
    
    Verifies artifacts meet requirements and quality standards.
    """
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """QA-specific configuration."""
        return {
            "max_tool_iterations": 30,
            "require_tool_approval": False
        }

# Factory function for backward compatibility
def create_qa_agent(
    mode: str = "workflow",
    provider: Optional[str] = None,
    model_id: Optional[str] = None
) -> QAAgent:
    """Factory function for creating QAAgent (backward compatibility)."""
    return QAAgent(mode=mode, provider=provider, model_id=model_id)
```

#### 2.7 CommsAgent
**File**: `agents-core/agents/comms_agent.py`

```python
from typing import Optional, Dict, Any
from agents_core.agents.base_agent import BaseAgent

class CommsAgent(BaseAgent):
    """
    Comms Agent - Communications and Notifications.
    
    Handles Slack channels, email notifications, and database notification records.
    """
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """Comms-specific configuration."""
        return {
            "max_tool_iterations": 15,
            "require_tool_approval": False
        }

# Factory function for backward compatibility
def create_comms_agent(
    mode: str = "workflow",
    provider: Optional[str] = None,
    model_id: Optional[str] = None
) -> CommsAgent:
    """Factory function for creating CommsAgent (backward compatibility)."""
    return CommsAgent(mode=mode, provider=provider, model_id=model_id)
```

#### 2.8 SubmissionAgent
**File**: `agents-core/agents/submission_agent.py`

```python
from typing import Optional, Dict, Any
from agents_core.agents.base_agent import BaseAgent

class SubmissionAgent(BaseAgent):
    """
    Submission Agent - Bid Submission via Email.
    
    Handles email draft generation, attachment preparation, and email sending.
    """
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """Submission-specific configuration."""
        return {
            "max_tool_iterations": 20,
            "require_tool_approval": False
        }

# Factory function for backward compatibility
def create_submission_agent(
    mode: str = "workflow",
    provider: Optional[str] = None,
    model_id: Optional[str] = None
) -> SubmissionAgent:
    """Factory function for creating SubmissionAgent (backward compatibility)."""
    return SubmissionAgent(mode=mode, provider=provider, model_id=model_id)
```

#### 2.9 SupervisorAgent
**File**: `agents-core/agents/supervisor_agent.py`

```python
from typing import Optional, Dict, Any
import logging
from agents_core.agents.base_agent import BaseAgent
from agents_core.core.config import get_config

logger = logging.getLogger(__name__)

class SupervisorAgent(BaseAgent):
    """
    Supervisor Agent - Workflow Orchestrator.
    
    Main orchestration agent that controls the entire workflow execution.
    Acts as the entry point in the Strands Agent Graph.
    """
    
    def __init__(
        self,
        mode: str = "workflow",
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs
    ):
        """Initialize Supervisor with specific configuration."""
        # Get config defaults for supervisor
        config = get_config()
        
        if provider is None:
            provider = config.get("agents.supervisor.provider", "bedrock")
        
        if model_id is None:
            model_id = config.get(
                "agents.supervisor.model_id",
                "anthropic.claude-3-5-sonnet-20241022-v2:0"
            )
        
        if temperature is None:
            temperature = config.get("agents.supervisor.temperature", 0.3)
        
        super().__init__(
            mode=mode,
            provider=provider,
            model_id=model_id,
            temperature=temperature,
            **kwargs
        )
        
        logger.info(f"SupervisorAgent initialized (mode: {mode})")
    
    def _get_agent_specific_config(self) -> Dict[str, Any]:
        """Supervisor-specific configuration."""
        return {
            "max_tool_iterations": 50,  # Can make many DB queries
            "require_tool_approval": False,
        }

# Factory functions for backward compatibility
def create_supervisor_agent(
    mode: str = "workflow",
    provider: Optional[str] = None,
    model_id: Optional[str] = None,
    temperature: Optional[float] = None,
    **model_kwargs
) -> SupervisorAgent:
    """Factory function for creating SupervisorAgent (backward compatibility)."""
    return SupervisorAgent(
        mode=mode,
        provider=provider,
        model_id=model_id,
        temperature=temperature,
        **model_kwargs
    )

def create_ai_assistant_supervisor(
    provider: Optional[str] = None,
    model_id: Optional[str] = None,
    temperature: Optional[float] = None,
    **model_kwargs
) -> SupervisorAgent:
    """Factory function for AI Assistant Supervisor."""
    return SupervisorAgent(
        mode="ai_assistant",
        provider=provider,
        model_id=model_id,
        temperature=temperature,
        **model_kwargs
    )
```

### Step 3: Update Graph Builder ✅

**File**: `agents-core/supervisors/workflow/agent_builder.py`

Update to work with both class instances and factory functions:

```python
# Both approaches now work:

# Option 1: Direct class instantiation (preferred OOP way)
parser_agent = ParserAgent(mode="workflow")
analysis_agent = AnalysisAgent(mode="workflow")

# Option 2: Factory functions (backward compatibility)
parser_agent = create_parser_agent(mode="workflow")
analysis_agent = create_analysis_agent(mode="workflow")

# Both return class instances, both work the same way
```

### Step 4: Update __init__.py Exports ✅

**File**: `agents-core/agents/__init__.py`

```python
"""Agent implementations package."""

# Import classes (primary exports)
from agents_core.agents.base_agent import BaseAgent
from agents_core.agents.parser_agent import ParserAgent
from agents_core.agents.analysis_agent import AnalysisAgent
from agents_core.agents.knowledge_agent import KnowledgeAgent
from agents_core.agents.content_agent import ContentAgent
from agents_core.agents.compliance_agent import ComplianceAgent
from agents_core.agents.qa_agent import QAAgent
from agents_core.agents.comms_agent import CommsAgent
from agents_core.agents.submission_agent import SubmissionAgent
from agents_core.agents.supervisor_agent import SupervisorAgent

# Import factory functions (backward compatibility)
from agents_core.agents.parser_agent import create_parser_agent
from agents_core.agents.analysis_agent import create_analysis_agent
from agents_core.agents.knowledge_agent import create_knowledge_agent
from agents_core.agents.content_agent import create_content_agent
from agents_core.agents.compliance_agent import create_compliance_agent
from agents_core.agents.qa_agent import create_qa_agent
from agents_core.agents.comms_agent import create_comms_agent
from agents_core.agents.submission_agent import create_submission_agent
from agents_core.agents.supervisor_agent import (
    create_supervisor_agent,
    create_ai_assistant_supervisor
)

__all__ = [
    # Base class
    "BaseAgent",
    
    # Agent classes (OOP)
    "SupervisorAgent",
    "ParserAgent",
    "AnalysisAgent",
    "KnowledgeAgent",
    "ContentAgent",
    "ComplianceAgent",
    "QAAgent",
    "CommsAgent",
    "SubmissionAgent",
    
    # Factory functions (backward compatibility)
    "create_supervisor_agent",
    "create_ai_assistant_supervisor",
    "create_parser_agent",
    "create_analysis_agent",
    "create_knowledge_agent",
    "create_content_agent",
    "create_compliance_agent",
    "create_qa_agent",
    "create_comms_agent",
    "create_submission_agent",
]
```

---

## Benefits of OOP Refactor

### 1. **Encapsulation** ✅
```python
# Before: Scattered global calls
def create_analysis_agent(mode, provider, model_id):
    tool_manager = get_tool_manager()  # Global
    tools = tool_manager.get_agent_tools("analysis", mode)
    return Agent(...)

# After: Encapsulated in class
class AnalysisAgent(BaseAgent):
    def __init__(self, mode, provider, model_id):
        super().__init__(mode, provider, model_id)
        # All state stored in instance variables
    
    def _load_tools(self):
        # Internal method, encapsulated
        return super()._load_tools()
```

### 2. **Inheritance** ✅
```python
# Common functionality in base class
class BaseAgent:
    def _load_tools(self): ...
    def _load_system_prompt(self): ...
    def _create_model(self): ...
    def get_agent(self): ...

# Subclasses inherit and extend
class ParserAgent(BaseAgent):
    def _get_agent_specific_config(self):
        return {"max_tool_iterations": 20}
```

### 3. **Composition** ✅
```python
# ContentAgent contains KnowledgeAgent
class ContentAgent(BaseAgent):
    def __init__(self, ...):
        super().__init__(...)
        self._knowledge_agent = KnowledgeAgent(...)  # Composition
    
    @property
    def knowledge_agent(self):
        return self._knowledge_agent
```

### 4. **Testability** ✅
```python
# Easy to mock and test
def test_analysis_agent():
    agent = AnalysisAgent(mode="workflow")
    assert agent.mode == "workflow"
    assert agent.agent_name == "analysis"
    
    # Can mock internal methods
    with patch.object(agent, '_load_tools') as mock_tools:
        mock_tools.return_value = []
        agent.get_agent()
```

### 5. **Extensibility** ✅
```python
# Easy to extend and customize
class CustomAnalysisAgent(AnalysisAgent):
    def _load_tools(self):
        tools = super()._load_tools()
        tools.append(my_custom_tool)
        return tools
```

---

## Migration Strategy

### Backward Compatibility ✅

All existing code continues to work:

```python
# Old way (factory function) - STILL WORKS
from agents_core.agents import create_analysis_agent
agent = create_analysis_agent(mode="workflow")

# New way (OOP class) - RECOMMENDED
from agents_core.agents import AnalysisAgent
agent = AnalysisAgent(mode="workflow")

# Both return the same type and work identically
```

### No Breaking Changes ✅

- Factory functions remain as thin wrappers
- Graph builder works with both approaches
- All existing imports continue to work
- Tests don't need immediate updates

---

## Execution Steps

1. ✅ Create `base_agent.py` with `BaseAgent` abstract class
2. ✅ Refactor `parser_agent.py` to `ParserAgent` class
3. ✅ Refactor `analysis_agent.py` to `AnalysisAgent` class
4. ✅ Refactor `knowledge_agent.py` to `KnowledgeAgent` class
5. ✅ Refactor `content_agent.py` to `ContentAgent` class (with composition)
6. ✅ Refactor `compliance_agent.py` to `ComplianceAgent` class
7. ✅ Refactor `qa_agent.py` to `QAAgent` class
8. ✅ Refactor `comms_agent.py` to `CommsAgent` class
9. ✅ Refactor `submission_agent.py` to `SubmissionAgent` class
10. ✅ Refactor `supervisor_agent.py` to `SupervisorAgent` class
11. ✅ Update `__init__.py` exports
12. ✅ Validate graph builder compatibility
13. ✅ Run validation tests

---

## Success Criteria

- ✅ All agents inherit from `BaseAgent`
- ✅ No global variables or scattered function calls
- ✅ Proper encapsulation of state
- ✅ Template method pattern implemented
- ✅ Composition used where appropriate (ContentAgent + KnowledgeAgent)
- ✅ Factory functions preserved for backward compatibility
- ✅ No breaking changes to existing code
- ✅ All validation tests pass

---

**Next**: Begin implementation with Step 1 (Create BaseAgent)