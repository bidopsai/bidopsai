# Quick Start: Deploy Workflow Agent to Dev

## Prerequisites

1. **Setup Environment Variables**

Create a `.env` file in the project root:

```bash
cd /Users/cbandara/Projects/MyProjects/bidopsai

cat > .env << 'EOF'
# AWS Configuration
AWS_ACCOUNT_ID=YOUR_AWS_ACCOUNT_ID
AWS_REGION=us-east-1

# Application Versions
APP_VERSION_WORKFLOW=1.0.0
APP_VERSION_AI_ASSISTANT=1.0.0
EOF
```

> **Important**: Replace `YOUR_AWS_ACCOUNT_ID` with your actual AWS account ID.

2. **Ensure Podman is installed**

```bash
podman --version
```

## Deployment Commands

Run these commands from the `infra/cdk/scripts` directory:

```bash
cd /Users/cbandara/Projects/MyProjects/bidopsai/infra/cdk/scripts
```

### Step 1: Deploy Infrastructure (ECR + IAM)

```bash
./deploy-infra.sh dev
```

This creates:
- ECR repository: `bidopsai-workflow-agent-dev`
- IAM roles for AgentCore runtime

### Step 2: Build and Push Container Image

```bash
./build-and-push.sh dev workflow
```

This:
- Builds the workflow agent container with Podman
- Tags with `v1.0.0`, `latest`, and `dev`
- Pushes to ECR

### Step 3: Deploy AgentCore Runtime

```bash
./deploy-agentcore.sh dev workflow
```

This:
- Deploys the AgentCore runtime stack
- Creates the runtime with the image from ECR
- **Outputs the Runtime ARN** (look for "Runtime ARN:" in the output)

## Expected Output

After running `./deploy-agentcore.sh dev workflow`, you'll see:

```
========================================
Runtime Information
========================================

Workflow Agent Runtime:
  Runtime ID: runtime-abc123
  Runtime ARN: arn:aws:bedrock:us-east-1:123456789012:agent-runtime/bidopsai_workflow_agent_dev
  Runtime Name: bidopsai-workflow-agent-dev
  Image Version: 1.0.0

Endpoint: DEFAULT

========================================
Deployment Complete
========================================
Environment: dev
Region: us-east-1

✓ AgentCore runtimes deployed successfully!
```

The **Runtime ARN** is displayed in the output!

## Update Workflow Agent (After Code Changes)

```bash
# 1. Update version in .env
nano /Users/cbandara/Projects/MyProjects/bidopsai/.env
# Change: APP_VERSION_WORKFLOW=1.0.0 → APP_VERSION_WORKFLOW=1.0.1

# 2. Build and deploy in one command
cd /Users/cbandara/Projects/MyProjects/bidopsai/infra/cdk/scripts
./build-and-push.sh dev workflow && ./deploy-agentcore.sh dev workflow
```

## Troubleshooting

### If ECR login fails:
```bash
aws ecr get-login-password --region us-east-1 | \
    podman login --username AWS --password-stdin \
    ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com
```

### If build fails:
```bash
# Verify Podman is working
podman info

# Check Dockerfile exists
ls -la /Users/cbandara/Projects/MyProjects/bidopsai/infra/docker/agents-core/workflow/Dockerfile
```

### View logs after deployment:
```bash
aws logs tail /aws/bedrock-agentcore/runtimes/bidopsai-workflow-agent-dev --follow --region us-east-1
```

## Getting the Runtime ARN Later

If you need to retrieve the Runtime ARN after deployment:

```bash
aws cloudformation describe-stacks \
    --stack-name BidOpsAI-AgentCore-dev \
    --region us-east-1 \
    --query "Stacks[0].Outputs[?OutputKey=='WorkflowAgentRuntimeArn'].OutputValue" \
    --output text
```

Or check in AWS Console:
https://console.aws.amazon.com/bedrock/home?region=us-east-1#/agentcore/runtimes