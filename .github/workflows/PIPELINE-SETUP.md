# CI/CD Pipeline Setup Guide

## 🚀 Quick Start

This guide will help you set up the CI/CD pipeline for BidOps.AI from scratch.

## Prerequisites

- AWS Account with ECR access
- GitHub repository with Actions enabled
- AWS CLI installed and configured locally

## Step 1: Create ECR Repositories

Run these commands **once** to create the ECR repositories:

```bash
# Set your AWS region
export AWS_REGION=us-east-1

# Create frontend repository
aws ecr create-repository \
  --repository-name bidopsai-web \
  --region $AWS_REGION \
  --image-scanning-configuration scanOnPush=true

# Create backend API repository
aws ecr create-repository \
  --repository-name bidopsai-core-api \
  --region $AWS_REGION \
  --image-scanning-configuration scanOnPush=true

# Create agentcore repository
aws ecr create-repository \
  --repository-name bidopsai-agentcore \
  --region $AWS_REGION \
  --image-scanning-configuration scanOnPush=true
```

**Verify:**
```bash
aws ecr describe-repositories --region us-east-1 --query 'repositories[*].repositoryName'
```

Expected output:
```json
[
    "bidopsai-web",
    "bidopsai-core-api",
    "bidopsai-agentcore"
]
```

## Step 2: Create IAM User for CI/CD

### Create IAM User

```bash
aws iam create-user --user-name github-actions-bidopsai
```

### Create and Attach Policy

Save this as `ecr-push-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRAuthentication",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECRPushPull",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:GetRepositoryPolicy",
        "ecr:DescribeRepositories",
        "ecr:ListImages",
        "ecr:DescribeImages",
        "ecr:BatchGetImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource": [
        "arn:aws:ecr:us-east-1:*:repository/bidopsai-web",
        "arn:aws:ecr:us-east-1:*:repository/bidopsai-core-api",
        "arn:aws:ecr:us-east-1:*:repository/bidopsai-agentcore"
      ]
    }
  ]
}
```

Apply the policy:

```bash
# Create the policy
aws iam create-policy \
  --policy-name BidOpsAI-ECR-Push \
  --policy-document file://ecr-push-policy.json

# Attach to user (replace ACCOUNT_ID with your AWS account ID)
aws iam attach-user-policy \
  --user-name github-actions-bidopsai \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/BidOpsAI-ECR-Push
```

### Create Access Keys

```bash
aws iam create-access-key --user-name github-actions-bidopsai
```

**Save the output!** You'll need:
- `AccessKeyId`
- `SecretAccessKey`

## Step 3: Configure GitHub Secrets

### Add Secrets to GitHub

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**

Add these secrets:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `AWS_ACCESS_KEY_ID` | From Step 2 | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | From Step 2 | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |

### Optional: Frontend Build Secrets

Add these **only if** you want to bake environment variables into the Docker image:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `NEXT_PUBLIC_API_URL` | Your API URL | `https://api.bidopsai.com/graphql` |
| `NEXT_PUBLIC_AGENT_CORE_URL` | Your agent URL | `https://agents.bidopsai.com` |
| `NEXT_PUBLIC_COGNITO_USER_POOL_ID` | From CDK | `us-east-1_XXXXXXXXX` |
| `NEXT_PUBLIC_COGNITO_CLIENT_ID` | From CDK | `XXXXXXXXXXXXXXXXXXXXXXXXXX` |

> **Note:** If you don't add these, you can set them at runtime via environment variables in ECS/Kubernetes.

## Step 4: Test the Pipeline

### Test via Push

```bash
# Make a small change
git checkout -b test-pipeline
echo "# Pipeline test" >> README.md
git add README.md
git commit -m "test: trigger CI/CD pipeline"
git push origin test-pipeline

# Create PR to trigger lint/test
gh pr create --title "Test Pipeline" --body "Testing CI/CD pipeline"
```

### Test via Manual Trigger

```bash
# Via GitHub CLI
gh workflow run ci-cd.yml

# Force rebuild all services
gh workflow run ci-cd.yml -f force_rebuild=true
```

### Monitor the Run

```bash
# Watch the pipeline
gh run watch

# Or view in browser
gh run view --web
```

## Step 5: Verify ECR Images

