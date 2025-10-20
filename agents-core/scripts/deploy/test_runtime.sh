#!/bin/bash

# Test AgentCore Runtime
# This script invokes the deployed AgentCore runtime using AWS CLI
# Usage: ./test_runtime.sh [environment] [agent-type] [aws-region] [aws-profile]

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-dev}
AGENT_TYPE=${2:-workflow}
# Get AWS region from parameter or environment or default
if [ -n "$3" ]; then
    AWS_REGION="$3"
elif [ -z "${AWS_REGION}" ]; then
    AWS_REGION="ap-southeast-2"
fi
# Preserve AWS_PROFILE from environment, or use parameter if provided
if [ -n "$4" ]; then
    AWS_PROFILE="$4"
fi
# AWS_PROFILE can be set via environment variable or parameter

OUTPUTS_FILE="../../infra/cdk/cdk-outputs.json"
STACK_NAME="BidOpsAI-AgentCore-${ENVIRONMENT}"

echo -e "${BLUE}🧪 Testing AgentCore Runtime...${NC}"
echo ""
echo "Environment: ${ENVIRONMENT}"
echo "Agent Type: ${AGENT_TYPE}"
echo "Region: ${AWS_REGION}"
echo ""

# Build AWS CLI profile argument
PROFILE_ARG=""
if [ -n "${AWS_PROFILE}" ]; then
    PROFILE_ARG="--profile ${AWS_PROFILE}"
fi

# Function to get stack output using AWS CLI
get_stack_output() {
    local OUTPUT_KEY="$1"
    
    if [ -n "${AWS_PROFILE}" ]; then
        aws cloudformation describe-stacks \
            --stack-name "${STACK_NAME}" \
            --region "${AWS_REGION}" \
            --profile "${AWS_PROFILE}" \
            --query "Stacks[0].Outputs[?OutputKey==\`${OUTPUT_KEY}\`].OutputValue" \
            --output text || echo ""
    else
        aws cloudformation describe-stacks \
            --stack-name "${STACK_NAME}" \
            --region "${AWS_REGION}" \
            --query "Stacks[0].Outputs[?OutputKey==\`${OUTPUT_KEY}\`].OutputValue" \
            --output text || echo ""
    fi
}

# Get runtime information based on agent type
if [ "${AGENT_TYPE}" == "workflow" ]; then
    RUNTIME_ID=$(get_stack_output "WorkflowAgentRuntimeId")
    RUNTIME_ARN=$(get_stack_output "WorkflowAgentRuntimeArn")
    RUNTIME_NAME=$(get_stack_output "WorkflowAgentRuntimeName")
elif [ "${AGENT_TYPE}" == "ai-assistant" ]; then
    RUNTIME_ID=$(get_stack_output "AIAssistantAgentRuntimeId")
    RUNTIME_ARN=$(get_stack_output "AIAssistantAgentRuntimeArn")
    RUNTIME_NAME=$(get_stack_output "AIAssistantAgentRuntimeName")
else
    echo -e "${RED}❌ Error: Invalid agent type '${AGENT_TYPE}'. Use 'workflow' or 'ai-assistant'${NC}"
    exit 1
fi

if [ -z "${RUNTIME_ID}" ] || [ "${RUNTIME_ID}" == "None" ]; then
    # Convert agent type to uppercase for env var name
    if [ "${AGENT_TYPE}" == "workflow" ]; then
        VERSION_VAR="APP_VERSION_WORKFLOW"
    else
        VERSION_VAR="APP_VERSION_AI_ASSISTANT"
    fi
    
    echo -e "${RED}❌ Error: Runtime not found for ${AGENT_TYPE} agent${NC}"
    echo "   Make sure the agent is deployed first:"
    echo "   cd ../../../infra/cdk/scripts"
    echo "   export ${VERSION_VAR}=\"1.0.0\""
    echo "   ./deploy-agentcore.sh ${ENVIRONMENT} ${AGENT_TYPE}"
    exit 1
fi

