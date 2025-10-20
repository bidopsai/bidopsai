# Technical Research: Docker Buildx and AWS ECR for Strands Agents

**Feature**: `003-specify-scripts-bash`  
**Date**: 2025-10-16  
**Status**: Complete

## Overview

Research findings for building ARM64 Docker images using Docker Buildx and pushing to AWS Elastic Container Registry (ECR) for Strands AI agent deployments to AWS Bedrock AgentCore.

## Docker Buildx Multi-Platform Builds

### What is Docker Buildx?

Docker Buildx is a CLI plugin that extends the `docker build` command with BuildKit capabilities, enabling multi-platform image builds. Required for ARM64 builds on x86_64 development machines.

### Key Capabilities

- **Multi-platform support**: Build for `linux/arm64`, `linux/amd64`, etc.
- **Builder instances**: Isolated build environments with custom configurations
- **BuildKit backend**: Enhanced build performance with caching and parallelism
- **Cross-compilation**: QEMU emulation for non-native architectures

### Buildx Setup Commands

```bash
docker buildx create --name arm64-builder --use --bootstrap
docker buildx inspect --bootstrap
docker buildx ls
```

### ARM64 Build Command

```bash
docker buildx build \
  --platform linux/arm64 \
  --tag <image-name>:<tag> \
  --load \
  .
```

**Flags**:
- `--platform linux/arm64`: Target ARM64 architecture
- `--load`: Load built image into local Docker daemon (required for single-platform builds)
- `--push`: Push directly to registry (alternative to `--load`)

### Buildx Detection

```bash
if docker buildx version &>/dev/null; then
  echo "Buildx available"
else
  echo "Buildx not found - install Docker Desktop or docker-buildx-plugin"
fi
```

### Builder Instance Management

```bash
docker buildx create --name mybuilder --driver docker-container --use
```

**Key learnings**:
- Default builder may not support ARM64
- Creating dedicated builder ensures consistent ARM64 builds
- Builder state persists across sessions
- `--bootstrap` pre-initializes builder to avoid first-build delays

## AWS ECR (Elastic Container Registry)

### ECR Repository Structure

Format: `<account-id>.dkr.ecr.<region>.amazonaws.com/<repository-name>:<tag>`

Example: `123456789012.dkr.ecr.us-east-1.amazonaws.com/strands-agents:latest`

### ECR Authentication

```bash
aws ecr get-login-password --region <region> | \
  docker login --username AWS --password-stdin \
  <account-id>.dkr.ecr.<region>.amazonaws.com
```

**Key learnings**:
- Login tokens expire after 12 hours
- Must authenticate before each push session
- Requires AWS credentials with `ecr:GetAuthorizationToken` permission

### ECR Repository Creation

```bash
aws ecr create-repository \
  --repository-name <name> \
  --image-scanning-configuration scanOnPush=true \
  --region <region>
```

**Output** (JSON):
```json
{
  "repository": {
    "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/strands-agents",
    "repositoryUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/strands-agents"
  }
}
```

### Check Repository Existence

```bash
aws ecr describe-repositories \
  --repository-names <name> \
  --region <region> 2>/dev/null || echo "Repository not found"
```

### ECR Image Push

```bash
docker tag <local-image>:<tag> <ecr-uri>:<tag>
docker push <ecr-uri>:<tag>
```

### ECR Image Verification

```bash
aws ecr describe-images \
  --repository-name <name> \
  --image-ids imageTag=<tag> \
  --region <region> \
  --output json
```

**Output fields**:
- `imageDigest`: SHA256 digest (immutable identifier)
- `imageSizeInBytes`: Image size
- `imagePushedAt`: Timestamp
- `imageTags`: List of tags for this digest

### ECR List All Tags

```bash
aws ecr describe-images \
  --repository-name <name> \
  --region <region> \
  --query 'sort_by(imageDetails, &imagePushedAt)[*].[imageTags[0], imagePushedAt, imageSizeInBytes]' \
  --output table
```

## AWS Credential Chain

### Credential Resolution Order

1. Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
2. Shared credentials file: `~/.aws/credentials` (profile from `AWS_PROFILE`)
3. IAM role attached to EC2/ECS instance
4. AWS SSO credentials

### Credential Validation

```bash
aws sts get-caller-identity
```

**Output**:
```json
{
  "UserId": "AIDAI...",
  "Account": "123456789012",
  "Arn": "arn:aws:iam::123456789012:user/developer"
}
```

**Key learnings**:
- Use `get-caller-identity` to validate credentials before starting build
- Extract account ID from output for ECR URI construction
- Non-zero exit code indicates invalid/expired credentials

