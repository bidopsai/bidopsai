# BidOpsAI Agent System

AWS AgentCore-based agentic system for automated bid preparation and workflow orchestration.

## Overview

This system provides intelligent automation for the complete bid preparation lifecycle, from document processing to artifact generation, compliance checking, and submission.

## Architecture

- **Supervisor Agents**: Orchestrate multi-agent workflows
  - Workflow Supervisor: Main bid preparation workflow
  - AI Assistant Supervisor: Conversational AI assistant
  
- **Sub-Agents**: Specialized domain agents
  - Parser Agent: Document processing
  - Analysis Agent: RFP/Bid analysis
  - Content Agent: Artifact generation
  - Knowledge Agent: Knowledge base retrieval
  - Compliance Agent: Compliance verification
  - QA Agent: Quality assurance
  - Comms Agent: Notifications and communications
  - Submission Agent: Bid submission

## Technology Stack

- **Framework**: AWS Bedrock AgentCore SDK
- **Agent Framework**: Strands Agents (Graph pattern)
- **API**: FastAPI with SSE streaming
- **Database**: PostgreSQL with Prisma ORM
- **Observability**: OpenTelemetry + LangFuse
- **Python**: 3.12+
- **Package Manager**: UV

## Getting Started

### Prerequisites

- Python 3.12+
- UV package manager
- PostgreSQL database
- AWS account with Bedrock access

### Installation

```bash
# Install dependencies
uv sync

# Run migrations
prisma migrate dev

# Start development server
uvicorn supervisors.workflow.agent_executor:app --reload
```

### Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/bidopsai

# AgentCore Runtime
AGENTCORE_RUNTIME_URL=https://your-runtime.amazonaws.com

# Observability
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test suite
pytest tests/unit/
pytest tests/integration/
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy .
```

## Deployment

### Docker Build

```bash
# Build workflow supervisor
podman build -f infra/docker/agents-core/workflow/Dockerfile -t bidopsai-workflow:latest .

# Build AI assistant supervisor
podman build -f infra/docker/agents-core/ai_assistant/Dockerfile -t bidopsai-assistant:latest .
```

### AWS AgentCore Runtime

Deploy to AWS AgentCore Runtime using the provided scripts:

```bash
# Build and push to ECR
./agents-core/scripts/deploy/build_and_push_to_ecr.sh

# Update AgentCore runtime
./agents-core/scripts/deploy/update_agentcore_runtime.sh
```

## Project Structure

```
agents-core/
├── agents/           # Sub-agent implementations
├── supervisors/      # Supervisor agent implementations
├── tools/            # Tool implementations (DB, S3, Email, etc.)
├── core/             # Core infrastructure (memory, observability)
├── models/           # Pydantic data models
├── prompts/          # System prompts library
├── tests/            # Test suites
└── scripts/          # Deployment and utility scripts
```

## Documentation

- [Architecture Documentation](./docs/)
- [API Reference](./docs/api/)
- [Deployment Guide](./docs/deployment/)
- [Development Guide](./docs/development/)

## License

MIT License - see LICENSE file for details

## Support

For support, email support@bidopsai.com or open an issue on GitHub.