echo -e "${GREEN}✓ Runtime found:${NC}"
echo "  Runtime ID: ${RUNTIME_ID}"
echo "  Runtime ARN: ${RUNTIME_ARN}"
echo "  Runtime Name: ${RUNTIME_NAME}"
echo ""

# Create test payload based on agent type
# Use snake_case field names to match Pydantic model
if [ "${AGENT_TYPE}" == "workflow" ]; then
    TEST_PAYLOAD=$(cat <<EOF
{
  "project_id": "00000000-0000-0000-0000-000000000001",
  "user_id": "00000000-0000-0000-0000-000000000002",
  "session_id": "test-session-$(date +%s)",
  "start": true,
  "user_input": null,
  "workflow_config": {},
  "metadata": {
    "test_message": "Create a new tender for software development project"
  }
}
EOF
)
else
    TEST_PAYLOAD=$(cat <<EOF
{
  "user_id": "00000000-0000-0000-0000-000000000002",
  "session_id": "test-session-$(date +%s)",
  "message": "What can you help me with?",
  "metadata": {
    "test_request": true
  }
}
EOF
)
fi

echo -e "${YELLOW}📤 Sending test request...${NC}"
echo "${TEST_PAYLOAD}" | jq . 2>/dev/null || echo "${TEST_PAYLOAD}"
echo ""

# Create temporary file for payload
TEMP_PAYLOAD=$(mktemp)
echo "${TEST_PAYLOAD}" > "${TEMP_PAYLOAD}"

# Invoke the runtime using AWS CLI
echo -e "${BLUE}Invoking runtime...${NC}"
RESPONSE_FILE=$(mktemp)

if [ -n "${AWS_PROFILE}" ]; then
    aws bedrock-agentcore invoke-agent-runtime \
        --agent-runtime-arn "${RUNTIME_ARN}" \
        --payload "file://${TEMP_PAYLOAD}" \
        --region "${AWS_REGION}" \
        --profile "${AWS_PROFILE}" \
        "${RESPONSE_FILE}" 2>&1
else
    aws bedrock-agentcore invoke-agent-runtime \
        --agent-runtime-arn "${RUNTIME_ARN}" \
        --payload "file://${TEMP_PAYLOAD}" \
        --region "${AWS_REGION}" \
        "${RESPONSE_FILE}" 2>&1
fi

INVOKE_STATUS=$?

# Clean up temporary payload file
rm -f "${TEMP_PAYLOAD}"

if [ ${INVOKE_STATUS} -eq 0 ]; then
    echo ""
    echo -e "${GREEN}📥 Response:${NC}"
    
    # Check if response file exists and has content
    if [ -f "${RESPONSE_FILE}" ] && [ -s "${RESPONSE_FILE}" ]; then
        cat "${RESPONSE_FILE}" | jq . 2>/dev/null || cat "${RESPONSE_FILE}"
        echo ""
        echo -e "${GREEN}✅ Test completed successfully!${NC}"
    else
        echo -e "${YELLOW}⚠️  Empty response received${NC}"
    fi
    
    # Clean up response file
    rm -f "${RESPONSE_FILE}"
else
    echo ""
    echo -e "${RED}❌ Test failed${NC}"
    if [ -f "${RESPONSE_FILE}" ]; then
        cat "${RESPONSE_FILE}"
        rm -f "${RESPONSE_FILE}"
    fi
    exit 1
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Environment: ${ENVIRONMENT}"
echo "Agent Type: ${AGENT_TYPE}"
echo "Runtime ID: ${RUNTIME_ID}"
echo "Region: ${AWS_REGION}"
echo ""
echo -e "${GREEN}✓ Runtime is healthy and responding${NC}"
echo ""
echo "Next steps:"
echo "  1. Check CloudWatch logs:"
echo "     https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#logsV2:log-groups"
echo ""
echo "  2. Monitor runtime in AWS Console:"
echo "     https://console.aws.amazon.com/bedrock/home?region=${AWS_REGION}#/agentcore/runtimes"