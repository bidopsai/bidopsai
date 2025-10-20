# Data Model: Script Interfaces and Configuration

**Feature**: `003-specify-scripts-bash`  
**Date**: 2025-10-16  
**Status**: Complete

## Overview

Defines input/output interfaces, configuration parameters, exit codes, and data contracts for all four bash scripts.

## Script Interfaces

### 1. `build-agent.sh` - Build ARM64 Docker Image

**Purpose**: Build ARM64-compatible Docker image for Strands agent using Docker Buildx.

#### Input Parameters

```bash
./build-agent.sh <agent-directory> <repository-name> [tag] [options]
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `agent-directory` | string (path) | Yes | - | Path to Strands agent project containing Dockerfile |
| `repository-name` | string | Yes | - | ECR repository name (without registry URI) |
| `tag` | string | No | `latest` | Docker image tag |
| `--no-cache` | flag | No | false | Disable Docker build cache |
| `--builder` | string | No | `arm64-builder` | Custom buildx builder name |

#### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DOCKER_BUILDKIT` | No | `1` | Enable BuildKit backend |

#### Output

**Success (stdout)**:
```
[INFO] Checking Docker Buildx availability...
[INFO] Creating buildx builder: arm64-builder
[INFO] Building Docker image for ARM64...
[SUCCESS] Image built: strands-agents:latest (linux/arm64)
[INFO] Image ID: sha256:abc123...
[INFO] Image size: 487 MB
```

**Failure (stderr)**:
```
[ERROR] Dockerfile not found in /path/to/agent
[ERROR] Docker Buildx not available. Install with: docker buildx create --use
[ERROR] Build failed. Check Dockerfile syntax and build context.
```

#### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success - image built successfully |
| `1` | Invalid arguments or missing dependencies |
| `2` | Dockerfile not found |
| `3` | Docker build failed |
| `4` | Buildx configuration failed |

#### Output Artifacts

- **Local Docker image**: `<repository-name>:<tag>` with platform `linux/arm64`
- **Build cache**: Stored in buildx builder instance

---

### 2. `push-to-ecr.sh` - Authenticate and Push to ECR

**Purpose**: Authenticate with AWS ECR and push Docker image to ECR repository.

#### Input Parameters

```bash
./push-to-ecr.sh <image-name> <repository-name> [region] [options]
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image-name` | string | Yes | - | Local Docker image name (e.g., `strands-agents:latest`) |
| `repository-name` | string | Yes | - | ECR repository name |
| `region` | string | No | `$AWS_REGION` or `us-east-1` | AWS region for ECR |
| `--force` | flag | No | false | Overwrite existing image with same tag |
| `--no-verify` | flag | No | false | Skip post-push verification |

#### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AWS_REGION` | No | `us-east-1` | Default AWS region |
| `AWS_PROFILE` | No | `default` | AWS credentials profile |
| `AWS_ACCESS_KEY_ID` | No* | - | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | No* | - | AWS secret key |

*Required if not using IAM role or credentials file

#### Output

**Success (stdout)**:
```
[INFO] Validating AWS credentials...
[INFO] Account ID: 123456789012
[INFO] Checking ECR repository: strands-agents
[INFO] Creating ECR repository: strands-agents (region: us-east-1)
[INFO] Authenticating with ECR...
[INFO] Tagging image: strands-agents:latest -> 123456789012.dkr.ecr.us-east-1.amazonaws.com/strands-agents:latest
[INFO] Pushing image to ECR...
[SUCCESS] Image pushed to ECR
[INFO] ECR URI: 123456789012.dkr.ecr.us-east-1.amazonaws.com/strands-agents:latest
[INFO] Image digest: sha256:def456...
```

**Failure (stderr)**:
```
[ERROR] AWS credentials not configured. Run: aws configure
[ERROR] Image not found: strands-agents:latest
[ERROR] ECR authentication failed. Check IAM permissions.
[ERROR] Push failed. Check network connectivity.
```

#### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success - image pushed to ECR |
| `1` | Invalid arguments or configuration |
| `2` | AWS credentials invalid or missing |
| `3` | ECR authentication failed |
| `4` | Image not found locally |
| `5` | Push operation failed |
| `6` | Post-push verification failed |

#### Output Artifacts

- **ECR image**: `<account-id>.dkr.ecr.<region>.amazonaws.com/<repository-name>:<tag>`
- **Image digest**: SHA256 hash (immutable identifier)

---

### 3. `build-and-push.sh` - Combined Workflow

**Purpose**: Build ARM64 image and push to ECR in one command.

#### Input Parameters

```bash
./build-and-push.sh <agent-directory> <repository-name> [tag] [region] [options]
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `agent-directory` | string (path) | Yes | - | Path to Strands agent project |
| `repository-name` | string | Yes | - | ECR repository name |
| `tag` | string | No | `latest` | Docker image tag |
| `region` | string | No | `$AWS_REGION` or `us-east-1` | AWS region |
| `--no-cache` | flag | No | false | Disable build cache |
| `--force` | flag | No | false | Overwrite existing ECR image |

#### Environment Variables

Same as `build-agent.sh` + `push-to-ecr.sh`

#### Output

**Success (stdout)**:
```
[INFO] === STAGE 1: BUILD ===
[INFO] Building Docker image for ARM64...
[SUCCESS] Image built: strands-agents:latest

[INFO] === STAGE 2: PUSH ===
[INFO] Pushing image to ECR...
[SUCCESS] Image pushed to ECR

[SUCCESS] Complete workflow finished
[INFO] ECR URI: 123456789012.dkr.ecr.us-east-1.amazonaws.com/strands-agents:latest
```

**Failure (stderr)**:
```
[ERROR] === STAGE 1: BUILD FAILED ===
[ERROR] Build failed. Halting before push.

[ERROR] === STAGE 2: PUSH FAILED ===
[INFO] Local image still available: strands-agents:latest
```

#### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success - build and push completed |
| `1-4` | Build stage failed (see `build-agent.sh` exit codes) |
| `5-6` | Push stage failed (see `push-to-ecr.sh` exit codes) |

#### Output Artifacts

- **Local Docker image**: `<repository-name>:<tag>`
- **ECR image**: `<account-id>.dkr.ecr.<region>.amazonaws.com/<repository-name>:<tag>`

---

### 4. `verify-ecr-image.sh` - Query ECR Image Metadata

**Purpose**: Verify image exists in ECR and display metadata.

#### Input Parameters

```bash
./verify-ecr-image.sh <repository-name> [tag] [region] [options]
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repository-name` | string | Yes | - | ECR repository name |
| `tag` | string | No | `latest` | Image tag to verify |
| `region` | string | No | `$AWS_REGION` or `us-east-1` | AWS region |
| `--list-all` | flag | No | false | List all tags in repository |
| `--json` | flag | No | false | Output raw JSON |

#### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AWS_REGION` | No | `us-east-1` | Default AWS region |

#### Output

**Success (stdout) - Single Tag**:
```
[INFO] Querying ECR for image: strands-agents:latest

Repository: strands-agents
Region: us-east-1
Tag: latest
Digest: sha256:def456789...
Size: 487 MB
Platform: linux/arm64
Pushed: 2025-10-16T14:32:15Z
URI: 123456789012.dkr.ecr.us-east-1.amazonaws.com/strands-agents:latest
```

**Success (stdout) - List All Tags**:
```
[INFO] Listing all tags in repository: strands-agents

TAG             PUSHED               SIZE      DIGEST
latest          2025-10-16 14:32:15  487 MB    sha256:def456...
v1.0.0          2025-10-15 09:15:42  485 MB    sha256:abc123...
v0.9.0          2025-10-14 16:20:11  480 MB    sha256:fed321...
```

