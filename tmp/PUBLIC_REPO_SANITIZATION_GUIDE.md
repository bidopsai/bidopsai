# Public Repository Sanitization Guide - BidOps.AI Hackathon Submission

## 🎯 Executive Summary

This guide identifies what to **exclude**, **mask**, or **keep** when creating a public fork for the AWS AI Agent Global Hackathon submission. The goal: showcase your work while protecting sensitive business logic and credentials.

**Key Principle**: The code doesn't need to be fully functional - it just needs to demonstrate your architecture, approach, and innovation.

---

## 📊 Classification Matrix

| Category | Action | Reason |
|----------|--------|--------|
| **AWS Account IDs** | ✅ KEEP (already public) | Visible in DNS, ARNs don't expose security risk |
| **Cognito Pool IDs** | ✅ KEEP (already public) | Public-facing auth endpoints, already in DNS |
| **Domain Names** | ✅ KEEP (already public) | bidopsai.com is public DNS |
| **Architecture Diagrams** | ✅ KEEP | Core hackathon requirement |
| **CDK Infrastructure Code** | ⚠️ REDACT PARTIALLY | Keep structure, remove business logic |
| **Frontend Code** | ✅ KEEP MOSTLY | Remove API integrations, keep UI/UX |
| **GraphQL Schema** | ⚠️ REDACT PARTIALLY | Keep structure, remove proprietary queries |
| **Agent Implementation** | 🔒 EXCLUDE COMPLETELY | Your competitive advantage |
| **Database Schema** | ⚠️ REDACT PARTIALLY | Keep ERD, remove sensitive tables |
| **Business Logic** | 🔒 EXCLUDE COMPLETELY | Proprietary algorithms |
| **Test Data** | 🔒 EXCLUDE COMPLETELY | May contain client info |
| **Secrets/Credentials** | 🔒 EXCLUDE COMPLETELY | Security risk |
| **Documentation** | ✅ KEEP | Shows professionalism |

---

## 🔒 MUST EXCLUDE (Security Risks)

### 1. Actual Secrets & Credentials
**Files to DELETE:**
```bash
# Environment files (never committed, but check)
**/.env
**/.env.local
**/.env.development
**/.env.production
apps/web/.env.local
services/core-api/.env

# AWS credentials
~/.aws/credentials
~/.aws/config

# Any files with actual passwords/tokens
```

**Content to REDACT:**
- Any hardcoded AWS access keys (AKIA...)
- Database passwords
- JWT secrets
- Third-party API keys (OpenAI, etc.)
- Session secrets
- OAuth client secrets (Google, etc.)

**Search & Destroy:**
```bash
# Find potential secrets
grep -r "AKIA" .
grep -r "aws_secret_access_key" .
grep -r "password.*=" . --include="*.py" --include="*.ts"
```

---

## 🎨 KEEP AS-IS (Public or Required)

### 1. AWS Account ID: `568790270051`
**Action**: ✅ **KEEP**  
**Why**: Already public in DNS records, ACM certificates, and CloudFormation exports. Account IDs alone don't grant access.

**Where it appears:**
- `infra/docs/deployment/*.md`
- CloudFormation outputs
- ACM certificate ARNs

### 2. Cognito Pool IDs
**Action**: ✅ **KEEP**  
**Why**: Public-facing authentication endpoints. Useless without valid credentials.

**IDs to keep:**
- User Pool: `us-east-1_3tjXn7pNM`
- App Client: `4uci08tqhijkrncjbebr3hu60q`
- Domain: `hackathon-dev.auth.us-east-1.amazoncognito.com`

**Where it appears:**
- `infra/docs/cognito/*.md`
- `apps/web/src/lib/auth/amplify.config.ts`
- Documentation files

### 3. Domain Names
**Action**: ✅ **KEEP**  
**Why**: Already public in DNS (bidopsai.com). No security risk.

### 4. Architecture Documentation
**Action**: ✅ **KEEP ALL**  
**Why**: Required for hackathon judging.

