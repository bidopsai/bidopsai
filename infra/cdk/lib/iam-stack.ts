import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

/**
 * BidOps.AI IAM Stack
 * 
 * Creates and configures IAM roles and policies for:
 * - AgentCore Runtime execution roles
 * - Service-to-service communication
 * - AWS resource access (S3, RDS, Bedrock, etc.)
 * 
 * Features:
 * - Least privilege access principles
 * - Separate roles for workflow and AI assistant agents
 * - Bedrock model access
 * - S3 bucket access for documents and artifacts
 * - RDS database access
 * - CloudWatch logging and X-Ray tracing
 */
export class IAMStack extends cdk.Stack {
  public readonly workflowAgentRole: iam.Role;
  public readonly aiAssistantAgentRole: iam.Role;
  public readonly agentCoreExecutionRole: iam.Role;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Get environment from stack name or default to 'dev'
    const environment = this.node.tryGetContext('environment') || 'dev';

    // Create execution role for AgentCore runtime (used by both agents)
    this.agentCoreExecutionRole = this.createAgentCoreExecutionRole(environment);

    // Create specific role for Workflow Supervisor Agent
    this.workflowAgentRole = this.createWorkflowAgentRole(environment);

    // Create specific role for AI Assistant Supervisor Agent
    this.aiAssistantAgentRole = this.createAIAssistantAgentRole(environment);

    // Stack outputs
    this.createOutputs(environment);