**Success (stdout) - JSON Output**:
```json
{
  "repository": "strands-agents",
  "region": "us-east-1",
  "imageTag": "latest",
  "imageDigest": "sha256:def456789...",
  "imageSizeInBytes": 510918656,
  "imagePushedAt": "2025-10-16T14:32:15Z",
  "imageManifestMediaType": "application/vnd.docker.distribution.manifest.v2+json",
  "imageScanStatus": "COMPLETE",
  "architectures": ["arm64"]
}
```

**Failure (stderr)**:
```
[ERROR] Repository not found: strands-agents
[ERROR] Image tag not found: v2.0.0
[ERROR] AWS credentials not configured
```

#### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success - image found and metadata displayed |
| `1` | Invalid arguments |
| `2` | AWS credentials invalid |
| `3` | Repository not found |
| `4` | Image tag not found |

#### Output Artifacts

- **Console output**: Formatted metadata or JSON

---

## Common Data Structures

### AWS Account Information

```json
{
  "accountId": "123456789012",
  "region": "us-east-1",
  "ecrRegistry": "123456789012.dkr.ecr.us-east-1.amazonaws.com"
}
```

### Docker Image Metadata

```json
{
  "imageName": "strands-agents",
  "imageTag": "latest",
  "imageId": "sha256:abc123...",
  "platform": "linux/arm64",
  "sizeBytes": 510918656,
  "created": "2025-10-16T14:30:00Z"
}
```

### ECR Image Details

```json
{
  "repositoryName": "strands-agents",
  "imageDigest": "sha256:def456...",
  "imageTags": ["latest", "v1.0.0"],
  "imageSizeInBytes": 510918656,
  "imagePushedAt": "2025-10-16T14:32:15Z",
  "imageManifestMediaType": "application/vnd.docker.distribution.manifest.v2+json"
}
```

## Error Handling Standards

### Error Message Format

```
[ERROR] <component>: <description>
[ERROR] Suggestion: <actionable next step>
```

**Example**:
```
[ERROR] Docker Buildx not available
[ERROR] Suggestion: Install with 'docker buildx create --use' or upgrade Docker Desktop
```

### Validation Order

1. **Dependency checks**: Docker, AWS CLI, jq, buildx
2. **Argument validation**: Required parameters present
3. **Credential validation**: AWS credentials valid
4. **Resource validation**: Files/directories exist
5. **Operation execution**: Build/push/verify

### Retry Logic

- **Network failures**: No automatic retry (user must re-run)
- **Authentication failures**: No retry (likely credential issue)
- **Build failures**: No retry (requires user intervention)

## Configuration Files

### `.ecr-config.json` (Optional)

Repository-level configuration for default parameters:

```json
{
  "repository": "strands-agents",
  "region": "us-east-1",
  "defaultTag": "latest",
  "scanOnPush": true,
  "imageMutability": "MUTABLE"
}
```

**Location**: Project root or `~/.config/ecr/`

**Usage**: Scripts check for this file and use values as defaults

## Performance Metrics

### Build Performance

- **Typical build time**: 2-4 minutes (500MB image, cached dependencies)
- **First build**: 5-8 minutes (no cache)
- **Incremental rebuild**: 30-60 seconds (code changes only)

### Push Performance

- **Push time**: 1-2 minutes (500MB image, good network)
- **Slow network**: 5-10 minutes
- **Layer deduplication**: Only changed layers pushed

### Total Workflow

- **Build + Push**: 3-6 minutes (typical)
- **Error detection**: <10 seconds (validation phase)

## Security Considerations

### Credential Storage

- **NEVER** store AWS credentials in scripts
- **NEVER** log credentials in output
- Use AWS credential chain (environment variables, profiles, IAM roles)

### Image Scanning

```bash
aws ecr put-image-scanning-configuration \
  --repository-name strands-agents \
  --image-scanning-configuration scanOnPush=true
```

### Repository Policies

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowPushPull",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/CI-Role"
      },
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage"
      ]
    }
  ]
}
```

## Next Steps

1. Create `quickstart.md` with end-to-end usage examples
2. Implement scripts using defined interfaces
3. Test with sample Strands agent
4. Validate exit codes and error messages
