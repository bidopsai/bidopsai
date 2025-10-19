#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { BidOpsAICognitoStack } from '../lib/cognito-stack';
import { S3SourceBucketStack } from '../lib/s3-source-bucket-stack';
import { ECRStack } from '../lib/ecr-stack';
import { ConfigStack } from '../lib/config-stack';
import { IAMStack } from '../lib/iam-stack';
// import { AgentCoreBuildPipelineStack } from '../lib/agentcore-build-pipeline-stack';
import { AgentCoreRuntimeStack } from '../lib/agentcore-runtime-stack';
import { BedrockDataAutomationStack } from '../lib/bedrock-data-automation-stack';
import { ObservabilityStack } from '../lib/observability-stack';

const app = new cdk.App();

// Get environment from context or default to 'dev'
const environment = app.node.tryGetContext('environment') || 'dev';

// Get AWS account and region from environment
const account = process.env.CDK_DEFAULT_ACCOUNT || process.env.AWS_ACCOUNT_ID;
const region = process.env.CDK_DEFAULT_REGION || process.env.AWS_REGION || 'us-east-1';

// Get image URIs from context (passed by deployment script)
const workflowImageUri = app.node.tryGetContext('workflowImageUri');
const aiAssistantImageUri = app.node.tryGetContext('aiAssistantImageUri');

// Stack configuration
const stackEnv = {
  account,
  region,
};

const commonTags = {
  Environment: environment,
  Project: 'BidOpsAI',
  ManagedBy: 'CDK',
};

// Deploy Cognito Stack
const cognitoStack = new BidOpsAICognitoStack(app, `BidOpsAI-Cognito-${environment}`, {
  env: stackEnv,
  description: `BidOps.AI Cognito User Pool Stack for ${environment}`,
  tags: commonTags,
});

// Deploy S3 Source Bucket Stack
const s3Stack = new S3SourceBucketStack(app, `BidOpsAI-S3SourceBucket-${environment}`, {
  env: stackEnv,
  description: `BidOps.AI S3 Source Bucket Stack for ${environment}`,
  tags: commonTags,
});

// Deploy ECR Stack for Docker images
const ecrStack = new ECRStack(app, `BidOpsAI-ECR-${environment}`, {
  env: stackEnv,
  description: `BidOps.AI ECR Repositories Stack for ${environment}`,
  tags: commonTags,
});

// Deploy Configuration Stack (SSM & Secrets Manager)
const configStack = new ConfigStack(app, `BidOpsAI-Config-${environment}`, {
  env: stackEnv,
  description: `BidOps.AI Configuration Stack (SSM & Secrets) for ${environment}`,
  tags: commonTags,
});

// Deploy IAM Stack
const iamStack = new IAMStack(app, `BidOpsAI-IAM-${environment}`, {
  env: stackEnv,
  description: `BidOps.AI IAM Roles and Policies Stack for ${environment}`,
  tags: commonTags,
});

// Grant config access to IAM roles
configStack.grantParameterReadAccess(iamStack.workflowAgentRole);
configStack.grantParameterReadAccess(iamStack.aiAssistantAgentRole);
configStack.grantSecretsReadAccess(iamStack.workflowAgentRole);
configStack.grantSecretsReadAccess(iamStack.aiAssistantAgentRole);

// TODO: Re-enable when AWS SDK supports Bedrock Data Automation commands
// Deploy Bedrock Data Automation Stack
// const dataAutomationStack = new BedrockDataAutomationStack(app, `BidOpsAI-DataAutomation-${environment}`, {
//   env: stackEnv,
//   description: `BidOps.AI Bedrock Data Automation Stack for ${environment}`,
//   tags: commonTags,
//   environment,
//   sourceBucket: s3Stack.projectDocumentsBucket,
// });

// Grant data automation access to workflow agent
// dataAutomationStack.grantProcessedDocsReadAccess(iamStack.workflowAgentRole);
// dataAutomationStack.grantDataAutomationAccess(iamStack.workflowAgentRole);

// Add dependencies
iamStack.addDependency(configStack);
iamStack.addDependency(s3Stack);
iamStack.addDependency(ecrStack);
// dataAutomationStack.addDependency(s3Stack);

// Deploy AgentCore Build Pipeline Stack (DISABLED - using manual deployment)
// We're using Podman-based deployment scripts instead of CodeBuild
// See: infra/cdk/scripts/build-and-push.sh
// const buildPipelineStack = new AgentCoreBuildPipelineStack(app, `BidOpsAI-AgentCore-Build-${environment}`, {
//   env: stackEnv,
//   description: `BidOps.AI AgentCore Build Pipeline Stack for ${environment}`,
//   tags: commonTags,
//   environment,
//   workflowAgentRepository: ecrStack.workflowAgentRepository,
//   aiAssistantAgentRepository: ecrStack.aiAssistantAgentRepository,
//   workflowAgentVersion: workflowVersion,
//   aiAssistantAgentVersion: aiAssistantVersion,
// });
// buildPipelineStack.addDependency(ecrStack);

// Deploy AgentCore Runtime Stack
// Images are built and pushed to ECR manually using: infra/cdk/scripts/build-and-push.sh
// Image URIs are passed via CDK context: -c workflowImageUri=... -c aiAssistantImageUri=...
// Supports deploying individual agents (workflow OR ai-assistant) or both
if (workflowImageUri || aiAssistantImageUri) {
  const agentCoreStack = new AgentCoreRuntimeStack(app, `BidOpsAI-AgentCore-${environment}`, {
    env: stackEnv,
    description: `BidOps.AI AgentCore Runtime Stack for ${environment}`,
    tags: commonTags,
    environment,
    workflowAgentRole: iamStack.workflowAgentRole,
    aiAssistantAgentRole: iamStack.aiAssistantAgentRole,
    workflowAgentImageUri: workflowImageUri,
    aiAssistantAgentImageUri: aiAssistantImageUri,
    enableDetailedMonitoring: environment === 'prod' || environment === 'staging',
  });

  // AgentCore runtime depends on IAM and ECR (images must exist in ECR before deployment)
  agentCoreStack.addDependency(iamStack);
  agentCoreStack.addDependency(ecrStack);
}

// Deploy Observability Stack (CloudWatch, X-Ray, LangFuse integration)
// Note: Roles are NOT passed to avoid circular dependency
// IAM stack already contains all necessary log group permissions
const observabilityStack = new ObservabilityStack(app, `BidOpsAI-Observability-${environment}`, {
  env: stackEnv,
  description: `BidOps.AI Observability Stack (CloudWatch, X-Ray) for ${environment}`,
  tags: commonTags,
  environment,
});

// Observability no longer depends on IAM (permissions are self-contained in IAM stack)

app.synth();