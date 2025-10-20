# BidOpsAI Deployment Scripts

Deployment scripts for BidOpsAI agents to AWS Bedrock AgentCore Runtime.

## Overview

This directory contains scripts to deploy containerized agents to AWS without using CodeBuild. The deployment process uses:

- **Container Engine**: Podman (preferred) or Docker
- **Package Manager**: UV for fast Python dependency installation
- **Architecture**: ARM64 (required by AWS Bedrock AgentCore in ap-southeast-2)
- **Versioning**: Semantic versioning via environment variables
- **Deployment**: Individual agent deployment support

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **AWS CDK** installed (`npm install -g aws-cdk`)
3. **Podman** or Docker installed
4. **Node.js** and npm for CDK
5. **Environment variables** set for versioning

## Environment Variables

Create a `.env` file or export these variables:

```bash
# Required for workflow agent
export APP_VERSION_WORKFLOW="1.0.0"

# Required for AI assistant agent
export APP_VERSION_AI_ASSISTANT="1.0.0"

# Optional: AWS configuration
export AWS_REGION="ap-southeast-2"
export AWS_ACCOUNT_ID="your-account-id"
export AWS_PROFILE="your-profile-name"
```

## Deployment Process

### Step 1: Deploy Infrastructure

Deploy ECR repositories, IAM roles, S3 buckets, and configuration:

```bash
./deploy-infra.sh <environment>
```

**Example:**
```bash
./deploy-infra.sh dev
```

**What it deploys:**
- ECR repositories for workflow and AI assistant agents
- IAM execution roles with necessary permissions
- S3 buckets for artifacts and documents
- Secrets Manager entries for credentials
- SSM parameters for configuration

### Step 2: Build and Push Docker Images

Build ARM64 Docker images and push to ECR:

```bash
# Build both agents
export APP_VERSION_WORKFLOW="1.0.0"
export APP_VERSION_AI_ASSISTANT="1.0.0"
./build-and-push.sh <environment>

# Build single agent
export APP_VERSION_WORKFLOW="1.0.0"
./build-and-push.sh <environment> workflow

export APP_VERSION_AI_ASSISTANT="1.0.0"
./build-and-push.sh <environment> ai-assistant
```

**Example:**
```bash
# Both agents
export APP_VERSION_WORKFLOW="1.0.0"
export APP_VERSION_AI_ASSISTANT="1.0.0"
./build-and-push.sh dev

# Workflow only
export APP_VERSION_WORKFLOW="1.0.1"
./build-and-push.sh dev workflow
```

**What it does:**
- Builds ARM64 Docker images from `infra/docker/agents-core/<agent>/Dockerfile`
- Tags images with semantic version
- Pushes to ECR repositories
- Verifies successful upload

**Important Notes:**
- Uses `agents-core/` as build context (not project root)
- Builds for `linux/arm64` platform (AgentCore requirement)
- Uses UV for fast dependency installation
- Images are optimized and run as non-root user

### Step 3: Deploy to AgentCore Runtime

Deploy agents to AWS Bedrock AgentCore:

```bash
# Deploy both agents (both version envs must be set)
export APP_VERSION_WORKFLOW="1.0.0"
export APP_VERSION_AI_ASSISTANT="1.0.0"
./deploy-agentcore.sh <environment>

# Deploy single agent
export APP_VERSION_WORKFLOW="1.0.0"
./deploy-agentcore.sh <environment> workflow

export APP_VERSION_AI_ASSISTANT="1.0.0"
./deploy-agentcore.sh <environment> ai-assistant
```

**Example:**
```bash
# Workflow only
export APP_VERSION_WORKFLOW="1.0.0"
./deploy-agentcore.sh dev workflow

# AI Assistant only
export APP_VERSION_AI_ASSISTANT="1.0.0"
./deploy-agentcore.sh dev ai-assistant

# Both agents
export APP_VERSION_WORKFLOW="1.0.0"
export APP_VERSION_AI_ASSISTANT="1.0.0"
./deploy-agentcore.sh dev
```