## Error Handling Patterns

### Docker Buildx Errors

```bash
if ! docker buildx version &>/dev/null; then
  echo "ERROR: Docker Buildx not found. Install Docker Desktop or run:"
  echo "  docker buildx create --use"
  exit 1
fi
```

### AWS CLI Errors

```bash
if ! aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$REGION" &>/dev/null; then
  echo "Creating ECR repository: $REPO_NAME"
  aws ecr create-repository --repository-name "$REPO_NAME" --region "$REGION"
fi
```

### Docker Build Errors

```bash
if ! docker buildx build --platform linux/arm64 --tag "$IMAGE_NAME" --load .; then
  echo "ERROR: Docker build failed. Check Dockerfile and build context."
  exit 2
fi
```

## Strands Agent Dockerfile Requirements

### Minimal Dockerfile Structure

```dockerfile
FROM python:3.11-slim-arm64

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key requirements**:
- Base image must support ARM64 (use `-arm64` or multi-arch images)
- Strands agents use FastAPI/uvicorn for HTTP interface
- Port 8000 default (customizable via environment variables)
- No special Bedrock AgentCore requirements beyond ARM64 architecture

### Multi-Stage Builds (Optimization)

```dockerfile
FROM python:3.11-slim-arm64 AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim-arm64
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Performance Considerations

### Build Caching

- Buildx uses BuildKit cache by default
- Cache layers across builds for faster rebuilds
- Cache stored in builder instance (not local Docker daemon)

### Push Performance

- ECR supports parallel layer uploads
- Typical 500MB image pushes in 1-2 minutes on good network
- Use `--quiet` flag to reduce output noise in CI/CD

### Image Size Optimization

- Use slim base images (`python:3.11-slim` vs `python:3.11`)
- Multi-stage builds reduce final image size by 50-70%
- ECR 10GB image limit rarely hit for Python applications

## Bash Scripting Best Practices

### Exit Codes

```bash
set -euo pipefail
```

- `-e`: Exit on command failure
- `-u`: Exit on undefined variable
- `-o pipefail`: Exit on pipe failures

### Parameter Parsing

```bash
REPO_NAME="${1:?Usage: $0 <repo-name> [tag] [region]}"
TAG="${2:-latest}"
REGION="${3:-${AWS_REGION:-us-east-1}}"
```

### Output Formatting

```bash
echo "[INFO] Building Docker image for ARM64..."
echo "[ERROR] Build failed" >&2
echo "[SUCCESS] Image pushed to ECR: $ECR_URI"
```

### jq for JSON Parsing

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

IMAGE_DIGEST=$(aws ecr describe-images \
  --repository-name "$REPO_NAME" \
  --image-ids imageTag="$TAG" \
  --query 'imageDetails[0].imageDigest' \
  --output text)
```

## Security Considerations

### Credential Handling

- **NEVER** store AWS credentials in scripts
- **NEVER** log AWS credentials in output
- Use IAM roles in CI/CD pipelines (GitHub Actions OIDC, ECS task roles)
- Validate credentials exist before starting long operations

### ECR Repository Permissions

Required IAM permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:CreateRepository",
        "ecr:DescribeRepositories",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:DescribeImages"
      ],
      "Resource": "*"
    }
  ]
}
```

### Image Scanning

```bash
aws ecr put-image-scanning-configuration \
  --repository-name "$REPO_NAME" \
  --image-scanning-configuration scanOnPush=true \
  --region "$REGION"
```

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Build and push to ECR
  env:
    AWS_REGION: us-east-1
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  run: |
    ./scripts/build-and-push.sh strands-agents ${{ github.sha }}
```

### Docker-in-Docker Requirements

- CI runners need Docker socket access or DinD
- Buildx may require `--driver docker-container` in CI
- Pre-warm builder in CI setup step

## References

- [Docker Buildx Documentation](https://docs.docker.com/build/buildx/)
- [AWS ECR User Guide](https://docs.aws.amazon.com/AmazonECR/latest/userguide/)
- [Docker Multi-Platform Builds](https://docs.docker.com/build/building/multi-platform/)
- [AWS CLI ECR Commands](https://docs.aws.amazon.com/cli/latest/reference/ecr/)
- [Bash Best Practices](https://www.gnu.org/software/bash/manual/bash.html)

## Next Steps

1. Define script interfaces in `data-model.md`
2. Create usage examples in `quickstart.md`
3. Implement `build-agent.sh` with buildx auto-configuration
4. Implement `push-to-ecr.sh` with repository auto-creation
