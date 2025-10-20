# Pre-commit Security Hooks Setup

This repository uses [pre-commit](https://pre-commit.com/) hooks to prevent committing sensitive data, enforce code quality, and maintain security standards.

## What Gets Checked

### Security Checks

- ✅ **Secret Detection**: Detects hardcoded secrets, API keys, tokens using `detect-secrets`
- ✅ **AWS Credentials**: Prevents committing AWS access keys, secret keys, and real ARNs
- ✅ **Private Keys**: Detects SSH and other private keys
- ✅ **Large Files**: Prevents committing files larger than 500KB

### Code Quality Checks

- ✅ **Merge Conflicts**: Catches unresolved merge conflict markers
- ✅ **YAML/JSON Syntax**: Validates configuration files
- ✅ **Trailing Whitespace**: Removes unnecessary whitespace
- ✅ **End of File**: Ensures files end with a newline
- ✅ **Code Formatting**: Prettier for TypeScript/JavaScript, Black for Python

## Installation

### Prerequisites

- Python 3.11+ (for pre-commit and Python hooks)
- Node.js 24+ (for JavaScript/TypeScript formatting)

### Quick Setup

```bash
# Install pre-commit
pip install pre-commit

# Install the git hooks
pre-commit install

# (Optional) Run on all files to verify setup
pre-commit run --all-files
```

## Usage

### Automatic Checks

Once installed, pre-commit hooks run automatically on `git commit`. If any check fails:

1. The commit will be blocked
2. You'll see which checks failed and why
3. Fix the issues and try committing again

### Manual Checks

```bash
# Run on all files
pre-commit run --all-files

# Run on specific files
pre-commit run --files apps/web/src/app/page.tsx

# Run a specific hook
pre-commit run detect-secrets --all-files

# Skip hooks (NOT RECOMMENDED for security hooks)
git commit --no-verify
```

## CI/CD Integration

The same pre-commit hooks run in the GitHub Actions CI/CD pipeline in the `security` job. This ensures:

- No one can bypass security checks by skipping local hooks
- All pull requests are validated before merge
- Consistent security standards across all contributors

## Troubleshooting

### False Positives in Secret Detection

If `detect-secrets` flags a false positive:

1. Create a baseline file:

   ```bash
   detect-secrets scan --baseline .secrets.baseline
   ```

2. Review and commit the baseline (but be careful!)

### Excluding Files

To exclude specific files or directories, update `.pre-commit-config.yaml`:

```yaml
hooks:
  - id: detect-secrets
    exclude: ^(path/to/exclude/|another/path/)
```

### Hook Update Issues

If hooks fail after updating:

```bash
# Clean pre-commit cache
pre-commit clean
pre-commit install --install-hooks
```

## What If I Find Secrets?

If you accidentally committed secrets:

1. **Immediately** rotate/revoke the exposed credentials
2. Remove them from git history using `git-filter-repo` or BFG Repo-Cleaner
3. Force push (if allowed) or contact a repo admin
4. Never rely on simply removing secrets in a new commit - they remain in git history!

## Repository Structure

This monorepo has different tools for different components:

- **Frontend** (`apps/web/`): TypeScript/React with Prettier
- **Core API** (`services/core-api/`): TypeScript/Node.js with Prettier
- **AgentCore** (`agentcore/`): Python with Black
- **Infrastructure** (`infra/`): Has its own `.pre-commit-config.yaml` (separate checks)

## Resources

- [Pre-commit Documentation](https://pre-commit.com/)
- [Detect Secrets](https://github.com/Yelp/detect-secrets)
- [Prettier](https://prettier.io/)
- [Black](https://black.readthedocs.io/)
