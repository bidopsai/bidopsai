<!--
SYNC IMPACT REPORT
==================
Version Change: 1.0.0 → 2.0.0
Bump Rationale: MAJOR - Complete restructure to align with AWS Well-Architected Framework for AWS hackathon submission. Added monorepo-specific governance and AWS-focused principles.

Modified Principles:
- I. Code Quality → I. AWS Well-Architected Framework (expanded to include 6 pillars)
- II. CLI Interface → REMOVED (not applicable to monorepo scope)
- III. Test-First → III. Test-First Development (retained, enhanced with coverage requirements)
- IV. Integration Testing → IV. Integration & Contract Testing (expanded scope)
- V. Observability & Versioning → Split into V. Observability & Operational Excellence and VI. Versioning & Release Management
- NEW: II. Infrastructure as Code Excellence
- NEW: VII. Security & Compliance First
- NEW: VIII. Monorepo Development Standards

Added Sections:
- AWS Well-Architected Framework Alignment
- Monorepo-Specific Standards
- AWS Hackathon Requirements

Removed Sections:
- CLI Interface principle (not applicable)

Templates Status:
⚠ No templates found in .specify/templates/ - propagation not required at repository root level
✅ Infra constitution at infra/.specify/memory/constitution.md already aligned with AWS principles
✅ README.md reviewed - architecture and AWS services documented

Follow-up TODOs:
- Consider creating .specify/templates/ directory if project-wide templates needed in future
- Ensure infra/ and services/ subdirectories maintain their own constitution compliance
-->

# BidOps.AI Monorepo Constitution

**Project Context**: This repository is a monorepo containing all code for the BidOps.AI project, developed as an AWS hackathon submission. It includes frontend (Next.js), backend (GraphQL API), infrastructure as code (AWS CDK), and AI agents (AWS Bedrock/LangChain).

## Core Principles

### I. AWS Well-Architected Framework (NON-NEGOTIABLE)

All architecture, infrastructure, and application designs MUST align with the six pillars of the AWS Well-Architected Framework:

**Operational Excellence**: Automate changes, respond to events, define standards for workload management. All deployments use IaC with automated CI/CD pipelines.

**Security**: Protect data, systems, and assets through defense-in-depth strategies. AWS Cognito for authentication, encryption at rest and in transit, least-privilege IAM policies, and OWASP Top 10 compliance are mandatory.

**Reliability**: Design for failure recovery, test recovery procedures, scale horizontally. Multi-AZ deployments required for production, automated health checks, and documented disaster recovery procedures.

**Performance Efficiency**: Use compute resources efficiently, experiment with new services. Leverage managed services (Aurora Serverless, Fargate, Bedrock), implement caching strategies, and monitor performance metrics.

**Cost Optimization**: Understand spending, select appropriate resources, scale based on demand. All resources must be tagged (Project, Environment, Owner, CostCenter), use right-sized instances, and leverage Reserved Instances or Savings Plans for long-running workloads.

**Sustainability**: Minimize environmental impact, maximize resource utilization. Prefer serverless and managed services, implement auto-scaling, and decommission unused resources.

**Rationale**: AWS Well-Architected Framework is mandatory for AWS hackathon submissions and ensures best practices are embedded from inception, reducing technical debt and maximizing cloud value.

### II. Infrastructure as Code Excellence

All AWS infrastructure MUST be defined using Infrastructure as Code (AWS CDK preferred):

- Every resource MUST be version controlled and peer reviewed
- Manual console changes are PROHIBITED except for emergency triage (must be back-ported to IaC within 24 hours)
- IaC MUST be modular, reusable, and environment-agnostic
- Secrets and credentials MUST NEVER be hardcoded (use AWS Secrets Manager or Parameter Store)
- CDK stacks MUST follow AWS best practices with proper tagging and resource naming

**Rationale**: IaC ensures reproducibility, auditability, and eliminates configuration drift. Required for hackathon demonstration and production readiness.

### III. Test-First Development (NON-NEGOTIABLE)