**What it does:**
- Verifies Docker images exist in ECR
- Deploys AgentCore runtime with specified images
- Creates/updates runtime configurations
- Provides runtime ARN and endpoint information

## Complete Deployment Example

```bash
# Set versions
export APP_VERSION_WORKFLOW="1.0.0"
export APP_VERSION_AI_ASSISTANT="1.0.0"

# 1. Deploy infrastructure (one-time setup)
./deploy-infra.sh dev

# 2. Build and push Docker images
./build-and-push.sh dev

# 3. Deploy to AgentCore
./deploy-agentcore.sh dev
```

## Updating Existing Deployment

To update an existing agent with a new version:

```bash
# 1. Update version
export APP_VERSION_WORKFLOW="1.0.1"

# 2. Build and push new image
./build-and-push.sh dev workflow

# 3. Update runtime
./deploy-agentcore.sh dev workflow
```

## Architecture & Platform Notes

### ARM64 Requirement
AWS Bedrock AgentCore in `ap-southeast-2` requires ARM64 architecture. All images are built with:
```bash
--platform linux/arm64
```

### Testing on Apple Silicon (M1/M2/M3)
Apple Silicon Macs use ARM64 natively, so you can test locally:
```bash
podman build --platform linux/arm64 -f infra/docker/agents-core/workflow/Dockerfile -t test-workflow ./agents-core
podman run --rm -p 8080:8080 test-workflow
```

### Testing on Intel/AMD Macs
For Intel Macs, build with platform emulation:
```bash
podman build --platform linux/arm64 -f infra/docker/agents-core/workflow/Dockerfile -t test-workflow ./agents-core
# Note: May be slower due to emulation
```

## Container Engine: Podman vs Docker

The scripts automatically detect and use Podman if available, falling back to Docker.

**Podman Benefits:**
- No daemon required
- Better security (rootless by default)
- Compatible with Docker commands
- Built-in support for multi-arch builds

**Note on macOS:**
- Podman build output may be silent (normal behavior)
- Check exit codes to verify success
- Images are still built and pushed correctly

## Script Reference

### deploy-infra.sh
**Purpose:** Deploy base infrastructure (ECR, IAM, S3, Secrets)

**Usage:**
```bash
./deploy-infra.sh <environment> [aws-region] [aws-profile]
```

**Parameters:**
- `environment`: Deployment environment (dev, staging, prod)
- `aws-region`: (Optional) AWS region (default: ap-southeast-2)
- `aws-profile`: (Optional) AWS CLI profile

**Example:**
```bash
./deploy-infra.sh dev
./deploy-infra.sh prod ap-southeast-2 production
```

### build-and-push.sh
**Purpose:** Build and push Docker images to ECR

**Usage:**
```bash
./build-and-push.sh <environment> [agent-type] [aws-region] [aws-profile]
```

**Parameters:**
- `environment`: Deployment environment
- `agent-type`: (Optional) 'workflow', 'ai-assistant', or omit for both
- `aws-region`: (Optional) AWS region (default: ap-southeast-2)
- `aws-profile`: (Optional) AWS CLI profile

**Required Environment Variables:**
- `APP_VERSION_WORKFLOW`: Version for workflow agent (if building workflow)
- `APP_VERSION_AI_ASSISTANT`: Version for AI assistant (if building ai-assistant)

**Example:**
```bash
export APP_VERSION_WORKFLOW="1.0.0"
./build-and-push.sh dev workflow

export APP_VERSION_AI_ASSISTANT="1.0.0"
./build-and-push.sh dev ai-assistant
```

### deploy-agentcore.sh
**Purpose:** Deploy/update AgentCore runtime with Docker images

**Usage:**
```bash
./deploy-agentcore.sh <environment> [agent-type] [aws-region] [aws-profile]
```

**Parameters:**
- `environment`: Deployment environment
- `agent-type`: (Optional) 'workflow', 'ai-assistant', or omit for both
- `aws-region`: (Optional) AWS region (default: ap-southeast-2)
- `aws-profile`: (Optional) AWS CLI profile

