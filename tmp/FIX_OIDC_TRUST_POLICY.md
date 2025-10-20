# Fix OIDC Trust Policy for Feature Branches

## Problem
Your PR on `fix/security-scan-trivy` branch will fail authentication because the OIDC role's trust policy only allows `main` and `develop` branches.

Current trust policy:
```json
"token.actions.githubusercontent.com:sub": [
    "repo:bidopsai/bidopsai:ref:refs/heads/main",
    "repo:bidopsai/bidopsai:ref:refs/heads/develop",
    "repo:chamikabm/bidopsai:ref:refs/heads/main",
    "repo:chamikabm/bidopsai:ref:refs/heads/develop",
    "repo:jerryyf/aws-hackathon-infra:ref:refs/heads/main",
    "repo:jerryyf/aws-hackathon-infra:ref:refs/heads/develop"
]
```

## ⚡ Quick Fix - Update Trust Policy Manually

### Step 1: Find Your OIDC Role
```bash
# Get the role ARN from your GitHub secrets
echo ${{ secrets.AWS_ROLE_ARN }}
# Or check the workflow file for the hardcoded role name
```

### Step 2: Update Trust Policy in AWS Console

1. Go to IAM Console: https://console.aws.amazon.com/iam/
2. Navigate to **Roles**
3. Search for your GitHub Actions role (likely named something like `github-actions-role` or `bidopsai-cicd-role`)
4. Click on the role
5. Go to **Trust relationships** tab
6. Click **Edit trust policy**
7. Replace the `StringEquals` condition with `StringLike` and use wildcards:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws:iam::568790270051:oidc-provider/token.actions.githubusercontent.com"
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringLike": {
                    "token.actions.githubusercontent.com:sub": [
                        "repo:bidopsai/bidopsai:ref:refs/heads/*",
                        "repo:chamikabm/bidopsai:ref:refs/heads/*",
                        "repo:jerryyf/aws-hackathon-infra:ref:refs/heads/*"
                    ]
                },
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                }
            }
        }
    ]
}
```

**Key Changes:**
- Changed `StringEquals` to `StringLike` for the `sub` condition
- Changed `ref:refs/heads/main` to `ref:refs/heads/*` (wildcard for all branches)
- Removed duplicate entries for main/develop (wildcard covers them)

### Step 3: Save and Test

1. Click **Update policy**
2. Your PR workflow should now be able to authenticate
3. Check the Actions tab to see if the workflow runs successfully

---

## 🏗️ Permanent Fix - Add OIDC to CDK (Recommended)

Create a proper CDK stack for GitHub OIDC authentication.

### Create New Stack File

**File:** `infra/cdk/stacks/cicd_stack.py`

```python
"""
CI/CD Stack for GitHub Actions OIDC Integration

Manages:
- GitHub OIDC Identity Provider
- IAM Role for GitHub Actions workflows
- ECR push/pull permissions
"""

from aws_cdk import Stack, aws_iam as iam, CfnOutput, Tags
from constructs import Construct


class CicdStack(Stack):
    """CI/CD infrastructure for GitHub Actions"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        github_org: str = "bidopsai",
        github_repo: str = "bidopsai",
        environment: str = "dev",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.github_org = github_org
        self.github_repo = github_repo
        self.env_name = environment

        # Create or import OIDC provider
        self.github_provider = self._create_oidc_provider()

        # Create GitHub Actions role with ECR permissions
        self.github_actions_role = self._create_github_actions_role()

        # Create outputs
        self._create_outputs()

        # Add tags
        Tags.of(self).add("Environment", environment)
        Tags.of(self).add("Project", "AWSHackathon")
        Tags.of(self).add("ManagedBy", "CDK")

    def _create_oidc_provider(self) -> iam.IOpenIdConnectProvider:
        """
        Create GitHub OIDC provider (or import existing one)
        
        NOTE: OIDC providers are account-level resources, not stack-specific.
        If it already exists, you'll get an error. In that case, use:
        iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(...)
        """

        # Try to create OIDC provider (comment out if already exists)
        try:
            provider = iam.OpenIdConnectProvider(
                self,
                "GitHubOIDCProvider",
                url="https://token.actions.githubusercontent.com",
                client_ids=["sts.amazonaws.com"],
                thumbprints=[
                    # GitHub's OIDC thumbprint (valid as of 2024)
                    "6938fd4d98bab03faadb97b34396831e3780aea1",
                    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",  # Backup
                ],
            )
            return provider
        except Exception:
            # If provider already exists, import it
            provider_arn = (
                f"arn:aws:iam::{Stack.of(self).account}:"
                f"oidc-provider/token.actions.githubusercontent.com"
            )
            return iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
                self, "GitHubOIDCProviderImported", provider_arn
            )

    def _create_github_actions_role(self) -> iam.Role:
        """Create IAM role for GitHub Actions with ECR permissions"""

        # Build trust policy for all branches
        assume_role_principal = iam.FederatedPrincipal(
            federated=self.github_provider.open_id_connect_provider_arn,
            conditions={
                "StringLike": {
                    "token.actions.githubusercontent.com:sub": [
                        f"repo:{self.github_org}/{self.github_repo}:ref:refs/heads/*",
                        # Also allow pull requests
                        f"repo:{self.github_org}/{self.github_repo}:pull_request",
                    ]
                },
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                },
            },
            assume_role_action="sts:AssumeRoleWithWebIdentity",
        )

        role = iam.Role(
            self,
            "GitHubActionsRole",
            role_name=f"github-actions-{self.env_name}",
            assumed_by=assume_role_principal,
            description=f"Role for GitHub Actions CI/CD workflows - {self.env_name}",
            max_session_duration=Stack.of(self).to_duration(3600),  # 1 hour
        )

        # ECR permissions for all bidopsai repositories
        role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRAuthToken",
                effect=iam.Effect.ALLOW,
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )

        role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRImageManagement",
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:PutImage",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload",
                    "ecr:DescribeRepositories",
                    "ecr:ListImages",
                    "ecr:DescribeImages",
                ],
                resources=[
                    f"arn:aws:ecr:{Stack.of(self).region}:{Stack.of(self).account}:repository/bidopsai/*"
                ],
            )
        )

        # CloudWatch Logs for debugging
        role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudWatchLogs",
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/github-actions/*"
                ],
            )
        )

        return role

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs"""

        CfnOutput(
            self,
            "GitHubActionsRoleArn",
            value=self.github_actions_role.role_arn,
            description="IAM Role ARN for GitHub Actions workflows",
            export_name=f"GitHubActionsRoleArn-{self.env_name}",
        )

        CfnOutput(
            self,
            "GitHubOIDCProviderArn",
            value=self.github_provider.open_id_connect_provider_arn,
            description="GitHub OIDC Provider ARN",
            export_name=f"GitHubOIDCProviderArn-{self.env_name}",
        )
```

### Update app.py

**File:** `infra/cdk/app.py`

Add the new stack:

```python
from stacks.cicd_stack import CicdStack

# ... existing imports ...

# Add CICD stack
cicd_stack = CicdStack(
    app,
    f"BidOpsAI-CICD-{config.environment}",
    github_org="bidopsai",
    github_repo="bidopsai",
    environment=config.environment,
    env=cdk.Environment(
        account=config.account_id,
        region=config.region,
    ),
)
```

### Deploy the Stack

```bash
cd infra
source .venv/bin/activate
cd cdk
cdk deploy BidOpsAI-CICD-dev --profile your-profile
```

### Update GitHub Secret

After deployment, update your GitHub secret `AWS_ROLE_ARN` with the new role ARN from the CloudFormation outputs.

---

## 🎯 Recommendation

**For NOW (to unblock your PR):**
- Use **Quick Fix** - Update trust policy manually to use wildcards

**For LATER (proper solution):**
- Use **Permanent Fix** - Add OIDC stack to CDK
- This makes your infrastructure fully reproducible
- Ensures trust policy is version-controlled
- Easier to manage across environments

---

## ⚠️ Security Considerations

### Wildcard Pattern Security

Using `ref:refs/heads/*` allows **any branch** to authenticate. If you want tighter security:

```json
// Only allow specific branch patterns
"token.actions.githubusercontent.com:sub": [
    "repo:bidopsai/bidopsai:ref:refs/heads/main",
    "repo:bidopsai/bidopsai:ref:refs/heads/develop",
    "repo:bidopsai/bidopsai:ref:refs/heads/feature/*",
    "repo:bidopsai/bidopsai:ref:refs/heads/fix/*",
    "repo:bidopsai/bidopsai:pull_request"
]
```

This allows:
- ✅ main, develop branches
- ✅ feature/* branches (e.g., feature/new-thing)
- ✅ fix/* branches (e.g., fix/security-scan-trivy)
- ✅ Pull requests
- ❌ Any other branches (e.g., personal/test-branch)

Choose the pattern that matches your branching strategy!