All new features require tests before implementation: write failing tests, then implement until tests pass, following a Red-Green-Refactor cycle:

- TDD mandatory for all new features: Tests written → User approved → Tests fail → Then implement
- Minimum 80% code coverage for core business logic
- Unit tests for individual functions and components
- Integration tests for cross-service interactions
- E2E tests for critical user workflows

**Rationale**: Test-first development catches bugs early, serves as living documentation, and ensures code quality meets hackathon standards.

### IV. Integration & Contract Testing

Whenever a new service or contract changes, integration tests must validate end-to-end flows and contract compliance:

- GraphQL schema changes MUST have contract tests
- AWS Bedrock AgentCore integrations MUST be tested with mocked and live endpoints
- Cross-service communication MUST have integration tests in staging
- Shared schemas and API contracts MUST have accompanying validation tests
- SSE (Server-Sent Events) streaming MUST be tested for reliability

**Rationale**: Microservices and agent-based systems require robust integration testing to prevent runtime failures.

### V. Observability & Operational Excellence

All code must emit structured logs and expose health checks for production observability:

- **Structured Logging**: JSON-formatted logs with correlation IDs, sent to CloudWatch Logs
- **Distributed Tracing**: AWS X-Ray MUST be enabled for request tracing across services
- **Metrics & Alarms**: CloudWatch metrics and alarms for key indicators (latency, error rate, saturation)
- **Health Checks**: All services MUST expose /health endpoints
- **Dashboards**: CloudWatch dashboards for real-time monitoring
- **Runbooks**: Operational procedures documented for common failure scenarios

**Rationale**: You cannot fix what you cannot see. Observability enables rapid incident response and meets AWS operational excellence standards.

### VI. Versioning & Release Management

Deployments use semantic versioning (MAJOR.MINOR.PATCH) and track breaking changes:

- **Semantic Versioning**: MAJOR for breaking changes, MINOR for new features, PATCH for fixes
- **Changelogs**: All releases MUST include CHANGELOG.md updates
- **Git Tags**: Version tags MUST be applied to releases
- **Breaking Changes**: MUST include migration guides and deprecation notices
- **Environment Progression**: Dev → Staging → Production (no skipping)

**Rationale**: Clear versioning enables rollbacks, tracks history, and communicates changes to stakeholders.

### VII. Security & Compliance First

All code must adhere to OWASP Top 10, use TLS for all network traffic, and follow security best practices:

- **Authentication**: AWS Cognito with MFA support and Google OAuth integration
- **Authorization**: RBAC with 5 user roles (Admin, Drafter, Bidder, KB-Admin, KB-View)
- **Encryption**: Data encrypted at rest (S3, Aurora) and in transit (TLS 1.2+)
- **Network Isolation**: Private subnets for compute, VPC endpoints for AWS services
- **Secrets Management**: AWS Secrets Manager with auto-rotation for database credentials
- **Vulnerability Scanning**: Container images and dependencies scanned before deployment
- **Least Privilege**: IAM policies grant minimum required permissions

**Rationale**: Security breaches damage trust and disqualify hackathon submissions. Defense-in-depth is mandatory.

### VIII. Monorepo Development Standards

All code commits must be reviewed, tested, and built across the monorepo:

- **Code Review**: All PRs MUST be peer reviewed before merge
- **CI/CD**: Continuous integration enforces linting, type-checking, unit tests, and integration tests
- **Quality Gates**: Code MUST pass all checks before merging
- **Monorepo Structure**: Maintain clear separation: apps/, services/, infra/, docs/
- **Dependency Management**: Use workspace features (npm workspaces) for shared dependencies
- **Independent Deployments**: Each service/app MUST be independently deployable
- **Consistent Tooling**: ESLint, Prettier, TypeScript configs shared across projects

**Rationale**: Monorepo requires discipline to maintain modularity while maximizing code reuse and consistency.

## AWS Hackathon Requirements

As an AWS hackathon submission, this project MUST:

- **Leverage AWS Services**: Bedrock (AgentCore, Knowledge Bases, Data Automation), Cognito, S3, Aurora, CloudWatch, X-Ray
- **Demonstrate Innovation**: Multi-agent workflow orchestration with real-time SSE streaming
- **Follow Best Practices**: AWS Well-Architected Framework compliance demonstrated through documentation
- **Showcase Scalability**: Multi-AZ deployment, auto-scaling, serverless where applicable
- **Include Documentation**: Architecture diagrams, deployment guides, demo scripts
- **Security First**: No hardcoded credentials, encryption everywhere, least-privilege access

## Monorepo-Specific Standards

### Repository Structure

```
bidopsai/
├── apps/web/          # Next.js frontend (TypeScript, React 19, TailwindCSS)
├── services/core-api/ # GraphQL backend (Node.js, Prisma, PostgreSQL)
├── agentcore/         # AI agents (AWS Bedrock, LangChain, Python)
├── infra/             # AWS CDK infrastructure (Python)
├── docs/              # Architecture and API documentation
└── .kiro/steering/    # Project governance and standards
```

### Technology Stack by Layer

**Frontend (apps/web/)**:
- Next.js 15+ with App Router and Server Components
- React 19+ with TypeScript 5.9+
- TailwindCSS 4+ for styling, Framer Motion for animations
- TanStack Query for server state, Zustand for client state
- AWS Amplify v6+ for Cognito integration

**Backend (services/core-api/)**:
- Node.js with GraphQL (Apollo Server)
- PostgreSQL with Prisma ORM
- AWS S3 for document storage with presigned URLs
- Server-Sent Events (SSE) for real-time updates

**AI Agents (agentcore/)**:
- AWS Bedrock AgentCore for agent orchestration
- AWS Bedrock Data Automation for document parsing
- AWS Bedrock Knowledge Bases for vector search
- LangChain/Strands for agent workflows

**Infrastructure (infra/)**:
- AWS CDK 2.219+ (Python)
- Multi-AZ VPC with public/private subnets
- Aurora Serverless v2 PostgreSQL
- ECS Fargate for container orchestration
- CloudFront + ALB for content delivery

### Development Workflow

**Branching Strategy**: Feature branches → Pull Request → Code Review → Main branch → Automated deployment

**Environment Progression**: Development → Staging → Production

**CI/CD Pipeline**:
1. Lint and format check (ESLint, Prettier)
2. Type checking (TypeScript, Python type hints)
3. Unit tests with coverage reports
4. Integration tests in isolated environment
5. Security scanning (SAST, dependency vulnerabilities)
6. Container image build and scan
7. CDK synth and validation
8. Automated deployment to target environment

**Quality Gates**:
- All tests must pass (unit, integration, contract)
- Code coverage ≥80% for core business logic
- No high/critical security vulnerabilities
- TypeScript strict mode compliance
- Linting errors must be zero

## Governance

This constitution supersedes all other practices. All PRs must include a compliance check to ensure constitutional alignment:

**Amendment Process**:
- Amendments require consensus among core team members
- MAJOR version bump for breaking changes or principle removals
- MINOR version bump for new principles or expanded guidance
- PATCH version bump for clarifications and wording improvements
- All amendments MUST be propagated to subdirectory constitutions within 48 hours

**Compliance Review**:
- Pre-merge PR reviews MUST verify constitutional compliance
- Violations MUST be addressed before merge
- Complexity MUST be justified with Architecture Decision Records (ADRs)
- Quarterly audits for codebase-wide compliance

**Enforcement**:
- PRs violating these principles MUST be blocked
- Production deployments violating security/reliability principles MUST be rolled back immediately
- Unjustified deviations require ADR approval from 2+ senior engineers

**Hackathon Demonstration Requirements**:
- Live demo MUST showcase AWS service integration
- Architecture diagram MUST reference AWS Well-Architected pillars
- README MUST include deployment instructions and AWS resource list
- Security practices MUST be documented and demonstrated

**Version**: 2.0.0 | **Ratified**: 2025-10-12 | **Last Amended**: 2025-10-16