**Files to keep:**
```
docs/architecture/
├── README.md
├── agent-core/
│   └── agentic-flow.mmd
├── core-api/
│   └── gql-schema.md
├── infra/
│   └── infra-architecture.md
└── web-frontend/
```

### 5. Public Documentation
**Action**: ✅ **KEEP**  
**Files:**
- `README.md`
- `HACKATHON_SUBMISSION.md`
- `docs/` (all public-facing docs)
- `AGENTS.md` (workflow guide)

---

## ⚠️ PARTIAL REDACTION (Sanitize Business Logic)

### 1. Infrastructure Code (`infra/`)

#### KEEP:
- CDK stack structure
- Resource types (VPC, RDS, ECS, etc.)
- Architecture patterns
- Deployment scripts

#### REDACT:
```python
# BEFORE (in infra/cdk/stacks/compute.py)
task_definition.add_container(
    "AgentCore",
    environment={
        "MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
        "AGENT_INSTRUCTIONS": "You are a bid analysis expert...",  # 🔒 REMOVE THIS
        "PROPRIETARY_ALGORITHM": "use_custom_ranking_v2",        # 🔒 REMOVE THIS
    }
)

# AFTER (sanitized)
task_definition.add_container(
    "AgentCore",
    environment={
        "MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
        # Proprietary agent configuration removed for public submission
    }
)
```

**Script to help:**
```bash
# Create sanitized version
cd infra/cdk/stacks
for file in *.py; do
    # Remove proprietary logic comments
    sed -i 's/# Proprietary:.*/# [REDACTED - Proprietary Implementation]/g' "$file"
done
```

### 2. AgentCore Implementation (`agentcore/`)

**Recommendation**: 🔒 **EXCLUDE ENTIRE DIRECTORY**

**Why**: This is your competitive advantage. Your multi-agent orchestration logic is what makes BidOps.AI unique.

**Alternative**: Create a **stub implementation** for demo purposes:

```python
# agentcore/agent.py (PUBLIC VERSION - STUB)
"""
BidOps.AI AgentCore - Multi-Agent Orchestration System

NOTE: This is a simplified stub for hackathon demonstration.
Full implementation uses proprietary algorithms and is not included.
"""

from typing import Dict, Any
import boto3

class AgentSupervisor:
    """
    Orchestrates 8 specialized agents for bid automation.
    
    Agents:
    - Parser Agent: Document extraction (AWS Bedrock Data Automation)
    - Analysis Agent: Requirement analysis (Claude 3 Sonnet)
    - Content Agent: Proposal generation (Claude 3 Haiku)
    - Knowledge Agent: Historical bid search (Bedrock Knowledge Bases)
    - Compliance Agent: Regulatory validation
    - QA Agent: Quality assurance
    - Comms Agent: Stakeholder notifications
    - Submission Agent: Final submission
    """
    
    def __init__(self):
        self.bedrock_client = boto3.client('bedrock-agent-runtime')
        # Real implementation uses custom state machine
        # [REDACTED - Proprietary orchestration logic]
    
    async def process_rfp(self, document_url: str) -> Dict[str, Any]:
        """
        Main workflow entry point.
        
        In production, this coordinates all 8 agents with:
        - Stateful workflow management (PostgreSQL)
        - Error recovery and retry logic
        - Human-in-the-loop approval gates
        - Real-time streaming to frontend
        
        [STUB IMPLEMENTATION - See HACKATHON_SUBMISSION.md for full description]
        """
        return {
            "status": "success",
            "message": "Full implementation redacted for public submission"
        }
```

### 3. GraphQL API (`services/core-api/`)

#### KEEP:
- GraphQL schema structure
- Type definitions
- Authentication middleware
- Database setup scripts

#### REDACT:
```typescript
// services/core-api/src/resolvers/project.resolver.ts

// BEFORE
export const projectResolvers = {
  Mutation: {
    async createProject(parent, args, context) {
      // Proprietary bid scoring algorithm
      const score = await calculateProprietaryBidScore(args.data);  // 🔒 REMOVE
      
      // Custom ML-based deadline estimation
      const deadline = await aiPredictDeadline(args.data);          // 🔒 REMOVE
      
      return context.prisma.project.create({ data: args.data });
    }
  }
};

// AFTER (sanitized)
export const projectResolvers = {
  Mutation: {
    async createProject(parent, args, context) {
      // [REDACTED - Proprietary bid scoring and deadline prediction]
      return context.prisma.project.create({ data: args.data });
    }
  }
};
```

