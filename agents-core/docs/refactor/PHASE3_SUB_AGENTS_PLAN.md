# Phase 3: Sub-Agent Refactoring Plan

**Status**: 🔄 IN PROGRESS  
**Phase**: 3 of 6 - Convert Sub-Agents to Strands Agent Pattern

---

## Problem Analysis

### Current Implementation (INCORRECT)

All sub-agents currently follow this anti-pattern:

```python
class ParserAgent:  # ❌ Class-based orchestrator
    def __init__(self, mode, provider, model_id, **kwargs):
        self.agent = Agent(model=self.model, tools=self.tools)  # Creates agent but never uses it
    
    async def execute(self, workflow_id, task_id, ...):  # ❌ Hardcoded orchestration
        # Step 1: Mark task in progress (hardcoded)
        await self._update_task_status(...)
        
        # Step 2: Fetch documents (hardcoded)
        documents = await self._fetch_project_documents(...)
        
        # Step 3: Process documents (hardcoded)
        results = await self._process_documents(...)
        
        # Step 4: Update task (hardcoded)
        await self._update_task_status(...)
        
        return {"success": True, ...}
```

**Issues**:
1. ❌ Returns class instance, not Strands `Agent`
2. ❌ LLM agent created but never used for decisions
3. ❌ All logic is hardcoded Python orchestration
4. ❌ Violates Strands Agent Graph pattern (no LLM autonomy)

### Target Implementation (CORRECT)

```python
def create_parser_agent(
    mode: str = "workflow",
    provider: Optional[str] = None,
    model_id: Optional[str] = None
) -> Agent:  # ✅ Returns Strands Agent directly
    """Factory function returns Strands Agent instance."""
    
    tool_manager = get_tool_manager()
    tools = tool_manager.get_agent_tools("parser", mode)
    system_prompt = get_agent_prompt("parser", mode)
    model = ModelFactory.create_model(provider, model_id)
    
    return Agent(  # ✅ Return Agent instance
        name="parser",
        model=model,
        system_prompt=system_prompt,
        tools=tools  # DB tools, S3 tools, Bedrock DA MCP tools
    )
```

**Benefits**:
1. ✅ Returns pure Strands `Agent` instance
2. ✅ LLM makes decisions using tools autonomously
3. ✅ System prompt guides agent behavior
4. ✅ Follows Strands Agent Graph pattern correctly

---

## Refactoring Strategy

### Option A: Pure Strands Agent Pattern (RECOMMENDED)

**Approach**: Remove all orchestration classes, return pure Strands Agents

**Pros**:
- ✅ True LLM-powered autonomy
- ✅ Follows Strands documentation correctly
- ✅ Simpler codebase (fewer classes)
- ✅ Matches requirements document

**Cons**:
- ⚠️ Requires trusting LLM to use tools correctly
- ⚠️ Need comprehensive system prompts
- ⚠️ May need more testing/iteration

**Implementation**:
```python
# agents-core/agents/parser_agent.py
def create_parser_agent(mode, provider, model_id) -> Agent:
    """Pure Strands Agent - LLM makes all decisions."""
    return Agent(
        name="parser",
        model=ModelFactory.create_model(provider, model_id),
        system_prompt=get_agent_prompt("parser", mode),
        tools=get_tool_manager().get_agent_tools("parser", mode)
    )
```

### Option B: Hybrid Pattern (FALLBACK)

**Approach**: Keep classes but expose Strands Agent

**Pros**:
- ✅ Maintains existing error handling
- ✅ Preserves SSE progress updates
- ✅ Less risky migration

**Cons**:
- ❌ Still not true Strands pattern
- ❌ More code to maintain
- ❌ Doesn't fully leverage LLM autonomy

**NOT RECOMMENDED** - Violates Strands architecture

---

## Decision: Option A (Pure Strands Agent)

Based on requirements document emphasis on "LLM-powered decision making" and AWS Strands best practices, we will implement **Option A**.

---

## Phase 3 Execution Plan

### Step 1: Update System Prompts (Sub-Agents)

Each agent needs comprehensive prompts that guide LLM on:
- What tools are available
- How to use tools correctly
- What output format to return
- Error handling strategies

**Files to Update**:
```
agents-core/prompts/workflow/
├── parser.txt          # Add MCP tool usage guidance
├── analysis.txt        # Add structured output format
├── content.txt         # Add Knowledge Agent invocation
├── compliance.txt      # Add feedback structure
├── qa.txt              # Add QA check format
├── comms.txt           # Add Slack MCP tool usage
└── submission.txt      # Add email draft format
```

### Step 2: Refactor Agent Files

Convert each agent to factory function pattern:

**Parser Agent** (`agents-core/agents/parser_agent.py`):
- DELETE: `ParserAgent` class (all 467 lines)
- CREATE: `create_parser_agent()` factory (returns `Agent`)
- UPDATE: System prompt with Bedrock DA MCP tool documentation

