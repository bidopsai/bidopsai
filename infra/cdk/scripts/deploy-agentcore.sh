#!/bin/bash

###############################################################################
# Deploy or Update AgentCore Runtimes
#
# This script deploys or updates AgentCore runtime stacks with the latest
# Docker images from ECR.
#
# Usage:
#   ./deploy-agentcore.sh [environment] [agent_type] [--profile PROFILE]
#
# Arguments:
#   environment: dev, staging, or prod (default: dev)
#   agent_type: workflow or ai-assistant (required)
#   --profile: AWS CLI profile to use (optional)
#
# Environment Variables (required):
#   APP_VERSION_WORKFLOW: Version for workflow agent
#   APP_VERSION_AI_ASSISTANT: Version for AI assistant
#   AWS_ACCOUNT_ID: AWS account ID
#   AWS_REGION: AWS region (default: us-east-1)
#
# Prerequisites:
#   - Infrastructure stacks deployed (run deploy-infra.sh)
#   - Docker images pushed to ECR (run build-and-push.sh)
#   - AWS CLI configured
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
# Get AWS region from AWS CLI config if not set
if [ -z "${AWS_REGION}" ]; then
    AWS_REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
fi
# Preserve AWS_PROFILE from environment, don't overwrite it
# AWS_PROFILE can be set via environment variable or --profile flag

# Validate agent type is provided
if [ -z "${AGENT_TYPE}" ]; then
    echo -e "${RED}ERROR: Agent type is required${NC}"
    echo "Usage: ./deploy-agentcore.sh [environment] [agent_type]"
    echo "Agent types: workflow, ai-assistant"
    exit 1
fi

