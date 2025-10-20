# Agent Prompts Directory

This directory contains system prompts for all agents in the BidOpsAI AgentCore system.

## Structure

```
prompts/
├── workflow/           # Workflow mode prompts
│   ├── supervisor.txt  # Workflow Supervisor Agent
│   ├── parser.txt      # Parser Agent
│   ├── analysis.txt    # Analysis Agent
│   ├── content.txt     # Content Agent
│   ├── knowledge.txt   # Knowledge Agent
│   ├── compliance.txt  # Compliance Agent
│   ├── qa.txt          # QA Agent
│   ├── comms.txt       # Communications Agent
│   └── submission.txt  # Submission Agent
├── ai_assistant/       # AI Assistant mode prompts
│   ├── supervisor.txt  # AI Assistant Supervisor
│   └── [agent].txt     # Agent prompts (same names as workflow)
└── prompt_manager.py   # Prompt loading and management
```

## Prompt Format

Each prompt file is a plain text file with:
- Role definition
- Responsibilities
- Tools available
- Output format expectations
- Context variables (using `{variable_name}` syntax)

## Context Variables

Common context variables injected at runtime:
- `{project_name}`: Name of current project
- `{user_name}`: Name of user
- `{current_step}`: Current workflow step
- `{previous_outputs}`: Summary of previous agent outputs
- `{completed_tasks}`: List of completed tasks

## Usage

```python
from agents_core.prompts.prompt_manager import get_agent_prompt

# Get prompt with context
prompt = get_agent_prompt(
    agent_name="parser",
    mode="workflow",
    project_name="ABC Corp RFP",
    user_name="John Doe",
    current_step="document_parsing"
)
```

## Adding New Prompts

1. Create a new `.txt` file in appropriate directory
2. Use existing prompts as templates
3. Include context variables as needed
4. Restart application to load new prompts

## Prompt Guidelines

1. **Be Specific**: Clearly define agent's role and boundaries
2. **Use Structured Outputs**: Request JSON/Pydantic models where needed
3. **Include Examples**: Show expected output formats
4. **Error Handling**: Specify how to report errors
5. **Tool Usage**: List available tools and when to use them

## Mode Differences

### Workflow Mode
- Sequential execution pattern
- Focus on completing specific tasks
- Less conversational, more transactional
- Clear handoff points between agents

### AI Assistant Mode
- Intent-driven routing
- Conversational responses
- Can handle multi-turn dialogues
- More context-aware of user history

## Testing Prompts

Use the prompt manager's validation:

```python
from agents_core.prompts.prompt_manager import get_prompt_manager

pm = get_prompt_manager()
validation = pm.validate_prompts()
print(validation)
```

## Prompt Versions

Prompts are versioned through git. To rollback:
```bash
git checkout <commit> agents-core/prompts/
```

## Best Practices

1. **Keep prompts under 4000 tokens** for most LLMs
2. **Use clear section headings** (#, ##, ###)
3. **Provide structured output examples**
4. **Include error handling instructions**
5. **Test with actual workflow scenarios**
6. **Document any custom context variables**

## Notes

- Prompts are loaded once at startup and cached
- Use `pm.reload_prompts()` to reload without restart (dev only)
- Fallback prompts are generated if file not found
- Supervisor prompts are more complex than agent prompts