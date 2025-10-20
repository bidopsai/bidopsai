# Quickstart Guide: AWS Strands Agent Build and Push to ECR

**Feature**: `003-specify-scripts-bash`  
**Date**: 2025-10-16  
**Status**: Complete

## Prerequisites

### Required Tools

```bash
docker --version
aws --version
jq --version
```

**Minimum versions**:
- Docker 20.10+ with Buildx plugin
- AWS CLI 2.0+
- jq 1.6+

### AWS Configuration

```bash
aws configure
```

**Required IAM permissions**:
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

### Verify Setup

```bash
aws sts get-caller-identity
docker buildx version
```

## Quick Start (5 Minutes)

### 1. One-Command Build and Push

```bash
cd /path/to/bidopsai

./scripts/build-and-push.sh ./agentcore strands-agents latest us-east-1
```

**Expected output**:
```
[INFO] === STAGE 1: BUILD ===
[INFO] Checking Docker Buildx availability...
[INFO] Creating buildx builder: arm64-builder
[INFO] Building Docker image for ARM64...
[SUCCESS] Image built: strands-agents:latest (linux/arm64)

[INFO] === STAGE 2: PUSH ===
[INFO] Validating AWS credentials...
[INFO] Account ID: 123456789012
[INFO] Creating ECR repository: strands-agents
[INFO] Authenticating with ECR...
[INFO] Pushing image to ECR...
[SUCCESS] Image pushed to ECR

[SUCCESS] Complete workflow finished
[INFO] ECR URI: 123456789012.dkr.ecr.us-east-1.amazonaws.com/strands-agents:latest
```

### 2. Verify Image in ECR

```bash
./scripts/verify-ecr-image.sh strands-agents latest us-east-1
```

**Expected output**:
```
Repository: strands-agents
Region: us-east-1
Tag: latest
Digest: sha256:def456789...
Size: 487 MB
Platform: linux/arm64
Pushed: 2025-10-16T14:32:15Z
URI: 123456789012.dkr.ecr.us-east-1.amazonaws.com/strands-agents:latest
```

## Usage Examples

### Example 1: Build Only (No Push)

**Use case**: Test local build before pushing to ECR

```bash
./scripts/build-agent.sh ./agentcore strands-agents latest
```

**Verify local image**:
```bash
docker images | grep strands-agents
docker inspect strands-agents:latest | jq '.[0].Architecture'
```

**Expected**: `"arm64"`

---

### Example 2: Push Pre-Built Image

**Use case**: Push an image you built earlier

```bash
./scripts/push-to-ecr.sh strands-agents:latest strands-agents us-east-1
```

**With force overwrite**:
```bash
./scripts/push-to-ecr.sh strands-agents:latest strands-agents us-east-1 --force
```

---

### Example 3: Build with Custom Tag

**Use case**: Version your agent deployments

```bash
./scripts/build-and-push.sh ./agentcore strands-agents v1.2.3 us-east-1
```

**Verify multiple tags**:
```bash
./scripts/verify-ecr-image.sh strands-agents --list-all
```

**Expected output**:
```
TAG             PUSHED               SIZE      DIGEST
v1.2.3          2025-10-16 15:00:00  487 MB    sha256:abc123...
v1.2.2          2025-10-15 10:30:00  485 MB    sha256:def456...
latest          2025-10-16 14:32:15  487 MB    sha256:abc123...
```

---

### Example 4: Multi-Region Deployment

**Use case**: Deploy agent to multiple AWS regions

```bash
./scripts/build-agent.sh ./agentcore strands-agents v1.0.0

./scripts/push-to-ecr.sh strands-agents:v1.0.0 strands-agents us-east-1
./scripts/push-to-ecr.sh strands-agents:v1.0.0 strands-agents us-west-2
./scripts/push-to-ecr.sh strands-agents:v1.0.0 strands-agents eu-west-1
```

**Verify all regions**:
```bash
for region in us-east-1 us-west-2 eu-west-1; do
  echo "=== $region ==="
  ./scripts/verify-ecr-image.sh strands-agents v1.0.0 $region
done
```

---