# Parse optional arguments
shift 2 2>/dev/null || shift $(($# < 2 ? $# : 2))
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            export AWS_PROFILE="$2"
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
CDK_DIR="${SCRIPT_DIR}/.."

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

# Get AWS region if not set (redundant check after initial setup, but kept for safety)
if [ -z "${AWS_REGION}" ]; then
    export AWS_REGION=$(aws configure get region 2>/dev/null || echo "ap-southeast-2")
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

# ECR repository URIs
WORKFLOW_REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/bidopsai-workflow-agent-${ENVIRONMENT}"
AI_ASSISTANT_REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/bidopsai-ai-assistant-agent-${ENVIRONMENT}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AgentCore Runtime Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Environment: ${ENVIRONMENT}"
echo "Agent Type: ${AGENT_TYPE}"
echo "Region: ${AWS_REGION}"
echo "CDK Directory: ${CDK_DIR}"
echo ""

# Change to CDK directory
cd "${CDK_DIR}"

# Verify images exist in ECR
echo -e "${YELLOW}Verifying Docker images in ECR...${NC}"

verify_image() {
    local REPO_NAME=$1
    local VERSION=$2
    
    local PROFILE_ARG=""
    if [ -n "${AWS_PROFILE}" ]; then
        PROFILE_ARG="--profile ${AWS_PROFILE}"
    fi
    
    if aws ecr describe-images \
        --repository-name ${REPO_NAME} \
        --image-ids imageTag=v${VERSION} \
        --region ${AWS_REGION} \
        ${PROFILE_ARG} >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Found ${REPO_NAME}:v${VERSION}${NC}"
        return 0
    else
        echo -e "${RED}✗ Image not found: ${REPO_NAME}:v${VERSION}${NC}"
        return 1
    fi
}

IMAGES_EXIST=0

if [ "${AGENT_TYPE}" == "workflow" ]; then
    if ! verify_image "bidopsai-workflow-agent-${ENVIRONMENT}" "${APP_VERSION_WORKFLOW}"; then
        IMAGES_EXIST=1
    fi
elif [ "${AGENT_TYPE}" == "ai-assistant" ]; then
    if ! verify_image "bidopsai-ai-assistant-agent-${ENVIRONMENT}" "${APP_VERSION_AI_ASSISTANT}"; then
        IMAGES_EXIST=1
    fi
fi

if [ $IMAGES_EXIST -ne 0 ]; then
    echo ""
    echo -e "${RED}ERROR: Required container image not found in ECR${NC}"
    echo "Please run build-and-push.sh first:"
    echo "  ./build-and-push.sh ${ENVIRONMENT} ${AGENT_TYPE}"
    exit 1
fi

echo -e "${GREEN}All required images verified in ECR${NC}"
echo ""

# Build CDK context parameters (only pass image URI for specified agent type)
CDK_CONTEXT="-c environment=${ENVIRONMENT}"
if [ "${AGENT_TYPE}" == "workflow" ]; then
    CDK_CONTEXT="${CDK_CONTEXT} -c workflowImageUri=${WORKFLOW_REPO_URI}:v${APP_VERSION_WORKFLOW}"
elif [ "${AGENT_TYPE}" == "ai-assistant" ]; then
    CDK_CONTEXT="${CDK_CONTEXT} -c aiAssistantImageUri=${AI_ASSISTANT_REPO_URI}:v${APP_VERSION_AI_ASSISTANT}"
fi

# Deploy AgentCore Runtime Stack
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deploying AgentCore Runtime Stack${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Stack: BidOpsAI-AgentCore-${ENVIRONMENT}"
echo ""

if [ "${AGENT_TYPE}" == "workflow" ]; then
    echo "Workflow Agent Image:"
    echo "  ${WORKFLOW_REPO_URI}:v${APP_VERSION_WORKFLOW}"
elif [ "${AGENT_TYPE}" == "ai-assistant" ]; then
    echo "AI Assistant Agent Image:"
    echo "  ${AI_ASSISTANT_REPO_URI}:v${APP_VERSION_AI_ASSISTANT}"
fi

echo ""
echo -e "${YELLOW}Starting CDK deployment...${NC}"
echo ""

PROFILE_FLAG=""
if [ -n "${AWS_PROFILE}" ]; then
    PROFILE_FLAG="--profile ${AWS_PROFILE}"
fi

cdk deploy "BidOpsAI-AgentCore-${ENVIRONMENT}" \
    ${CDK_CONTEXT} \
    --require-approval never \
    --outputs-file "${CDK_DIR}/cdk-outputs.json" \
    ${PROFILE_FLAG}

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: AgentCore stack deployment failed${NC}"
    exit 1
fi

# Make outputs file readable
if [ -f "${CDK_DIR}/cdk-outputs.json" ]; then
    chmod 644 "${CDK_DIR}/cdk-outputs.json"
fi

echo ""
echo -e "${GREEN}AgentCore stack deployed successfully${NC}"
echo ""

# Get runtime information
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Runtime Information${NC}"
echo -e "${BLUE}========================================${NC}"

# Extract outputs using AWS CLI
get_stack_output() {
    local OUTPUT_KEY=$1
    local PROFILE_ARG=""
    if [ -n "${AWS_PROFILE}" ]; then
        PROFILE_ARG="--profile ${AWS_PROFILE}"
    fi
    
    aws cloudformation describe-stacks \
        --stack-name "BidOpsAI-AgentCore-${ENVIRONMENT}" \
        --region ${AWS_REGION} \
        --query "Stacks[0].Outputs[?OutputKey=='${OUTPUT_KEY}'].OutputValue" \
        --output text \
        ${PROFILE_ARG} 2>/dev/null || echo "N/A"
}

if [ "${AGENT_TYPE}" == "workflow" ]; then
    echo ""
    echo "Workflow Agent Runtime:"
    echo "  Runtime ID: $(get_stack_output 'WorkflowAgentRuntimeId')"
    echo "  Runtime ARN: $(get_stack_output 'WorkflowAgentRuntimeArn')"
    echo "  Runtime Name: $(get_stack_output 'WorkflowAgentRuntimeName')"
    echo "  Image Version: ${APP_VERSION_WORKFLOW}"
elif [ "${AGENT_TYPE}" == "ai-assistant" ]; then
    echo ""
    echo "AI Assistant Agent Runtime:"
    echo "  Runtime ID: $(get_stack_output 'AIAssistantAgentRuntimeId')"
    echo "  Runtime ARN: $(get_stack_output 'AIAssistantAgentRuntimeArn')"
    echo "  Runtime Name: $(get_stack_output 'AIAssistantAgentRuntimeName')"
    echo "  Image Version: ${APP_VERSION_AI_ASSISTANT}"
fi

echo ""
echo "Endpoint: $(get_stack_output 'EndpointName')"
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${AWS_REGION}"
echo ""
echo -e "${GREEN}✓ AgentCore runtimes deployed successfully!${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Test the runtime deployment:"
echo "   See agents-core/scripts/deploy/test_runtime.sh"
echo ""
echo "2. Monitor the runtimes in AWS Console:"
echo "   https://console.aws.amazon.com/bedrock/home?region=${AWS_REGION}#/agentcore/runtimes"
echo ""
echo "3. View CloudWatch logs:"
echo "   https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#logsV2:log-groups/log-group/\$252Faws\$252Fbedrock-agentcore\$252Fruntimes"
echo ""