**Keep:**
- Basic CRUD operations
- Authentication/authorization logic
- Input validation
- Error handling

**Remove:**
- Proprietary algorithms
- Custom ML models
- Business-specific scoring logic
- Client-specific customizations

### 4. Frontend (`apps/web/`)

#### KEEP:
- UI/UX components
- Theme system (your futuristic themes are impressive!)
- Routing structure
- State management patterns
- Animation/design system

#### REDACT:
```typescript
// apps/web/src/components/agents/AgentProgress.tsx

// BEFORE
export function AgentProgress({ projectId }: Props) {
  // Proprietary real-time agent streaming protocol
  const { stream } = useCustomAgentStream(projectId);  // 🔒 REMOVE IMPLEMENTATION
  
  // Custom progress calculation
  const progress = calculateProprietaryProgress(stream); // 🔒 REMOVE
  
  return <ProgressBar value={progress} />;
}

// AFTER (sanitized)
export function AgentProgress({ projectId }: Props) {
  // [REDACTED - Proprietary agent streaming implementation]
  // See HACKATHON_SUBMISSION.md for architecture overview
  
  const progress = 75; // Mock data for demo
  return <ProgressBar value={progress} />;
}
```

**Keep the visuals, remove the backend integration.**

### 5. Database Schema (`services/core-api/prisma/`)

#### KEEP:
- Entity Relationship Diagram (ERD)
- Core table structure (projects, users, artifacts)
- Public schema documentation

#### REDACT:
```prisma
// services/core-api/prisma/schema.prisma

// BEFORE
model Project {
  id              String   @id @default(uuid())
  name            String
  // ... public fields ...
  
  // 🔒 REMOVE: Proprietary scoring fields
  proprietaryScore Float?   
  aiConfidence     Float?
  customRanking    Json?
  
  // 🔒 REMOVE: Client-specific fields
  clientSecretData Json?
}

// AFTER (sanitized)
model Project {
  id              String   @id @default(uuid())
  name            String
  // ... public fields ...
  
  // [REDACTED - Proprietary scoring and client-specific fields]
}
```

**Alternative**: Replace `schema.prisma` with ERD diagram only:
```
docs/database/bidopsai.mmd  # Keep this (visual diagram)
services/core-api/prisma/   # Replace with stub schema
```

---

## 📁 Files & Directories - Action Plan

### 🔒 DELETE COMPLETELY

```bash
# Agent implementation (your secret sauce)
agentcore/agent.py          # Replace with stub (see above)
agentcore/orchestrator.py   # DELETE
agentcore/tools/            # DELETE (custom tool implementations)

# Environment files
**/.env*
apps/web/.env.local
services/core-api/.env

# Test data (may contain client info)
services/core-api/prisma/seed.ts  # DELETE or sanitize
infra/tests/fixtures/             # DELETE real data

# Proprietary documentation
docs/scratches/                   # DELETE (internal brainstorming)
specs/**/contracts/               # DELETE (contract tests have real data)

# Temporary/build artifacts
tmp/                              # DELETE
.venv/                            # DELETE
node_modules/                     # DELETE (already in .gitignore)
```

### ⚠️ SANITIZE (Keep structure, remove logic)

```bash
# Infrastructure
infra/cdk/stacks/*.py             # Remove proprietary config
infra/specs/                      # Remove internal task details

# Backend
services/core-api/src/resolvers/  # Simplify business logic
services/core-api/src/services/   # Remove proprietary algorithms
services/core-api/prisma/schema.prisma  # Remove secret fields

# Frontend
apps/web/src/lib/api/             # Replace real API calls with mocks
apps/web/src/hooks/               # Simplify custom hooks
```

### ✅ KEEP AS-IS