**Analysis Agent** (`agents-core/agents/analysis_agent.py`):
- DELETE: `AnalysisAgent` class (all 657 lines)
- CREATE: `create_analysis_agent()` factory (returns `Agent`)
- UPDATE: System prompt with structured output guidance

**Content Agent** (`agents-core/agents/content_agent.py`):
- DELETE: `ContentAgent` class (all 707 lines)
- CREATE: `create_content_agent()` factory (returns `Agent`)
- UPDATE: System prompt with Knowledge Agent usage pattern

**Compliance Agent** (`agents-core/agents/compliance_agent.py`):
- DELETE: `ComplianceAgent` class (all 529 lines)
- CREATE: `create_compliance_agent()` factory (returns `Agent`)
- UPDATE: System prompt with feedback format

**QA Agent** (`agents-core/agents/qa_agent.py`):
- DELETE: `QAAgent` class (all 608 lines)
- CREATE: `create_qa_agent()` factory (returns `Agent`)
- UPDATE: System prompt with QA check format

**Comms Agent** (`agents-core/agents/comms_agent.py`):
- DELETE: `CommsAgent` class
- CREATE: `create_comms_agent()` factory (returns `Agent`)
- UPDATE: System prompt with Slack MCP tool documentation

**Submission Agent** (`agents-core/agents/submission_agent.py`):
- DELETE: `SubmissionAgent` class
- CREATE: `create_submission_agent()` factory (returns `Agent`)
- UPDATE: System prompt with email draft format

**Knowledge Agent** (`agents-core/agents/knowledge_agent.py`):
- DELETE: `KnowledgeAgent` class
- CREATE: `create_knowledge_agent()` factory (returns `Agent`)
- UPDATE: System prompt with Bedrock KB querying guidance

### Step 3: Update Tool Configurations

Verify each agent has correct tools registered in `tool_config.py`:

- Parser: DB tools + S3 tools + Bedrock DA MCP
- Analysis: DB tools + S3 tools
- Content: DB tools + S3 tools + Artifact creation tools
- Knowledge: KB query tools (Bedrock Knowledge Base)
- Compliance: DB tools + Artifact retrieval tools
- QA: DB tools + Artifact retrieval tools
- Comms: DB tools + Slack MCP + Notification tools
- Submission: DB tools + S3 tools + Email tools

### Step 4: Create System Prompt Templates

Each prompt must include:

1. **Role Definition**: What the agent does
2. **Available Tools**: List with usage examples
3. **Decision Process**: Step-by-step thinking framework
4. **Output Format**: Structured output requirements (Pydantic models)
5. **Error Handling**: What to do on failures
6. **Examples**: Sample tool invocations and responses

**Template Structure**:
```
You are the [Agent Name] for BidOpsAI, specialized in [domain].

# YOUR ROLE
[Role description]

# AVAILABLE TOOLS
[List of tools with descriptions]

# DECISION PROCESS
1. [Step 1]
2. [Step 2]
...

# OUTPUT FORMAT
[Pydantic model schema or JSON structure]

# ERROR HANDLING
[Guidance on handling errors]

# EXAMPLES
[Sample tool uses and outputs]
```

---

## Implementation Timeline

**Estimated Duration**: 2-3 hours

### Batch 1: Parser + Analysis (30 min)
- Update prompts
- Refactor to factory functions
- Test agent creation

### Batch 2: Content + Knowledge (45 min)
- Update prompts
- Refactor to factory functions
- Handle Content → Knowledge interaction

### Batch 3: Compliance + QA (45 min)
- Update prompts
- Refactor to factory functions
- Test feedback formats

### Batch 4: Comms + Submission (45 min)
- Update prompts with MCP tool docs
- Refactor to factory functions
- Test MCP tool access

### Testing & Validation (30 min)
- Verify all factory functions return `Agent` instances
- Test agent creation with different modes
- Validate tool loading

---

## Risks & Mitigation

### Risk 1: LLM Not Using Tools Correctly
**Mitigation**: Comprehensive system prompts with examples

### Risk 2: Loss of SSE Progress Updates
**Mitigation**: Agents can still emit SSE events via tools or direct SDK calls

### Risk 3: Complex Error Handling Lost
**Mitigation**: System prompts include error handling guidance

### Risk 4: Breaking Graph Integration
**Mitigation**: Phase 4 will rebuild graph with new agent pattern

---

## Success Criteria

- [ ] All agent files use factory function pattern
- [ ] All factory functions return pure `Agent` instances
- [ ] No class-based orchestrators remain
- [ ] System prompts are comprehensive
- [ ] Tool configurations are correct
- [ ] Agent creation tests pass
- [ ] Ready for Phase 4 (Graph building)

---

## Next Steps

After Phase 3 completion, proceed to:

**Phase 4**: Build Strands Graph with supervisor entry point
**Phase 5**: Update FastAPI `/invocations` endpoint
**Phase 6**: End-to-end testing

---

## Notes

- This is the most critical refactor phase
- Requires trust in LLM autonomy
- Aligns with AWS Strands best practices
- Fulfills requirements document mandate for LLM-powered agents