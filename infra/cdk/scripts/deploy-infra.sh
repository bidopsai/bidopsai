#!/bin/bash

###############################################################################
# Deploy Infrastructure Stacks for AgentCore
#
# This script deploys the required CDK stacks for AgentCore deployment:
# 1. ECR repositories for Docker images
# 2. IAM roles for AgentCore runtimes
#
# Usage:
#   ./deploy-infra.sh [environment] [--profile PROFILE]
#
# Arguments:
#   environment: dev, staging, or prod (default: dev)
#   --profile: AWS CLI profile to use (optional)
#
# Prerequisites:
#   - AWS CDK installed (npm install -g aws-cdk)
#   - AWS CLI configured
#   - Node.js dependencies installed in infra/cdk (npm install)
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
# Preserve AWS_PROFILE from environment, don't overwrite it
# AWS_PROFILE can be set via environment variable or --profile flag

# Parse optional arguments
shift || true
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
CDK_DIR="${SCRIPT_DIR}/.."

# Validate environment
if [[ ! "${ENVIRONMENT}" =~ ^(dev|staging|prod)$ ]]; then
    echo -e "${RED}ERROR: Invalid environment '${ENVIRONMENT}'${NC}"
    echo "Valid values: dev, staging, prod"
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
    # AWS_PROFILE is already set as environment variable, AWS CLI will use it automatically
    export AWS_REGION=$(aws configure get region 2>/dev/null || echo "ap-southeast-2")
    echo -e "${GREEN}AWS Region: ${AWS_REGION}${NC}"
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AgentCore Infrastructure Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${AWS_REGION}"
echo "Account: ${AWS_ACCOUNT_ID}"
echo "CDK Directory: ${CDK_DIR}"
echo ""

# Change to CDK directory
cd "${CDK_DIR}"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing CDK dependencies...${NC}"
    npm install
    echo -e "${GREEN}Dependencies installed${NC}"
    echo ""
fi

# Bootstrap CDK (if needed)
echo -e "${YELLOW}Checking CDK bootstrap...${NC}"
if ! cdk bootstrap -c environment=${ENVIRONMENT} ${AWS_PROFILE} 2>&1 | grep -q "already bootstrapped"; then
    echo -e "${GREEN}CDK bootstrapped successfully${NC}"
else
    echo -e "${GREEN}CDK already bootstrapped${NC}"
fi
echo ""

# Deploy ECR Stack
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deploying ECR Stack${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Stack: BidOpsAI-ECR-${ENVIRONMENT}"
echo ""

cdk deploy "BidOpsAI-ECR-${ENVIRONMENT}" \
    -c environment=${ENVIRONMENT} \
    --require-approval never \
    ${AWS_PROFILE}

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: ECR stack deployment failed${NC}"
    exit 1
fi

echo -e "${GREEN}ECR stack deployed successfully${NC}"
echo ""

# Deploy IAM Stack
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deploying IAM Stack${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Stack: BidOpsAI-IAM-${ENVIRONMENT}"
echo ""

cdk deploy "BidOpsAI-IAM-${ENVIRONMENT}" \
    -c environment=${ENVIRONMENT} \
    --require-approval never \
    ${AWS_PROFILE}

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: IAM stack deployment failed${NC}"
    exit 1
fi

echo -e "${GREEN}IAM stack deployed successfully${NC}"
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Infrastructure Deployment Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo "Environment: ${ENVIRONMENT}"
echo ""
echo "Deployed Stacks:"
echo "  ✓ BidOpsAI-ECR-${ENVIRONMENT}"
echo "  ✓ BidOpsAI-IAM-${ENVIRONMENT}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Build and push Docker images:"
echo "   ./scripts/build-and-push.sh ${ENVIRONMENT}"
echo ""
echo "2. Deploy AgentCore runtimes:"
echo "   ./scripts/deploy-agentcore.sh ${ENVIRONMENT}"
echo ""