```bash
# Documentation (required for judging)
README.md
HACKATHON_SUBMISSION.md
AGENTS.md
docs/architecture/
docs/database/bidopsai.mmd

# Public infrastructure
.github/workflows/ci-cd.yml       # OIDC workflow (good practice to show)
docker/                           # Dockerfile examples
Makefile                          # Build scripts

# Frontend (showcase)
apps/web/src/components/ui/       # Your UI components (impressive!)
apps/web/src/styles/              # Theme system
apps/web/tailwind.config.ts       # Design tokens

# Schema (structure only)
services/core-api/src/schema/     # GraphQL schema types
```

---

## 🛠️ Sanitization Script

Create this script to automate sanitization:

```bash
#!/bin/bash
# scripts/sanitize-for-public.sh

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
PUBLIC_REPO="/tmp/bidopsai-public"

echo "🧹 Creating sanitized public repository..."

# 1. Clone to temporary location
rm -rf "$PUBLIC_REPO"
git clone "$REPO_ROOT" "$PUBLIC_REPO"
cd "$PUBLIC_REPO"

# 2. Delete sensitive directories
echo "🔒 Removing sensitive files..."
rm -rf \
  agentcore/ \
  .env* \
  **/.env* \
  tmp/ \
  .venv/ \
  docs/scratches/ \
  specs/**/contracts/ \
  services/core-api/prisma/seed.ts

# 3. Create stub files
echo "📝 Creating stub implementations..."

# Stub agent
mkdir -p agentcore
cat > agentcore/agent.py << 'EOF'
"""
BidOps.AI AgentCore - Multi-Agent Orchestration System (STUB)

NOTE: Full implementation redacted for public hackathon submission.
See HACKATHON_SUBMISSION.md for architecture details.
"""

class AgentSupervisor:
    """Stub implementation - see documentation for full system."""
    def __init__(self):
        pass
    
    async def process_rfp(self, document_url: str):
        return {"status": "stub", "message": "Implementation redacted"}
EOF

# Stub .env.example
cat > services/core-api/.env.example << 'EOF'
# Application
NODE_ENV=development
PORT=4000

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/bidopsai

# AWS (use your own credentials)
AWS_REGION=us-east-1
AWS_COGNITO_USER_POOL_ID=your-pool-id
AWS_COGNITO_CLIENT_ID=your-client-id

# [REDACTED - See documentation for full configuration]
EOF

# 4. Sanitize documentation files
echo "📄 Sanitizing documentation..."
find infra/docs -name "*.md" -exec sed -i 's/568790270051/XXXXXXXXXXXX/g' {} \;

# 5. Add public README note
cat > PUBLIC_REPO_NOTE.md << 'EOF'
# 🚨 Public Repository Notice

This is a **sanitized version** of BidOps.AI created for the AWS AI Agent Global Hackathon.

**What's included:**
- ✅ Architecture documentation
- ✅ Infrastructure as Code (CDK)
- ✅ UI/UX components
- ✅ GraphQL schema structure
- ✅ Deployment guides

**What's excluded:**
- 🔒 Proprietary agent orchestration logic
- 🔒 Business-specific algorithms
- 🔒 Production credentials
- 🔒 Client-specific customizations

**To run this code:**
This repository demonstrates our architecture and approach. To build a working system, you'll need to implement the agent logic using AWS Bedrock AgentCore as described in `HACKATHON_SUBMISSION.md`.

**Full submission details:** See `HACKATHON_SUBMISSION.md`
EOF

# 6. Commit and show summary
git add -A
git commit -m "chore: sanitize for public hackathon submission"

echo "✅ Sanitization complete!"
echo ""
echo "📊 Summary:"
echo "  - Location: $PUBLIC_REPO"
echo "  - Next steps:"
echo "    1. Review changes: cd $PUBLIC_REPO && git log -1 --stat"
echo "    2. Create GitHub repo: gh repo create bidopsai/bidopsai-hackathon --public"
echo "    3. Push: git remote add origin <url> && git push -u origin main"
echo ""
echo "⚠️  IMPORTANT: Review manually before pushing!"
```

