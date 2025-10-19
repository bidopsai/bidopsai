#!/bin/bash

###############################################################################
# Build and Push Container Images to ECR
#
# This script builds container images for AgentCore agents and pushes them to ECR.
# It uses semantic versioning from environment variables and Podman for containerization.
#
# Usage:
#   ./build-and-push.sh [environment] [agent_type] [--profile PROFILE]
#
# Arguments:
#   environment: dev, staging, or prod (default: dev)
#   agent_type: workflow or ai-assistant (required)
#   --profile: AWS CLI profile to use (optional)
#
# Environment Variables (required):
#   APP_VERSION_WORKFLOW: Semantic version for workflow agent (e.g., 1.0.0)
#   APP_VERSION_AI_ASSISTANT: Semantic version for AI assistant (e.g., 1.0.0)
#   AWS_ACCOUNT_ID: AWS account ID
#   AWS_REGION: AWS region (default: us-east-1)
#
# Prerequisites:
#   - Podman installed and running
#   - AWS CLI configured
#   - ECR repositories created (run deploy-infra.sh first)
#   - Environment variables set in .env or exported
###############################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${1:-dev}"
AGENT_TYPE="${2}"
AWS_REGION="${AWS_REGION:-ap-southeast-2}"
# Preserve AWS_PROFILE from environment, don't overwrite it
# AWS_PROFILE can be set via environment variable or --profile flag

# Validate agent type is provided
if [ -z "${AGENT_TYPE}" ]; then
    echo -e "${RED}ERROR: Agent type is required${NC}"
    echo "Usage: ./build-and-push.sh [environment] [agent_type]"
    echo "Agent types: workflow, ai-assistant"
    exit 1
fi