After a successful push to `main` or `develop`:

```bash
# List images in each repository
aws ecr list-images --repository-name bidopsai-web --region us-east-1
aws ecr list-images --repository-name bidopsai-core-api --region us-east-1
aws ecr list-images --repository-name bidopsai-agentcore --region us-east-1

# Get image details
aws ecr describe-images --repository-name bidopsai-web --region us-east-1
```

Expected output:
```json
{
    "imageDetails": [
        {
            "imageTags": [
                "develop",
                "develop-abc1234"
            ],
            "imagePushedAt": "2025-10-17T10:30:00+00:00",
            "imageDigest": "sha256:..."
        }
    ]
}
```

## Pipeline Workflow

```
┌─────────────────────────────────────────────┐
│  Trigger: Push/PR/Manual                    │
└──────────────┬──────────────────────────────┘
               │
        ┌──────▼──────┐
        │   Changes   │ ← Detect which services changed
        │  Detection  │
        └──────┬──────┘
               │
        ┌──────┴──────────────┐
        │                     │
┌───────▼────────┐    ┌──────▼────────┐
│  Lint & Test   │    │  Lint & Test  │
│   Frontend     │    │   Backend     │
│   AgentCore    │    │   API         │
└───────┬────────┘    └──────┬────────┘
        │                     │
        └──────┬──────────────┘
               │
        ┌──────▼──────┐
        │   Build &   │ ← Only on push to main/develop
        │  Push ECR   │
        └─────────────┘
```

## Troubleshooting

### Error: "repository does not exist"

**Cause:** ECR repository not created  
**Fix:** Run Step 1 commands

### Error: "Access Denied"

**Cause:** Missing IAM permissions  
**Fix:** Verify IAM policy in Step 2

### Error: "Cannot find module"

**Cause:** Missing dependencies  
**Fix:** Check `package.json` and `package-lock.json` are in sync

### Builds are Slow

**Optimization tips:**
- Enable GitHub Actions cache (already configured)
- Use Docker layer caching (already configured)
- Consider using ECR pull-through cache

### Images Not Tagged as "latest"

**Cause:** Only `main` branch gets `latest` tag  
**Fix:** This is by design. Merge to `main` for `latest` tag.

## Advanced Configuration

### Change ECR Repository Names

Edit `.github/workflows/ci-cd.yml`:

```yaml
env:
  ECR_REPO_WEB: your-new-name-web
  ECR_REPO_API: your-new-name-api
  ECR_REPO_AGENT: your-new-name-agent
```

Then recreate ECR repositories with new names.

### Change AWS Region

Edit `.github/workflows/ci-cd.yml`:

```yaml
env:
  AWS_REGION: us-west-2  # Change here
```

And update ECR repositories in the new region.

### Add Deployment Step

After build jobs, add a deploy job:

```yaml
deploy:
  name: Deploy to ECS
  runs-on: ubuntu-latest
  needs: [build-web, build-api, build-agent]
  if: github.ref == 'refs/heads/main'
  steps:
    - name: Deploy
      run: |
        # Your deployment commands here
```

## Cleanup

To remove the pipeline setup:

```bash
# Delete ECR repositories (⚠️ DESTRUCTIVE)
aws ecr delete-repository --repository-name bidopsai-web --force
aws ecr delete-repository --repository-name bidopsai-core-api --force
aws ecr delete-repository --repository-name bidopsai-agentcore --force

# Delete IAM user
aws iam delete-access-key --user-name github-actions-bidopsai --access-key-id AKIA...
aws iam detach-user-policy --user-name github-actions-bidopsai --policy-arn arn:aws:iam::ACCOUNT:policy/BidOpsAI-ECR-Push
aws iam delete-user --user-name github-actions-bidopsai
aws iam delete-policy --policy-arn arn:aws:iam::ACCOUNT:policy/BidOpsAI-ECR-Push
```

## Next Steps

After pipeline is working:

1. ✅ Set up ECS/EKS deployment
2. ✅ Configure CloudWatch monitoring
3. ✅ Add security scanning (Trivy, Snyk)
4. ✅ Set up staging/production environments
5. ✅ Configure automated rollback

---

**Need Help?** Check the main [README.md](README.md) or contact DevOps team.