**Required Environment Variables:**
- `APP_VERSION_WORKFLOW`: Version for workflow agent (if deploying workflow)
- `APP_VERSION_AI_ASSISTANT`: Version for AI assistant (if deploying ai-assistant)

**Example:**
```bash
export APP_VERSION_WORKFLOW="1.0.0"
./deploy-agentcore.sh dev workflow
```

## Troubleshooting

### Issue: "No space left on device" during build
**Solution:** Wrong build context. Use `agents-core/` not project root:
```bash
# ✓ Correct
podman build -f infra/docker/agents-core/workflow/Dockerfile -t workflow ./agents-core

# ✗ Wrong
podman build -f infra/docker/agents-core/workflow/Dockerfile -t workflow .
```

### Issue: "Architecture incompatible" during deployment
**Solution:** Ensure ARM64 platform:
```bash
podman build --platform linux/arm64 ...
```

### Issue: Podman build appears silent on macOS
**Behavior:** Normal - Podman on macOS doesn't stream build output
**Verification:** Check exit code and ECR for pushed image
```bash
./build-and-push.sh dev workflow
echo $?  # Should be 0 for success
```

### Issue: "Image does not exist in ECR"
**Solution:** Build and push before deploying:
```bash
# 1. Build first
export APP_VERSION_WORKFLOW="1.0.0"
./build-and-push.sh dev workflow

# 2. Then deploy
./deploy-agentcore.sh dev workflow
```

### Issue: CDK deployment fails with "No stacks match"
**Solution:** Ensure at least one image URI is provided via environment variable
```bash
# Set version before deploying
export APP_VERSION_WORKFLOW="1.0.0"
./deploy-agentcore.sh dev workflow
```

## Monitoring & Testing

### View Runtime Status
```bash
aws bedrock-agentcore list-runtimes --region ap-southeast-2
```

### Check Runtime Details
```bash
aws bedrock-agentcore get-runtime \
  --runtime-id bidopsai_workflow_agent_dev-XXXXX \
  --region ap-southeast-2
```

### View CloudWatch Logs
Navigate to:
```
https://console.aws.amazon.com/cloudwatch/home?region=ap-southeast-2#logsV2:log-groups
```
Look for log group: `/aws/bedrock-agentcore/runtimes`

### Test Runtime
See `agents-core/scripts/deploy/test_runtime.sh` for testing deployed runtimes.

## CI/CD Integration

For automated deployments, set environment variables in your CI/CD pipeline:

```yaml
# Example GitHub Actions
env:
  APP_VERSION_WORKFLOW: ${{ github.ref_name }}
  APP_VERSION_AI_ASSISTANT: ${{ github.ref_name }}
  AWS_REGION: ap-southeast-2

steps:
  - name: Deploy Infrastructure
    run: ./infra/cdk/scripts/deploy-infra.sh ${{ env.ENVIRONMENT }}
  
  - name: Build and Push
    run: ./infra/cdk/scripts/build-and-push.sh ${{ env.ENVIRONMENT }}
  
  - name: Deploy AgentCore
    run: ./infra/cdk/scripts/deploy-agentcore.sh ${{ env.ENVIRONMENT }}
```

## Best Practices

1. **Versioning:** Always use semantic versioning (MAJOR.MINOR.PATCH)
2. **Testing:** Test builds locally before pushing to ECR
3. **Incremental Updates:** Deploy one agent at a time for safer rollouts
4. **Monitoring:** Check CloudWatch logs after deployment
5. **Rollback:** Keep previous versions in ECR for quick rollback
6. **Security:** Never commit AWS credentials or `.env` files

## Security Notes

- All containers run as non-root user (`bedrock_agentcore`)
- IAM roles follow principle of least privilege
- Secrets stored in AWS Secrets Manager
- ECR repositories have lifecycle policies for image cleanup
- Container images are scanned for vulnerabilities

## Support

For issues or questions:
1. Check CloudWatch logs for runtime errors
2. Verify ECR images exist and are ARM64
3. Review IAM role permissions
4. Check AWS service quotas for AgentCore

## Resources

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/agentcore/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Podman Documentation](https://docs.podman.io/)
- [UV Package Manager](https://github.com/astral-sh/uv)