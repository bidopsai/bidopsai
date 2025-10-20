# CI/CD Pipeline Documentation

## Overview

This pipeline builds and pushes Docker images for all BidOps.AI services to Amazon ECR.

**Services:**
- **Frontend (web)**: Next.js application → `bidopsai-web`
- **Backend API (core-api)**: GraphQL API → `bidopsai-core-api`
- **AgentCore (agent)**: Python AI agents → `bidopsai-agentcore`

## Pipeline Overview

This workflow provides a comprehensive CI/CD pipeline for the BidOps.AI project, including:

- **Multi-service Docker builds** for frontend, core-api, and agentcore
- **Smart change detection** to only build what's changed
- **Testing and linting** before builds
- **Multi-architecture builds** (AMD64 and ARM64)
- **ECR integration** with automatic login and push
- **Security scanning** with Trivy
- **Staging and production deployments**
- **Automatic cleanup** of old ECR images

## Required GitHub Secrets

You need to set up the following secrets in your GitHub repository:

### AWS Credentials
- `AWS_ACCESS_KEY_ID` - AWS access key with ECR permissions
- `AWS_SECRET_ACCESS_KEY` - AWS secret access key

### Required AWS Permissions

Your AWS user/role needs the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:BatchDeleteImage",
                "ecr:PutImage",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
                "ecr:DescribeRepositories",
                "ecr:CreateRepository",
                "ecr:ListImages",
                "ecr:DescribeImages"
            ],
            "Resource": "*"
        }
    ]
}
```

## ECR Repository Setup

Before running the workflow, ensure your ECR repositories exist:

```bash
# Create repositories for each service
aws ecr create-repository --repository-name bidopsai-web --region us-east-1
aws ecr create-repository --repository-name bidopsai-core-api --region us-east-1
aws ecr create-repository --repository-name bidopsai-agentcore --region us-east-1
```

## Workflow Triggers

The workflow runs on:

1. **Push to main/develop branches** - Full pipeline with potential deployment
2. **Pull requests to main/develop** - Build and test only
3. **Manual trigger** - Via GitHub UI with optional force rebuild

## Workflow Jobs

### 1. Changes Detection
- Uses `dorny/paths-filter` to detect which services have changes
- Only builds services that have been modified
- Can be overridden with manual `force_rebuild` option

### 2. Testing Jobs
- **test-web**: Lints, type-checks, and builds the Next.js frontend
- **test-core-api**: Lints, tests, and builds the Node.js API

### 3. Build and Push
- **Matrix strategy** builds all three services in parallel
- **Multi-architecture builds** for AMD64 and ARM64
- **Smart caching** using GitHub Actions cache
- **ECR push** with multiple tags (branch, SHA, latest)

### 4. Security Scanning
- **Trivy vulnerability scanning** on all built images
- **SARIF upload** to GitHub Security tab

### 5. Deployment
- **Staging deployment** on develop branch pushes
- **Production deployment** on main branch pushes
- Uses GitHub environments for approval workflows

### 6. Cleanup
- **Automatic cleanup** of old ECR images
- Keeps latest 10 images per repository

## Docker Image Tags

Images are tagged with:
- `latest` (for main branch)
- `develop` (for develop branch)
- `pr-123` (for pull requests)
- `main-abc1234` (branch + short SHA)

## Configuration

### Environment Variables
- `AWS_REGION`: Set to `us-east-1` (modify in workflow if needed)
- `ECR_REGISTRY_ALIAS`: Set to `bidopsai` (modify if your ECR repos have different naming)

### Customization Points

1. **AWS Region**: Change `AWS_REGION` environment variable
2. **ECR Repository Names**: Modify `ECR_REGISTRY_ALIAS` or the repository naming pattern
3. **Build Platforms**: Modify `platforms` in docker/build-push-action
4. **Retention Policy**: Change image cleanup logic in the cleanup job
5. **Deployment Commands**: Add actual deployment scripts in deploy jobs

## Usage Examples

### Manual Deployment
```bash
# Trigger workflow manually with force rebuild
gh workflow run ci.yaml -f force_rebuild=true
```

### Check Workflow Status
```bash
# List recent workflow runs
gh run list

# View specific run
gh run view <run-id>
```

### ECR Image Management
```bash
# List images in repository
aws ecr list-images --repository-name bidopsai-web

# Pull specific image
docker pull <account-id>.dkr.ecr.us-east-1.amazonaws.com/bidopsai-web:latest
```

## Troubleshooting

### Common Issues

1. **ECR Repository Not Found**
   - Ensure repositories are created before first run
   - Check repository names match the workflow configuration

2. **Permission Denied**
   - Verify AWS credentials have required ECR permissions
   - Check if IAM user/role has proper policies attached

3. **Build Failures**
   - Check if Dockerfiles exist at expected paths
   - Verify context paths in the workflow matrix

4. **Large Images**
   - Consider multi-stage builds to reduce image size
   - Use `.dockerignore` files to exclude unnecessary files

### Debugging Tips

1. **Enable verbose logging**: Add `ACTIONS_STEP_DEBUG: true` to workflow environment
2. **Check build logs**: Review the "Build and push Docker image" step output
3. **Verify ECR login**: Ensure the ECR login step completes successfully
4. **Test locally**: Use the same Docker commands locally to debug build issues

## Security Best Practices

1. **Least privilege**: IAM user only has required ECR permissions
2. **Secrets management**: AWS credentials stored as GitHub secrets
3. **Image scanning**: Trivy scans all images for vulnerabilities
4. **Multi-architecture**: Builds for both AMD64 and ARM64
5. **Environment protection**: Production deployments require approval