**Usage:**
```bash
chmod +x scripts/sanitize-for-public.sh
./scripts/sanitize-for-public.sh
cd /tmp/bidopsai-public
# Manual review
git log --stat
# Push to public repo
```

---

## 🎯 Final Checklist

Before making the repo public, verify:

### Security Checks
- [ ] No AWS access keys (search for `AKIA`)
- [ ] No database passwords
- [ ] No JWT secrets
- [ ] No third-party API keys
- [ ] No client data in test fixtures
- [ ] No internal IP addresses
- [ ] No proprietary algorithm implementations

### Content Checks
- [ ] Architecture diagrams present
- [ ] README explains what's redacted
- [ ] HACKATHON_SUBMISSION.md complete
- [ ] Stub implementations for excluded code
- [ ] .env.example files sanitized
- [ ] Documentation links work

### Functionality Check
- [ ] Can clone and read code
- [ ] Architecture is clear
- [ ] Innovation is evident
- [ ] Doesn't need to run (per organizer guidance)

---

## 📋 Quick Reference - What Judges Need

Hackathon judges evaluate:

1. **Technical Excellence (50%)**: ✅ Keep infrastructure code, remove business logic
2. **Innovation (10%)**: ✅ Keep architecture docs, agent workflow diagrams
3. **Value/Impact (20%)**: ✅ Keep HACKATHON_SUBMISSION.md with impact metrics
4. **Functionality (10%)**: ⚠️ Stub implementations OK per organizers
5. **Demo (10%)**: ✅ Keep video, screenshots in docs/

**You can safely remove:**
- Actual agent implementation
- Proprietary algorithms
- Client-specific code
- Production credentials
- Internal documentation

**You must keep:**
- Architecture diagrams
- CDK infrastructure structure
- UI/UX showcase
- Documentation
- GraphQL schema types

---

## 🚀 Recommended Approach

### Option 1: Minimal Sanitization (Recommended)
**Best for**: Showcasing work while protecting core IP

1. Delete `agentcore/` (replace with stub)
2. Remove `.env` files
3. Sanitize test data
4. Add `PUBLIC_REPO_NOTE.md`
5. Push to new public repo

**Effort**: 2 hours  
**Risk**: Low  
**Impact**: High (shows architecture, hides secret sauce)

### Option 2: Full Sanitization
**Best for**: Maximum security

1. Run `sanitize-for-public.sh` script
2. Manual review of all code
3. Replace real API calls with mocks
4. Remove all proprietary comments
5. Sanitize git history (BFG Repo-Cleaner)

**Effort**: 8 hours  
**Risk**: Very Low  
**Impact**: High (completely clean)

### Option 3: Two-Repo Strategy
**Best for**: Flexibility

1. Keep private repo as-is
2. Create new public repo from scratch
3. Copy only public-safe files
4. Add comprehensive documentation

**Effort**: 4 hours  
**Risk**: Very Low  
**Impact**: Medium (requires documentation rewrite)

---

## 💡 Pro Tips

1. **Don't over-sanitize**: Account IDs and Cognito pools are already public. No need to redact.

2. **Use stubs, not deletion**: Judges want to see structure, not necessarily working code.

3. **Document what's redacted**: Add comments like `// [REDACTED - Proprietary implementation]`

4. **Keep the impressive parts**: Your UI/UX, architecture diagrams, and infrastructure code are showcase-worthy.

5. **Test the public repo**: Clone it fresh and see if judges can understand your work.

---

## 📞 Questions?

**Q: Can I include AWS account IDs?**  
A: ✅ Yes, they're already public in DNS records.

**Q: What about Cognito pool IDs?**  
A: ✅ Yes, public auth endpoints are safe to share.

**Q: Should I sanitize git history?**  
A: ⚠️ Optional, but recommended if you ever committed secrets.

**Q: Do I need a working demo?**  
A: ❌ No, per organizers: "not mandatory that code should be working"

**Q: How much can I redact?**  
A: As much as needed to protect IP, as long as architecture is clear.

---

**Generated**: 2025-10-19  
**For**: AWS AI Agent Global Hackathon Submission  
**Repository**: bidopsai/bidopsai
