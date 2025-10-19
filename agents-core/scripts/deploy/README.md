# AgentCore Runtime Testing

This directory contains scripts for testing deployed AgentCore runtimes.

## test_runtime.sh

Test a deployed AgentCore runtime by sending a sample request.

### Usage

```bash
./test_runtime.sh [environment] [agent-type] [aws-region] [aws-profile]
```

### Parameters

- `environment` (optional): Deployment environment (default: `dev`)
- `agent-type` (optional): Agent to test - `workflow` or `ai-assistant` (default: `workflow`)
- `aws-region` (optional): AWS region (default: `ap-southeast-2`)
- `aws-profile` (optional): AWS CLI profile name

### Examples

```bash
# Test workflow agent in dev environment (default)
./test_runtime.sh

# Test workflow agent explicitly
./test_runtime.sh dev workflow

# Test AI assistant agent
./test_runtime.sh dev ai-assistant

# Test with specific AWS profile
./test_runtime.sh dev workflow ap-southeast-2 my-profile

# Test in production
./test_runtime.sh prod workflow
```

### What It Does

1. Retrieves runtime information from CloudFormation stack outputs
2. Creates a test payload appropriate for the agent type
3. Invokes the runtime using AWS Bedrock AgentCore API
4. Displays the response
5. Provides links to CloudWatch logs and AWS Console

### Requirements

- AWS CLI installed and configured
- `jq` for JSON parsing (optional, for prettier output)
- Deployed AgentCore runtime for the specified agent type
- Appropriate AWS permissions to invoke Bedrock AgentCore runtimes

### Test Payloads

**Workflow Agent:**
```json
{
  "sessionId": "test-session-<timestamp>",
  "message": "Create a new tender for software development project",
  "userId": "test-user",
  "projectId": "test-project-123"
}
```

**AI Assistant Agent:**
```json
{
  "sessionId": "test-session-<timestamp>",
  "message": "What can you help me with?",
  "userId": "test-user"
}
```

### Troubleshooting

**Error: Runtime not found**
```bash
❌ Error: Runtime not found for workflow agent
   Make sure the agent is deployed first
```
**Solution:** Deploy the agent first:
```bash
cd ../../../infra/cdk/scripts
export APP_VERSION_WORKFLOW="1.0.0"
./deploy-agentcore.sh dev workflow
```

**Error: Invalid agent type**
```bash
❌ Error: Invalid agent type 'xyz'. Use 'workflow' or 'ai-assistant'
```
**Solution:** Use valid agent type: `workflow` or `ai-assistant`

**Error: Access denied**
```bash
❌ Test failed
An error occurred (AccessDeniedException)...
```
**Solution:** Ensure your AWS credentials have permission to invoke Bedrock AgentCore runtimes:
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock-agentcore:InvokeRuntime"
  ],
  "Resource": "arn:aws:bedrock-agentcore:*:*:runtime/*"
}
```

### Output

Successful test output:
```
🧪 Testing AgentCore Runtime...

Environment: dev
Agent Type: workflow
Region: ap-southeast-2

✓ Runtime found:
  Runtime ID: bidopsai_workflow_agent_dev-XhMsNQEw6d
  Runtime ARN: arn:aws:bedrock-agentcore:ap-southeast-2:123456789012:runtime/bidopsai_workflow_agent_dev-XhMsNQEw6d
  Runtime Name: bidopsai_workflow_agent_dev

📤 Sending test request...
{
  "sessionId": "test-session-1234567890",
  "message": "Create a new tender for software development project",
  "userId": "test-user",
  "projectId": "test-project-123"
}

Invoking runtime...

📥 Response:
{
  "response": "...",
  "sessionId": "test-session-1234567890"
}

✅ Test completed successfully!

========================================
Test Summary
========================================
Environment: dev
Agent Type: workflow
Runtime ID: bidopsai_workflow_agent_dev-XhMsNQEw6d
Region: ap-southeast-2

✓ Runtime is healthy and responding

Next steps:
  1. Check CloudWatch logs:
     https://console.aws.amazon.com/cloudwatch/home?region=ap-southeast-2#logsV2:log-groups

  2. Monitor runtime in AWS Console:
     https://console.aws.amazon.com/bedrock/home?region=ap-southeast-2#/agentcore/runtimes
```

## Monitoring

### CloudWatch Logs

AgentCore runtimes log to CloudWatch. Access logs via:

1. **AWS Console:**
   - Navigate to CloudWatch → Log groups
   - Look for `/aws/bedrock-agentcore/runtimes`

2. **AWS CLI:**
   ```bash
   aws logs tail /aws/bedrock-agentcore/runtimes \
     --follow \
     --region ap-southeast-2
   ```

### Runtime Status

Check runtime status using AWS CLI:

```bash
# List all runtimes
aws bedrock-agentcore list-runtimes --region ap-southeast-2

# Get specific runtime details
aws bedrock-agentcore get-runtime \
  --runtime-id bidopsai_workflow_agent_dev-XhMsNQEw6d \
  --region ap-southeast-2
```

### Metrics

Monitor runtime metrics in CloudWatch:
- Invocation count
- Error rate
- Duration
- Throttles

## Integration Testing

For more comprehensive testing, integrate with your application's test suite:

```bash
# Example: Integration test
RUNTIME_ID=$(aws cloudformation describe-stacks \
  --stack-name BidOpsAI-AgentCore-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`WorkflowAgentRuntimeId`].OutputValue' \
  --output text)

# Invoke with custom payload
aws bedrock-agentcore invoke-runtime \
  --runtime-id "${RUNTIME_ID}" \
  --endpoint-name DEFAULT \
  --body file://test-payload.json \
  --region ap-southeast-2 \
  response.json
```

## Continuous Testing

Set up automated testing:

```bash
#!/bin/bash
# ci-test-runtime.sh

set -e

ENVIRONMENT=${1:-dev}
AGENT_TYPE=${2:-workflow}

echo "Testing ${AGENT_TYPE} agent in ${ENVIRONMENT}..."

# Run test
./test_runtime.sh "${ENVIRONMENT}" "${AGENT_TYPE}"

# Check exit code
if [ $? -eq 0 ]; then
  echo "✅ Runtime test passed"
  exit 0
else
  echo "❌ Runtime test failed"
  exit 1
fi
```

## Related Documentation

- [Deployment Scripts](../../../infra/cdk/scripts/README.md)
- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/agentcore/)