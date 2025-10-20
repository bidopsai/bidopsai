# BidOps.AI Scripts

Automation scripts for infrastructure and deployment tasks.

## AWS ECR Scripts

Scripts for building and deploying Strands AI agents to AWS Elastic Container Registry (ECR).

### Prerequisites

- Docker 20.10+ with Buildx plugin
- AWS CLI 2.0+
- jq 1.6+
- AWS credentials configured with ECR permissions

### Scripts

#### `build-agent.sh` - Build ARM64 Docker Image

Build ARM64-compatible Docker image for Strands agent using Docker Buildx.

```bash
./scripts/build-agent.sh <agent-directory> <repository-name> [tag] [options]
```

**Arguments**:
- `agent-directory`: Path to Strands agent project containing Dockerfile
- `repository-name`: ECR repository name (without registry URI)
- `tag`: Docker image tag (default: `latest`)

**Options**:
- `--no-cache`: Disable Docker build cache
- `--builder NAME`: Custom buildx builder name (default: `arm64-builder`)

**Examples**:
```bash
./scripts/build-agent.sh ./agentcore strands-agents
./scripts/build-agent.sh ./agentcore strands-agents v1.0.0
./scripts/build-agent.sh ./agentcore strands-agents latest --no-cache
```

---

#### `push-to-ecr.sh` - Push Image to ECR

Authenticate with AWS ECR and push Docker image to ECR repository.

```bash
./scripts/push-to-ecr.sh <image-name> <repository-name> [region] [options]
```

**Arguments**:
- `image-name`: Local Docker image name (e.g., `strands-agents:latest`)
- `repository-name`: ECR repository name
- `region`: AWS region for ECR (default: `$AWS_REGION` or `us-east-1`)

**Options**:
- `--no-verify`: Skip post-push verification

**Examples**:
```bash
./scripts/push-to-ecr.sh strands-agents:latest strands-agents
./scripts/push-to-ecr.sh strands-agents:v1.0.0 strands-agents us-west-2
```

---

#### `build-and-push.sh` - Combined Workflow

Build ARM64 image and push to ECR in one command.

```bash
./scripts/build-and-push.sh <agent-directory> <repository-name> [tag] [region] [options]
```

**Arguments**:
- `agent-directory`: Path to Strands agent project
- `repository-name`: ECR repository name
- `tag`: Docker image tag (default: `latest`)
- `region`: AWS region (default: `$AWS_REGION` or `us-east-1`)

**Options**:
- `--no-cache`: Disable Docker build cache

**Examples**:
```bash
./scripts/build-and-push.sh ./agentcore strands-agents
./scripts/build-and-push.sh ./agentcore strands-agents v1.0.0 us-east-1
```

---

#### `verify-ecr-image.sh` - Verify Image in ECR

Verify image exists in ECR and display metadata.

```bash
./scripts/verify-ecr-image.sh <repository-name> [tag] [region] [options]
```

**Arguments**:
- `repository-name`: ECR repository name
- `tag`: Image tag to verify (default: `latest`)
- `region`: AWS region (default: `$AWS_REGION` or `us-east-1`)

**Options**:
- `--list-all`: List all tags in repository
- `--json`: Output raw JSON

**Examples**:
```bash
./scripts/verify-ecr-image.sh strands-agents
./scripts/verify-ecr-image.sh strands-agents v1.0.0 us-east-1
./scripts/verify-ecr-image.sh strands-agents --list-all
./scripts/verify-ecr-image.sh strands-agents latest --json
```

---

### Quick Start

Build and push a Strands agent to ECR:

```bash
./scripts/build-and-push.sh ./agentcore strands-agents latest us-east-1
```

Verify the image:

```bash
./scripts/verify-ecr-image.sh strands-agents latest us-east-1
```

---

### AWS Cleanup

#### `clean-bidopsai-stack.sh` - Clean BidOps.AI Infrastructure

Remove all BidOps.AI infrastructure stacks from AWS.

```bash
./scripts/clean-bidopsai-stack.sh
```

See script source for details on stack removal order and behavior.

---

## Documentation

For detailed documentation on ECR scripts, see:
- [Feature Spec](../specs/003-specify-scripts-bash/spec.md)
- [Quickstart Guide](../specs/003-specify-scripts-bash/quickstart.md)
- [Technical Research](../specs/003-specify-scripts-bash/research.md)
- [Data Model](../specs/003-specify-scripts-bash/data-model.md)
