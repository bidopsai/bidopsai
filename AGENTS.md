# Agent Guidelines for BidOps.AI

Specs can be found in .kiro/specs and top level specs/ folders.

## Commands

### Frontend (apps/web)
- `cd apps/web && npm run dev` - Start Next.js dev server with Turbopack
- `cd apps/web && npm run build` - Build for production
- `cd apps/web && npm run lint` - Run ESLint
- `cd apps/web && npx tsc --noEmit` - Type check
- `cd apps/web && npx prettier --write "src/**/*.{ts,tsx}"` - Format code

### GraphQL API (services/core-api)
- `cd services/core-api && npm run dev` - Start API server with hot reload
- `cd services/core-api && npm test` - Run all Jest tests
- `cd services/core-api && npm test -- path/to/test.spec.ts` - Run single test file
- `cd services/core-api && npm run lint` - Run ESLint
- `cd services/core-api && npm run format` - Format with Prettier

### Infrastructure (infra)
- `cd infra && source .venv/bin/activate` - Activate Python virtual environment
- `cd infra && PYTHONPATH=. pytest` - Run all tests
- `cd infra && PYTHONPATH=. pytest tests/unit/test_file.py::test_name` - Run single test
- `cd infra/cdk && pyright` - Type check Python code

## Code Style

### TypeScript (Frontend & API)
- **Formatting**: Prettier with semi, 2-space tabs, 100 char width. Frontend uses double quotes, API uses single quotes
- **Types**: Use strict mode, no implicit any, prefer `string | null` over `Optional<string>`
- **Imports**: Group by stdlib → third-party → local, use path aliases (`@/` for apps/web)
- **Naming**: camelCase for vars/functions, PascalCase for types/components, UPPER_SNAKE_CASE for constants
- **Error handling**: Use custom error classes (AppError, ValidationError), never expose internal errors in production
- **React**: Function components only, use hooks, Server Components by default (mark Client Components with `'use client'`)
- **GraphQL**: Schema-first development, use DataLoader for N+1 prevention, validate inputs with Zod

### Python (Infrastructure)
- **Python 3.11+** with type hints, use `str | None` syntax
- **Formatting**: Black (line-length 88), no module/class docstrings
- **Imports**: Group by stdlib → third-party → local, AWS CDK imports use `as` aliases (e.g., `aws_ec2 as ec2`)
- **Naming**: snake_case for vars/functions, PascalCase for classes, ALL_CAPS for constants
- **CDK**: Use L2 constructs, `CfnOutput` for exports, check `self.account`/`self.region` before context lookups

## Testing
- **Frontend**: TDD principles, write tests before implementation (see .kiro/steering/fe-testing-standards.md)
- **API**: Jest with testcontainers for integration tests, contract tests validate GraphQL schema (see .kiro/steering/gql-testing-standards.md)
- **Infrastructure**: pytest with Template.from_stack() assertions, contract tests validate CloudFormation outputs

## Workflow
- This project uses Kiro specs. Always read documents in .kiro/specs and update the tasks as they are completed.
- Follow spec-kit workflows in specs/ directories (spec.md, plan.md, tasks.md)
- Use @general subagent for complex searches or multi-step tasks
- DO NOT run git/gh commands unless explicitly granted permission
- Use context7 for up-to-date documentation, webfetch for URLs provided by user or context7