### Example 5: CI/CD Integration (GitHub Actions)

**Use case**: Automate builds on git push

**.github/workflows/build-agent.yml**:
```yaml
name: Build and Push Strands Agent

on:
  push:
    branches: [main]
    paths:
      - 'agentcore/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Build and push to ECR
        run: |
          ./scripts/build-and-push.sh \
            ./agentcore \
            strands-agents \
            ${{ github.sha }} \
            us-east-1
      
      - name: Verify push
        run: |
          ./scripts/verify-ecr-image.sh \
            strands-agents \
            ${{ github.sha }} \
            us-east-1 \
            --json
```

---

### Example 6: Development Workflow

**Use case**: Rapid iteration during agent development

```bash
cd agentcore

vim agent.py

cd ..

./scripts/build-and-push.sh ./agentcore strands-agents dev us-east-1 --no-cache

./scripts/verify-ecr-image.sh strands-agents dev --json | jq '.imageDigest'
```

**Deploy to Bedrock AgentCore** (example):
```bash
DIGEST=$(./scripts/verify-ecr-image.sh strands-agents dev us-east-1 --json | jq -r '.imageDigest')

aws bedrock-agent update-agent \
  --agent-id agent-123 \
  --agent-resource-role-arn arn:aws:iam::123456789012:role/AgentRole \
  --foundation-model anthropic.claude-v2 \
  --agent-runtime-config "containerImageDigest=$DIGEST"
```

---

## Common Workflows

### New Agent Development

```bash
mkdir -p my-new-agent
cd my-new-agent

cat > Dockerfile <<EOF
FROM python:3.11-slim-arm64
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

cat > requirements.txt <<EOF
fastapi==0.104.1
uvicorn[standard]==0.24.0
EOF

cat > agent.py <<EOF
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/invoke")
def invoke(payload: dict):
    return {"result": "Agent processing complete"}
EOF

cd ..

./scripts/build-and-push.sh ./my-new-agent my-agent latest us-east-1
```

### Update Existing Agent

```bash
cd agentcore

vim agent.py

cd ..

./scripts/build-and-push.sh ./agentcore strands-agents latest us-east-1 --force

./scripts/verify-ecr-image.sh strands-agents latest
```

### Rollback to Previous Version

```bash
./scripts/verify-ecr-image.sh strands-agents --list-all

aws ecr batch-get-image \
  --repository-name strands-agents \
  --image-ids imageTag=v1.2.2 \
  --query 'images[0].imageManifest' \
  --output text | \
  aws ecr put-image \
    --repository-name strands-agents \
    --image-tag latest \
    --image-manifest file:///dev/stdin
```

### Clean Up Old Images

```bash
./scripts/verify-ecr-image.sh strands-agents --list-all

aws ecr batch-delete-image \
  --repository-name strands-agents \
  --image-ids imageTag=v0.9.0 imageTag=v0.8.0
```

## Troubleshooting

### Error: Docker Buildx not available

**Symptom**:
```
[ERROR] Docker Buildx not available
[ERROR] Suggestion: Install with 'docker buildx create --use'
```

**Solution**:
```bash
docker buildx create --name arm64-builder --use
docker buildx inspect --bootstrap
```

**Verify**:
```bash
docker buildx ls
```

---

### Error: AWS credentials not configured

**Symptom**:
```
[ERROR] AWS credentials not configured. Run: aws configure
```

**Solution**:
```bash
aws configure
```

Or use environment variables:
```bash
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
```

**Verify**:
```bash
aws sts get-caller-identity
```

---

### Error: Dockerfile not found

**Symptom**:
```
[ERROR] Dockerfile not found in /path/to/agent
```

**Solution**:
```bash
ls -la /path/to/agent/Dockerfile

cat > /path/to/agent/Dockerfile <<EOF
FROM python:3.11-slim-arm64
WORKDIR /app
COPY . .
CMD ["python", "agent.py"]
EOF
```

---

### Error: ECR authentication failed

**Symptom**:
```
[ERROR] ECR authentication failed. Check IAM permissions.
```

**Solution**:
Verify IAM user/role has `ecr:GetAuthorizationToken` permission:

