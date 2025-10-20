#!/bin/bash

###############################################################################
# Update AgentCore Runtime with New Images
#
# This script updates the AgentCore runtime deployments with newly pushed
# Docker images from ECR.
#
# Usage:
#   ./update-agentcore-runtime.sh [environment] [agent_type]
#
# Arguments:
#   environment: dev, staging, or prod (default: dev)
#   agent_type: workflow, ai-assistant, or all (default: all)
#
# Prerequisites:
#   - Docker images must be already pushed to ECR
#   - AWS CLI configured with appropriate credentials
#   - AgentCore runtimes must be deployed
#
# Environment Variables:
#   APP_VERSION_WORKFLOW: Version for workflow agent
#   APP_VERSION_AI_ASSISTANT: Version for AI assistant
#   AWS_ACCOUNT_ID: AWS account ID
#   AWS_REGION: AWS region (default: us-east-1)
###############################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${1:-dev}"
AGENT_TYPE="${2:-all}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Load environment variables from .env if it exists
if [ -f "${PROJECT_ROOT}/.env" ]; then
    echo -e "${GREEN}Loading environment variables from .env${NC}"
    export $(grep -v '^#' "${PROJECT_ROOT}/.env" | xargs)
fi

# Validate required environment variables
if [ -z "${AWS_ACCOUNT_ID}" ]; then
    echo -e "${RED}ERROR: AWS_ACCOUNT_ID not set${NC}"
    exit 1
fi

if [ -z "${APP_VERSION_WORKFLOW}" ] && [ "${AGENT_TYPE}" != "ai-assistant" ]; then
    echo -e "${RED}ERROR: APP_VERSION_WORKFLOW not set${NC}"
    exit 1
fi

if [ -z "${APP_VERSION_AI_ASSISTANT}" ] && [ "${AGENT_TYPE}" != "workflow" ]; then
    echo -e "${RED}ERROR: APP_VERSION_AI_ASSISTANT not set${NC}"
    exit 1
fi

# AgentCore runtime names (these should match your deployed runtime names)
WORKFLOW_RUNTIME_NAME="bidopsai-workflow-agent-${ENVIRONMENT}"
AI_ASSISTANT_RUNTIME_NAME="bidopsai-ai-assistant-agent-${ENVIRONMENT}"

# ECR repository URIs
WORKFLOW_REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/bidopsai-workflow-agent-${ENVIRONMENT}"
AI_ASSISTANT_REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/bidopsai-ai-assistant-agent-${ENVIRONMENT}"

###############################################################################
# Function to update AgentCore runtime
###############################################################################
update_runtime() {
    local RUNTIME_NAME=$1
    local IMAGE_URI=$2
    local VERSION=$3
    
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Updating ${RUNTIME_NAME}${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "Runtime: ${RUNTIME_NAME}"
    echo "Image: ${IMAGE_URI}:v${VERSION}"
    echo ""
    
    # Check if runtime exists
    echo -e "${YELLOW}Checking if runtime exists...${NC}"
    if ! aws bedrock describe-agent-runtime \
        --runtime-identifier "${RUNTIME_NAME}" \
        --region ${AWS_REGION} &>/dev/null; then
        echo -e "${RED}ERROR: AgentCore runtime '${RUNTIME_NAME}' not found${NC}"
        echo "Please deploy the runtime first using CDK or AWS Console"
        return 1
    fi
    
    echo -e "${GREEN}Runtime found${NC}"
    echo ""
    
    # Update runtime with new image
    echo -e "${YELLOW}Updating runtime with new image...${NC}"
    aws bedrock update-agent-runtime \
        --runtime-identifier "${RUNTIME_NAME}" \
        --runtime-config "{
            \"containerConfig\": {
                \"image\": \"${IMAGE_URI}:v${VERSION}\"
            }
        }" \
        --region ${AWS_REGION}
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Failed to update runtime${NC}"
        return 1
    fi
    
    echo -e "${GREEN}Runtime updated successfully!${NC}"
    echo ""
    
    # Wait for runtime to be ready
    echo -e "${YELLOW}Waiting for runtime to be ready...${NC}"
    local MAX_ATTEMPTS=30
    local ATTEMPT=0
    
    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        local STATUS=$(aws bedrock describe-agent-runtime \
            --runtime-identifier "${RUNTIME_NAME}" \
            --region ${AWS_REGION} \
            --query 'runtimeStatus' \
            --output text 2>/dev/null)
        
        if [ "${STATUS}" == "AVAILABLE" ]; then
            echo -e "${GREEN}Runtime is ready!${NC}"
            return 0
        elif [ "${STATUS}" == "FAILED" ]; then
            echo -e "${RED}ERROR: Runtime update failed${NC}"
            return 1
        fi
        
        echo -n "."
        sleep 10
        ATTEMPT=$((ATTEMPT + 1))
    done
    
    echo ""
    echo -e "${YELLOW}WARNING: Runtime status check timed out${NC}"
    echo "Please check the runtime status manually in AWS Console"
    return 0
}

###############################################################################
# Update runtimes based on AGENT_TYPE
###############################################################################

FAILED=0

if [ "${AGENT_TYPE}" == "workflow" ] || [ "${AGENT_TYPE}" == "all" ]; then
    if ! update_runtime \
        "${WORKFLOW_RUNTIME_NAME}" \
        "${WORKFLOW_REPO_URI}" \
        "${APP_VERSION_WORKFLOW}"; then
        FAILED=1
    fi
fi

if [ "${AGENT_TYPE}" == "ai-assistant" ] || [ "${AGENT_TYPE}" == "all" ]; then
    if ! update_runtime \
        "${AI_ASSISTANT_RUNTIME_NAME}" \
        "${AI_ASSISTANT_REPO_URI}" \
        "${APP_VERSION_AI_ASSISTANT}"; then
        FAILED=1
    fi
fi

###############################################################################
# Summary
###############################################################################
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Update Summary${NC}"
echo -e "${GREEN}========================================${NC}"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${AWS_REGION}"

if [ "${AGENT_TYPE}" == "workflow" ] || [ "${AGENT_TYPE}" == "all" ]; then
    echo ""
    echo "Workflow Agent Runtime:"
    echo "  Name: ${WORKFLOW_RUNTIME_NAME}"
    echo "  Version: ${APP_VERSION_WORKFLOW}"
fi

if [ "${AGENT_TYPE}" == "ai-assistant" ] || [ "${AGENT_TYPE}" == "all" ]; then
    echo ""
    echo "AI Assistant Agent Runtime:"
    echo "  Name: ${AI_ASSISTANT_RUNTIME_NAME}"
    echo "  Version: ${APP_VERSION_AI_ASSISTANT}"
fi

echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All runtimes updated successfully!${NC}"
    exit 0
else
    echo -e "${RED}Some runtime updates failed${NC}"
    exit 1
fi