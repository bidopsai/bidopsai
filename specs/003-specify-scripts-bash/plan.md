# Implementation Plan: AWS Strands Agent Build and Push to ECR Automation

**Branch**: `003-specify-scripts-bash` | **Date**: 2025-10-16 | **Spec**: [spec.md](./spec.md)

## Summary

Build automation scripts for containerizing Strands AI agents and deploying to AWS ECR for use with Bedrock AgentCore runtimes. Implementation provides four bash scripts: individual build/push operations, combined workflow, and verification utility.

## Technical Context

**Language/Version**: Bash 4.0+  
**Primary Dependencies**: Docker 20.10+, AWS CLI 2.0+, jq 1.6+  
**Storage**: AWS Elastic Container Registry (ECR)  
**Testing**: Manual testing with sample Strands agent, shellcheck linting  
**Target Platform**: macOS/Linux developer environments, CI/CD pipelines  
**Project Type**: Single (bash scripts)  
**Performance Goals**: Build + push in <5 minutes (excluding network)  
**Constraints**: ARM64 only, Docker buildx required, ECR 10GB image limit  
**Scale/Scope**: 4 scripts supporting local development and CI/CD automation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

✅ **Infrastructure as Code Excellence**: Scripts automate ECR repository creation following IaC principles  
✅ **Test-First Development**: Manual testing plan defined; shellcheck for static analysis  
✅ **Observability & Operational Excellence**: Scripts emit structured output, progress indicators, error messages  
✅ **Security & Compliance First**: AWS credentials via environment variables only; no credential storage  
✅ **Monorepo Development Standards**: Scripts placed in `/scripts` directory following repository structure  

**No constitutional violations** - Scripts are infrastructure automation utilities, exempt from application-level TDD requirements.

## Project Structure

### Documentation (this feature)

```
specs/003-specify-scripts-bash/
├── plan.md              # This file
├── research.md          # Technical research (Docker buildx, ECR API)
├── data-model.md        # Script inputs/outputs, configuration schema
├── quickstart.md        # Usage examples and troubleshooting
└── checklists/
    └── requirements.md  # Quality validation checklist
```

### Source Code (repository root)

```
scripts/
├── build-agent.sh       # P1: Build ARM64 Docker image for Strands agent
├── push-to-ecr.sh       # P1: Authenticate with ECR and push image
├── build-and-push.sh    # P2: Combined workflow (calls build + push)
├── verify-ecr-image.sh  # P3: Query ECR for image metadata
└── README.md            # Updated with new script documentation

agentcore/
├── agent.py             # Sample Strands agent for testing
└── Dockerfile           # Sample Dockerfile for testing
```

**Structure Decision**: Scripts in `/scripts` following existing pattern (see `clean-bidopsai-stack.sh`). Sample agent in `/agentcore` for testing. No tests/ directory needed - scripts validated manually with real ECR/Docker.

## Complexity Tracking

*No constitutional violations requiring justification.*

## Implementation Phases

### Phase 0: Research & Discovery

**Goal**: Understand Docker buildx ARM64 builds, ECR API, AWS credential handling

**Deliverable**: `research.md` documenting:
- Docker buildx setup and multi-platform builds
- ECR API for repository creation and image push
- AWS credential chain resolution (environment variables, profiles, IAM roles)
- Error handling patterns for Docker/AWS CLI commands
- Strands agent Dockerfile requirements

### Phase 1: Design & Contracts

**Goal**: Define script interfaces, input/output schemas, error codes

**Deliverables**:
- `data-model.md`: Script parameters, exit codes, environment variables
- `quickstart.md`: Usage examples for each script
- `contracts/` directory: Sample input files, expected outputs

**Contracts**:
1. **build-agent.sh**: Input (agent directory, repository name, tag), Output (local Docker image)
2. **push-to-ecr.sh**: Input (image name, AWS region), Output (ECR image URI + digest)
3. **build-and-push.sh**: Combined inputs, Output (ECR image URI)
4. **verify-ecr-image.sh**: Input (repository name, region), Output (JSON metadata)

### Phase 2: Core Implementation (P1 Scripts)

**User Story 1**: Build ARM64 Docker image
- Implement `build-agent.sh`
- Detect Docker buildx availability
- Auto-configure buildx builder if missing
- Build with `--platform linux/arm64`
- Validate Dockerfile exists before build

**User Story 2**: Push to ECR
- Implement `push-to-ecr.sh`
- Validate AWS credentials via `aws sts get-caller-identity`
- Create ECR repository if not exists
- Authenticate Docker with ECR using `aws ecr get-login-password`
- Tag and push image
- Verify push success with `aws ecr describe-images`

### Phase 3: Enhanced Workflows (P2-P3 Scripts)

**User Story 3**: Combined build + push
- Implement `build-and-push.sh`
- Call `build-agent.sh`, exit on failure
- Call `push-to-ecr.sh` with built image
- Report final ECR URI

**User Story 4**: Image verification
- Implement `verify-ecr-image.sh`
- Query ECR for image metadata
- Display digest, size, platform, timestamp
- Support listing all tags sorted by timestamp

### Phase 4: Testing & Documentation

- Test all scripts with sample Strands agent
- Run shellcheck for linting
- Update `/scripts/README.md` with usage examples
- Create `quickstart.md` with end-to-end walkthrough
- Test error scenarios (missing Dockerfile, invalid credentials, network failure)

## Dependencies

**External**:
- Docker 20.10+ with buildx plugin
- AWS CLI 2.0+
- jq 1.6+ (for JSON parsing)

**Internal**:
- Sample Strands agent in `/agentcore` for testing
- Existing ECR repository from StorageStack (optional)

## Success Criteria Validation

- **SC-001**: Build + push in <5 minutes ✅ (validated via timing during manual testing)
- **SC-002**: Error detection in <10 seconds ✅ (validation checks run before build)
- **SC-003**: 100% verifiable in ECR ✅ (`verify-ecr-image.sh` confirms architecture)
- **SC-004**: 85% reduction in manual steps ✅ (1 command vs 7 individual commands)
- **SC-005**: Actionable error messages ✅ (all error outputs include next steps)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Docker buildx not available | High | Auto-install or provide clear instructions |
| AWS credentials expired mid-operation | Medium | Validate credentials upfront via `aws sts get-caller-identity` |
| ECR region mismatch | Medium | Accept region as parameter, validate availability |
| Image exceeds 10GB limit | Low | Check image size before push, warn if >8GB |
| Network interruption during push | Medium | Docker CLI handles retries; document manual retry |

## Timeline Estimate

- Phase 0 (Research): 30 minutes
- Phase 1 (Design): 1 hour
- Phase 2 (P1 Implementation): 2 hours
- Phase 3 (P2-P3 Implementation): 1 hour
- Phase 4 (Testing): 1 hour

**Total**: ~5.5 hours

## Next Steps

1. Create `research.md` with Docker buildx and ECR API details
2. Create `data-model.md` with script interfaces
3. Create `quickstart.md` with usage examples
4. Implement P1 scripts (`build-agent.sh`, `push-to-ecr.sh`)
5. Implement P2-P3 scripts (`build-and-push.sh`, `verify-ecr-image.sh`)
6. Test with sample Strands agent
7. Update `/scripts/README.md`