```bash
aws ecr get-login-password --region us-east-1
```

If this fails, attach the ECR policy:
```bash
aws iam attach-user-policy \
  --user-name your-user \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser
```

---

### Error: Image push failed

**Symptom**:
```
[ERROR] Push failed. Check network connectivity.
denied: Your authorization token has expired. Reauthenticate and retry.
```

**Solution**:
Re-run the push script (it will re-authenticate):
```bash
./scripts/push-to-ecr.sh strands-agents:latest strands-agents us-east-1
```

Or manually re-authenticate:
```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com
```

---

### Error: Image size exceeds limit

**Symptom**:
```
[ERROR] Image size (12 GB) exceeds ECR limit (10 GB)
```

**Solution**:
Optimize Dockerfile with multi-stage builds:

```dockerfile
FROM python:3.11-slim-arm64 AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

FROM python:3.11-slim-arm64
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
CMD ["uvicorn", "agent:app", "--host", "0.0.0.0"]
```

**Verify size**:
```bash
docker images strands-agents:latest --format "{{.Size}}"
```

---

### Warning: Builder not supporting ARM64

**Symptom**:
```
[WARN] Current builder does not support linux/arm64. Creating new builder...
```

**Solution**:
This is automatically handled by the script. Verify builder:
```bash
docker buildx inspect arm64-builder
```

**Expected output**:
```
Platforms: linux/amd64, linux/arm64, linux/arm/v7, ...
```

---

## Performance Tips

### 1. Use Build Cache

**First build** (slow):
```bash
./scripts/build-agent.sh ./agentcore strands-agents v1.0.0
```

**Incremental builds** (fast):
```bash
./scripts/build-agent.sh ./agentcore strands-agents v1.0.1
```

Cache persists in buildx builder.

### 2. Optimize Dockerfile Layer Order

```dockerfile
FROM python:3.11-slim-arm64

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0"]
```

**Why**: Dependencies change less frequently than code, so caching works better.

### 3. Use `.dockerignore`

```bash
cat > ./agentcore/.dockerignore <<EOF
__pycache__
*.pyc
.git
.venv
node_modules
.env
.DS_Store
EOF
```

**Why**: Reduces build context size, faster uploads to Docker daemon.

### 4. Pre-warm Builder

```bash
docker buildx create --name arm64-builder --use --bootstrap
docker buildx inspect --bootstrap
```

**Why**: Avoids builder initialization delay on first build.

## Advanced Usage

### Custom Builder Configuration

```bash
docker buildx create \
  --name custom-builder \
  --driver docker-container \
  --driver-opt network=host \
  --buildkitd-flags '--allow-insecure-entitlement network.host' \
  --use

./scripts/build-agent.sh ./agentcore strands-agents latest --builder custom-builder
```

### Build with Secrets

```dockerfile
RUN --mount=type=secret,id=pypi_token \
    pip install --extra-index-url https://$(cat /run/secrets/pypi_token)@pypi.org/simple mypackage
```

```bash
docker buildx build \
  --platform linux/arm64 \
  --secret id=pypi_token,src=$HOME/.pypi/token \
  --tag strands-agents:latest \
  --load \
  .
```

### Export Image Digest

```bash
DIGEST=$(./scripts/verify-ecr-image.sh strands-agents latest us-east-1 --json | jq -r '.imageDigest')

echo "export STRANDS_AGENT_DIGEST=$DIGEST" >> .env
```

Use in infrastructure-as-code:
```python
agent_image = f"{ecr_repository.repository_url}@{os.getenv('STRANDS_AGENT_DIGEST')}"
```

## Next Steps

1. Implement `build-agent.sh` script
2. Implement `push-to-ecr.sh` script
3. Implement `build-and-push.sh` script
4. Implement `verify-ecr-image.sh` script
5. Test all scripts with sample agent
6. Update `/scripts/README.md`

## References

- [Data Model](./data-model.md) - Script interfaces and exit codes
- [Research](./research.md) - Docker Buildx and ECR technical details
- [Spec](./spec.md) - Feature requirements and user stories
- [Plan](./plan.md) - Implementation phases