    // Add tags
    cdk.Tags.of(this).add('Environment', environment);
    cdk.Tags.of(this).add('Project', 'BidOpsAI');
    cdk.Tags.of(this).add('ManagedBy', 'CDK');
    cdk.Tags.of(this).add('Component', 'IAM');
  }

  /**
   * Create base execution role for AgentCore runtime
   */
  private createAgentCoreExecutionRole(environment: string): iam.Role {
    const role = new iam.Role(this, 'AgentCoreExecutionRole', {
      roleName: `BidOpsAI-AgentCore-Execution-${environment}`,
      description: 'Base execution role for AgentCore runtime',
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchLogsFullAccess'),
        iam.ManagedPolicy.fromAwsManagedPolicyName('AWSXRayDaemonWriteAccess'),
      ],
    });

    // Add basic AgentCore permissions
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'AgentCoreBasicPermissions',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
          'bedrock:Retrieve',
          'bedrock:RetrieveAndGenerate',
        ],
        resources: ['*'],
      })
    );

    return role;
  }

  /**
   * Create role for Workflow Supervisor Agent
   */
  private createWorkflowAgentRole(environment: string): iam.Role {
    const role = new iam.Role(this, 'WorkflowAgentRole', {
      roleName: `BidOpsAI-WorkflowAgent-${environment}`,
      description: 'IAM role for Workflow Supervisor Agent - AgentCore Runtime',
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
    });

    // ECR Image Access (required by AgentCore to pull container images)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'ECRImageAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'ecr:BatchGetImage',
          'ecr:GetDownloadUrlForLayer',
        ],
        resources: [`arn:aws:ecr:${this.region}:${this.account}:repository/*`],
      })
    );

    // ECR Token Access (required by AgentCore)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'ECRTokenAccess',
        effect: iam.Effect.ALLOW,
        actions: ['ecr:GetAuthorizationToken'],
        resources: ['*'],
      })
    );

    // Bedrock model access (including Converse API and Inference Profiles)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'BedrockModelInvocation',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
          'bedrock:Converse',
          'bedrock:ConverseStream',
          'bedrock:ListFoundationModels',
          'bedrock:GetFoundationModel',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/*`,
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
          `arn:aws:bedrock:${this.region}:${this.account}:*`,
        ],
      })
    );

    // Bedrock Knowledge Base access
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'BedrockKnowledgeBaseAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:Retrieve',
          'bedrock:RetrieveAndGenerate',
          'bedrock:ListKnowledgeBases',
          'bedrock:GetKnowledgeBase',
        ],
        resources: [`arn:aws:bedrock:${this.region}:${this.account}:knowledge-base/*`],
      })
    );

    // Bedrock Data Automation access
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'BedrockDataAutomationAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:StartIngestionJob',
          'bedrock:GetIngestionJob',
          'bedrock:ListIngestionJobs',
        ],
        resources: [`arn:aws:bedrock:${this.region}:${this.account}:data-automation-project/*`],
      })
    );

    // S3 access for project documents and artifacts
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'S3BucketAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          's3:GetObject',
          's3:PutObject',
          's3:DeleteObject',
          's3:ListBucket',
          's3:GetObjectVersion',
        ],
        resources: [
          `arn:aws:s3:::bidopsai-project-documents-${environment}-${this.account}`,
          `arn:aws:s3:::bidopsai-project-documents-${environment}-${this.account}/*`,
          `arn:aws:s3:::bidopsai-artifacts-${environment}-${this.account}`,
          `arn:aws:s3:::bidopsai-artifacts-${environment}-${this.account}/*`,
        ],
      })
    );

    // RDS database access (via IAM authentication)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'RDSAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'rds-db:connect',
        ],
        resources: [
          `arn:aws:rds-db:${this.region}:${this.account}:dbuser:*/bidopsai_agent`,
        ],
      })
    );

    // CloudWatch Logs (required by AgentCore runtime)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'CloudWatchLogsDescribe',
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:DescribeLogStreams',
          'logs:CreateLogGroup',
        ],
        resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*`],
      })
    );

    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'CloudWatchLogsDescribeAll',
        effect: iam.Effect.ALLOW,
        actions: ['logs:DescribeLogGroups'],
        resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:*`],
      })
    );

    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'CloudWatchLogsWrite',
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:CreateLogStream',
          'logs:PutLogEvents',
        ],
        resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*`],
      })
    );

    // X-Ray tracing (required by AgentCore runtime)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'XRayTracing',
        effect: iam.Effect.ALLOW,
        actions: [
          'xray:PutTraceSegments',
          'xray:PutTelemetryRecords',
          'xray:GetSamplingRules',
          'xray:GetSamplingTargets',
        ],
        resources: ['*'],
      })
    );

    // CloudWatch Metrics (required by AgentCore runtime)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'CloudWatchMetrics',
        effect: iam.Effect.ALLOW,
        actions: ['cloudwatch:PutMetricData'],
        resources: ['*'],
        conditions: {
          StringEquals: {
            'cloudwatch:namespace': 'bedrock-agentcore',
          },
        },
      })
    );

    // AgentCore Identity - Get Workload Access Token
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'GetAgentAccessToken',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock-agentcore:GetWorkloadAccessToken',
          'bedrock-agentcore:GetWorkloadAccessTokenForJWT',
          'bedrock-agentcore:GetWorkloadAccessTokenForUserId',
        ],
        resources: [
          `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
          `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/bidopsai_workflow_agent_${environment}-*`,
        ],
      })
    );

    // SSM Parameter Store access
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'SSMParameterAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'ssm:GetParameter',
          'ssm:GetParameters',
          'ssm:GetParametersByPath',
        ],
        resources: [
          `arn:aws:ssm:${this.region}:${this.account}:parameter/bidopsai/${environment}/agents/*`,
        ],
      })
    );

    // Secrets Manager access
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'SecretsManagerAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'secretsmanager:GetSecretValue',
          'secretsmanager:DescribeSecret',
        ],
        resources: [
          `arn:aws:secretsmanager:${this.region}:${this.account}:secret:bidopsai/${environment}/*`,
        ],
      })
    );

    // AgentCore Memory access
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'AgentCoreMemoryAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:CreateAgentMemory',
          'bedrock:GetAgentMemory',
          'bedrock:UpdateAgentMemory',
          'bedrock:DeleteAgentMemory',
          'bedrock:ListAgentMemories',
        ],
        resources: [
          `arn:aws:bedrock:${this.region}:${this.account}:agent-memory/*`,
        ],
      })
    );

    return role;
  }

  /**
   * Create role for AI Assistant Supervisor Agent
   */
  private createAIAssistantAgentRole(environment: string): iam.Role {
    const role = new iam.Role(this, 'AIAssistantAgentRole', {
      roleName: `BidOpsAI-AIAssistantAgent-${environment}`,
      description: 'IAM role for AI Assistant Supervisor Agent - AgentCore Runtime',
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
    });

    // ECR Image Access (required by AgentCore to pull container images)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'ECRImageAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'ecr:BatchGetImage',
          'ecr:GetDownloadUrlForLayer',
        ],
        resources: [`arn:aws:ecr:${this.region}:${this.account}:repository/*`],
      })
    );

    // ECR Token Access (required by AgentCore)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'ECRTokenAccess',
        effect: iam.Effect.ALLOW,
        actions: ['ecr:GetAuthorizationToken'],
        resources: ['*'],
      })
    );

    // Bedrock model access (including Converse API and Inference Profiles)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'BedrockModelInvocation',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
          'bedrock:Converse',
          'bedrock:ConverseStream',
          'bedrock:ListFoundationModels',
          'bedrock:GetFoundationModel',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/*`,
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
          `arn:aws:bedrock:${this.region}:${this.account}:*`,
        ],
      })
    );

    // Bedrock Knowledge Base access (read-only for AI Assistant)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'BedrockKnowledgeBaseAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:Retrieve',
          'bedrock:RetrieveAndGenerate',
          'bedrock:ListKnowledgeBases',
          'bedrock:GetKnowledgeBase',
        ],
        resources: [`arn:aws:bedrock:${this.region}:${this.account}:knowledge-base/*`],
      })
    );

    // S3 access (read-only for AI Assistant)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'S3BucketReadAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          's3:GetObject',
          's3:ListBucket',
          's3:GetObjectVersion',
        ],
        resources: [
          `arn:aws:s3:::bidopsai-project-documents-${environment}-${this.account}`,
          `arn:aws:s3:::bidopsai-project-documents-${environment}-${this.account}/*`,
          `arn:aws:s3:::bidopsai-artifacts-${environment}-${this.account}`,
          `arn:aws:s3:::bidopsai-artifacts-${environment}-${this.account}/*`,
        ],
      })
    );

    // RDS database access (read-only)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'RDSReadAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'rds-db:connect',
        ],
        resources: [
          `arn:aws:rds-db:${this.region}:${this.account}:dbuser:*/bidopsai_agent`,
        ],
      })
    );

    // CloudWatch Logs (required by AgentCore runtime)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'CloudWatchLogsDescribe',
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:DescribeLogStreams',
          'logs:CreateLogGroup',
        ],
        resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*`],
      })
    );

    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'CloudWatchLogsDescribeAll',
        effect: iam.Effect.ALLOW,
        actions: ['logs:DescribeLogGroups'],
        resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:*`],
      })
    );

    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'CloudWatchLogsWrite',
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:CreateLogStream',
          'logs:PutLogEvents',
        ],
        resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*`],
      })
    );

    // X-Ray tracing (required by AgentCore runtime)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'XRayTracing',
        effect: iam.Effect.ALLOW,
        actions: [
          'xray:PutTraceSegments',
          'xray:PutTelemetryRecords',
          'xray:GetSamplingRules',
          'xray:GetSamplingTargets',
        ],
        resources: ['*'],
      })
    );

    // CloudWatch Metrics (required by AgentCore runtime)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'CloudWatchMetrics',
        effect: iam.Effect.ALLOW,
        actions: ['cloudwatch:PutMetricData'],
        resources: ['*'],
        conditions: {
          StringEquals: {
            'cloudwatch:namespace': 'bedrock-agentcore',
          },
        },
      })
    );

    // AgentCore Identity - Get Workload Access Token
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'GetAgentAccessToken',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock-agentcore:GetWorkloadAccessToken',
          'bedrock-agentcore:GetWorkloadAccessTokenForJWT',
          'bedrock-agentcore:GetWorkloadAccessTokenForUserId',
        ],
        resources: [
          `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
          `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/bidopsai_ai_assistant_agent_${environment}-*`,
        ],
      })
    );

    // SSM Parameter Store access
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'SSMParameterAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'ssm:GetParameter',
          'ssm:GetParameters',
          'ssm:GetParametersByPath',
        ],
        resources: [
          `arn:aws:ssm:${this.region}:${this.account}:parameter/bidopsai/${environment}/agents/*`,
        ],
      })
    );

    // Secrets Manager access
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'SecretsManagerAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'secretsmanager:GetSecretValue',
          'secretsmanager:DescribeSecret',
        ],
        resources: [
          `arn:aws:secretsmanager:${this.region}:${this.account}:secret:bidopsai/${environment}/*`,
        ],
      })
    );

    // AgentCore Memory access
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'AgentCoreMemoryAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:GetAgentMemory',
          'bedrock:ListAgentMemories',
        ],
        resources: [
          `arn:aws:bedrock:${this.region}:${this.account}:agent-memory/*`,
        ],
      })
    );

    return role;
  }

  /**
   * Create CloudFormation outputs
   */
  private createOutputs(environment: string): void {
    // AgentCore Execution Role
    new cdk.CfnOutput(this, 'AgentCoreExecutionRoleArn', {
      value: this.agentCoreExecutionRole.roleArn,
      description: 'ARN of AgentCore execution role',
      exportName: `BidOpsAI-AgentCoreExecutionRoleArn-${environment}`,
    });

    new cdk.CfnOutput(this, 'AgentCoreExecutionRoleName', {
      value: this.agentCoreExecutionRole.roleName,
      description: 'Name of AgentCore execution role',
      exportName: `BidOpsAI-AgentCoreExecutionRoleName-${environment}`,
    });

    // Workflow Agent Role
    new cdk.CfnOutput(this, 'WorkflowAgentRoleArn', {
      value: this.workflowAgentRole.roleArn,
      description: 'ARN of Workflow Agent role',
      exportName: `BidOpsAI-WorkflowAgentRoleArn-${environment}`,
    });

    new cdk.CfnOutput(this, 'WorkflowAgentRoleName', {
      value: this.workflowAgentRole.roleName,
      description: 'Name of Workflow Agent role',
      exportName: `BidOpsAI-WorkflowAgentRoleName-${environment}`,
    });

    // AI Assistant Agent Role
    new cdk.CfnOutput(this, 'AIAssistantAgentRoleArn', {
      value: this.aiAssistantAgentRole.roleArn,
      description: 'ARN of AI Assistant Agent role',
      exportName: `BidOpsAI-AIAssistantAgentRoleArn-${environment}`,
    });

    new cdk.CfnOutput(this, 'AIAssistantAgentRoleName', {
      value: this.aiAssistantAgentRole.roleName,
      description: 'Name of AI Assistant Agent role',
      exportName: `BidOpsAI-AIAssistantAgentRoleName-${environment}`,
    });
  }
}