# Parse optional arguments
shift 2 2>/dev/null || shift $(($# < 2 ? $# : 2))
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Load environment variables from .env if it exists
if [ -f "${PROJECT_ROOT}/.env" ]; then
    echo -e "${GREEN}Loading environment variables from .env${NC}"
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
fi

# Validate environment
if [[ ! "${ENVIRONMENT}" =~ ^(dev|staging|prod)$ ]]; then
    echo -e "${RED}ERROR: Invalid environment '${ENVIRONMENT}'${NC}"
    echo "Valid values: dev, staging, prod"
    exit 1
fi

# Validate agent type
if [[ ! "${AGENT_TYPE}" =~ ^(workflow|ai-assistant)$ ]]; then
    echo -e "${RED}ERROR: Invalid agent type '${AGENT_TYPE}'${NC}"
    echo "Valid values: workflow, ai-assistant"
    exit 1
fi

# Get AWS account ID if not set
if [ -z "${AWS_ACCOUNT_ID}" ]; then
    echo -e "${YELLOW}AWS_ACCOUNT_ID not set, retrieving from AWS CLI...${NC}"
    # AWS_PROFILE is already set as environment variable, AWS CLI will use it automatically
    export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>&1)
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to retrieve AWS account ID${NC}"
        echo "${AWS_ACCOUNT_ID}"
        exit 1
    fi
    echo -e "${GREEN}AWS Account ID: ${AWS_ACCOUNT_ID}${NC}"
fi

# Get AWS region if not set
if [ -z "${AWS_REGION}" ]; then
    export AWS_REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
    echo -e "${GREEN}AWS Region: ${AWS_REGION}${NC}"
fi

if [ "${AGENT_TYPE}" == "workflow" ] && [ -z "${APP_VERSION_WORKFLOW}" ]; then
    echo -e "${RED}ERROR: APP_VERSION_WORKFLOW not set${NC}"
    echo "Please set APP_VERSION_WORKFLOW environment variable or add it to .env file"
    exit 1
fi

if [ "${AGENT_TYPE}" == "ai-assistant" ] && [ -z "${APP_VERSION_AI_ASSISTANT}" ]; then
    echo -e "${RED}ERROR: APP_VERSION_AI_ASSISTANT not set${NC}"
    echo "Please set APP_VERSION_AI_ASSISTANT environment variable or add it to .env file"
    exit 1
fi

# ECR repository names
WORKFLOW_REPO="bidopsai-workflow-agent-${ENVIRONMENT}"
AI_ASSISTANT_REPO="bidopsai-ai-assistant-agent-${ENVIRONMENT}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Build and Push Container Image${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Environment: ${ENVIRONMENT}"
echo "Agent Type: ${AGENT_TYPE}"
echo "Region: ${AWS_REGION}"
echo "Account: ${AWS_ACCOUNT_ID}"
echo ""

# Check Podman is available
if ! command -v podman &> /dev/null; then
    echo -e "${RED}ERROR: Podman is not installed${NC}"
    echo "Please install Podman: https://podman.io/getting-started/installation"
    exit 1
fi

# ECR login with Podman
echo -e "${YELLOW}Logging in to ECR...${NC}"
# AWS_PROFILE is already set as environment variable, AWS CLI will use it automatically
aws ecr get-login-password --region ${AWS_REGION} | \
    podman login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: ECR login failed${NC}"
    exit 1
fi

echo -e "${GREEN}ECR login successful${NC}"
echo ""

###############################################################################
# Function to build and push Docker image
###############################################################################
build_and_push() {
    local AGENT_NAME=$1
    local REPO_NAME=$2
    local VERSION=$3
    local DOCKERFILE_PATH=$4
    local BUILD_CONTEXT=$5
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Building ${AGENT_NAME}${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    # ECR repository URI
    local REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}"
    
    # Tags
    local VERSION_TAG="${REPO_URI}:v${VERSION}"
    local LATEST_TAG="${REPO_URI}:latest"
    local ENV_TAG="${REPO_URI}:${ENVIRONMENT}"
    
    echo "Repository: ${REPO_NAME}"
    echo "Version: ${VERSION}"
    echo "Tags: v${VERSION}, latest, ${ENVIRONMENT}"
    echo "Dockerfile: ${DOCKERFILE_PATH}"
    echo ""
    
    # Build arguments
    local BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
    
    # Build the container image with Podman
    echo -e "${YELLOW}Building container image with Podman...${NC}"
    echo ""
    echo "Dockerfile: ${DOCKERFILE_PATH}"
    echo "Build Context: ${BUILD_CONTEXT}"
    echo ""
    
    # Temporarily disable exit on error to see build output
    set +e
    
    echo "⏳ Building image (this may take a few minutes)..."
    echo ""
    echo "Note: Podman on macOS doesn't show build output in real-time."
    echo "The build is running in the background. Please wait..."
    echo ""
    
    # Start time
    START_TIME=$(date +%s)
    
    # Run podman build in background and monitor
    # Note: AWS Bedrock AgentCore requires ARM64 architecture
    podman build \
        --platform linux/arm64 \
        --build-arg VERSION=${VERSION} \
        --build-arg BUILD_DATE=${BUILD_DATE} \
        -t ${VERSION_TAG} \
        -t ${LATEST_TAG} \
        -t ${ENV_TAG} \
        -f ${DOCKERFILE_PATH} \
        ${BUILD_CONTEXT} &
    
    PODMAN_PID=$!
    
    # Show progress while build is running
    while kill -0 $PODMAN_PID 2>/dev/null; do
        ELAPSED=$(($(date +%s) - START_TIME))
        printf "\r⏳ Building... (${ELAPSED}s elapsed)"
        sleep 2
    done
    
    # Wait for podman to finish and get exit code
    wait $PODMAN_PID
    BUILD_EXIT_CODE=$?
    
    # Clear the progress line
    printf "\r"
    
    # Calculate total time
    END_TIME=$(date +%s)
    TOTAL_TIME=$((END_TIME - START_TIME))
    echo "Build completed in ${TOTAL_TIME} seconds"
    echo ""
    
    # Re-enable exit on error
    set -e
    
    if [ $BUILD_EXIT_CODE -ne 0 ]; then
        echo ""
        echo -e "${RED}ERROR: Podman build failed for ${AGENT_NAME}${NC}"
        echo -e "${RED}Exit code: $BUILD_EXIT_CODE${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ Build successful${NC}"
    echo ""
    
    # Push all tags
    echo -e "${YELLOW}Pushing images to ECR...${NC}"
    echo "  → Pushing ${VERSION_TAG}"
    podman push ${VERSION_TAG}
    
    echo "  → Pushing ${LATEST_TAG}"
    podman push ${LATEST_TAG}
    
    echo "  → Pushing ${ENV_TAG}"
    podman push ${ENV_TAG}
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Podman push failed for ${AGENT_NAME}${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ Push successful${NC}"
    echo ""
    echo -e "${GREEN}Image URIs:${NC}"
    echo "  ${VERSION_TAG}"
    echo "  ${LATEST_TAG}"
    echo "  ${ENV_TAG}"
    echo ""
    
    return 0
}

###############################################################################
# Build and push image for specified agent
###############################################################################

BUILD_FAILED=0

if [ "${AGENT_TYPE}" == "workflow" ]; then
    if ! build_and_push \
        "Workflow Supervisor Agent" \
        "${WORKFLOW_REPO}" \
        "${APP_VERSION_WORKFLOW}" \
        "${PROJECT_ROOT}/infra/docker/agents-core/workflow/Dockerfile" \
        "${PROJECT_ROOT}/agents-core"; then
        BUILD_FAILED=1
    fi
elif [ "${AGENT_TYPE}" == "ai-assistant" ]; then
    if ! build_and_push \
        "AI Assistant Supervisor Agent" \
        "${AI_ASSISTANT_REPO}" \
        "${APP_VERSION_AI_ASSISTANT}" \
        "${PROJECT_ROOT}/infra/docker/agents-core/ai_assistant/Dockerfile" \
        "${PROJECT_ROOT}/agents-core"; then
        BUILD_FAILED=1
    fi
fi

###############################################################################
# Summary
###############################################################################
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build and Push Summary${NC}"
echo -e "${GREEN}========================================${NC}"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${AWS_REGION}"
echo "Account: ${AWS_ACCOUNT_ID}"

if [ "${AGENT_TYPE}" == "workflow" ]; then
    echo ""
    echo "Workflow Agent:"
    echo "  Version: ${APP_VERSION_WORKFLOW}"
    echo "  Repository: ${WORKFLOW_REPO}"
    echo "  URI: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${WORKFLOW_REPO}:v${APP_VERSION_WORKFLOW}"
elif [ "${AGENT_TYPE}" == "ai-assistant" ]; then
    echo ""
    echo "AI Assistant Agent:"
    echo "  Version: ${APP_VERSION_AI_ASSISTANT}"
    echo "  Repository: ${AI_ASSISTANT_REPO}"
    echo "  URI: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${AI_ASSISTANT_REPO}:v${APP_VERSION_AI_ASSISTANT}"
fi

echo ""

if [ $BUILD_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ Image built and pushed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}Next Step:${NC}"
    echo "Deploy AgentCore runtime with the new image:"
    echo "  ./deploy-agentcore.sh ${ENVIRONMENT} ${AGENT_TYPE}"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Image build failed${NC}"
    exit 1
fi