import * as cdk from 'aws-cdk-lib';
import * as agentcore from 'aws-cdk-lib/aws-bedrock';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

/**
 * AgentCore Identity Stack
 * 
 * Integrates AWS Bedrock AgentCore Identity with existing Cognito User Pool
 * to provide secure authentication, authorization, and credential management
 * for AI agents and automated workloads.
 * 
 * Features:
 * - Integration with existing Cognito User Pool
 * - Identity validation for agent invocations
 * - Credential management for agent-to-service communication
 * - Audit trails for identity-related operations
 * 
 * References:
 * - https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html
 * - https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/03-AgentCore-identity
 */
export interface AgentCoreIdentityStackProps extends cdk.StackProps {
  /**
   * Environment name (development, staging, production)
   */
  environment: string;

  /**
   * Cognito User Pool ID from existing stack
   */
  cognitoUserPoolId: string;

  /**
   * Cognito User Pool ARN from existing stack
   */
  cognitoUserPoolArn: string;

  /**
   * Cognito App Client ID for web application
   */
  cognitoAppClientId: string;

  /**
   * Workflow AgentCore Runtime ID
   */
  workflowRuntimeId?: string;

  /**
   * AI Assistant AgentCore Runtime ID
   */
  aiAssistantRuntimeId?: string;
}

export class AgentCoreIdentityStack extends cdk.Stack {
  public readonly identityServiceRole: iam.Role;
  public readonly agentExecutionRole: iam.Role;
  public readonly identityConfigParameter: ssm.StringParameter;

  constructor(scope: Construct, id: string, props: AgentCoreIdentityStackProps) {
    super(scope, id, props);

    // Import existing Cognito User Pool
    const userPool = cognito.UserPool.fromUserPoolId(
      this,
      'ImportedUserPool',
      props.cognitoUserPoolId
    );

    // Create IAM role for AgentCore Identity Service
    this.identityServiceRole = new iam.Role(this, 'IdentityServiceRole', {
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Role for AgentCore Identity Service to manage agent identities',
      roleName: `bidopsai-agentcore-identity-${props.environment}`,
    });

    // Grant Identity Service permissions to Cognito User Pool
    this.identityServiceRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'cognito-idp:AdminGetUser',
          'cognito-idp:AdminListGroupsForUser',
          'cognito-idp:GetUser',
          'cognito-idp:ListUsers',
          'cognito-idp:DescribeUserPool',
          'cognito-idp:DescribeUserPoolClient',
        ],
        resources: [props.cognitoUserPoolArn],
      })
    );

    // Grant Identity Service permissions to manage credentials
    this.identityServiceRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'secretsmanager:GetSecretValue',
          'secretsmanager:DescribeSecret',
          'secretsmanager:CreateSecret',
          'secretsmanager:UpdateSecret',
          'secretsmanager:PutSecretValue',
        ],
        resources: [
          `arn:aws:secretsmanager:${this.region}:${this.account}:secret:bidopsai/agentcore/*`,
        ],
      })
    );

    // Grant Identity Service permissions to SSM Parameter Store
    this.identityServiceRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'ssm:GetParameter',
          'ssm:GetParameters',
          'ssm:GetParametersByPath',
        ],
        resources: [
          `arn:aws:ssm:${this.region}:${this.account}:parameter/bidopsai/${props.environment}/*`,
        ],
      })
    );

    // Create IAM role for Agent Execution with Identity
    this.agentExecutionRole = new iam.Role(this, 'AgentExecutionRole', {
      assumedBy: new iam.CompositePrincipal(
        new iam.ServicePrincipal('bedrock.amazonaws.com'),
        new iam.ServicePrincipal('lambda.amazonaws.com')
      ),
      description: 'Execution role for agents with identity validation',
      roleName: `bidopsai-agent-execution-${props.environment}`,
    });

    // Grant Agent Execution role permissions to invoke Bedrock models
    this.agentExecutionRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          `arn:aws:bedrock:${this.region}::foundation-model/*`,
        ],
      })
    );

    // Grant Agent Execution role permissions to access RDS database
    this.agentExecutionRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'rds-data:ExecuteStatement',
          'rds-data:BatchExecuteStatement',
          'rds-data:BeginTransaction',
          'rds-data:CommitTransaction',
          'rds-data:RollbackTransaction',
        ],
        resources: [
          `arn:aws:rds:${this.region}:${this.account}:cluster:bidopsai-*`,
        ],
      })
    );

    // Grant Agent Execution role permissions to access S3
    this.agentExecutionRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          's3:GetObject',
          's3:PutObject',
          's3:ListBucket',
          's3:DeleteObject',
        ],
        resources: [
          `arn:aws:s3:::bidopsai-${props.environment}-*`,
          `arn:aws:s3:::bidopsai-${props.environment}-*/*`,
        ],
      })
    );

    // Grant Agent Execution role permissions to CloudWatch Logs
    this.agentExecutionRole.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchLogsFullAccess')
    );

    // Create AgentCore Identity Configuration
    const identityConfig = {
      version: '1.0',
      environment: props.environment,
      cognito: {
        userPoolId: props.cognitoUserPoolId,
        userPoolArn: props.cognitoUserPoolArn,
        appClientId: props.cognitoAppClientId,
        region: this.region,
      },
      identityService: {
        roleArn: this.identityServiceRole.roleArn,
        enabled: true,
        validateIdentity: true,
        auditEnabled: true,
      },
      agentExecution: {
        roleArn: this.agentExecutionRole.roleArn,
        allowAssumeRole: true,
        sessionDuration: 3600, // 1 hour
      },
      runtimes: {
        workflow: props.workflowRuntimeId || '',
        aiAssistant: props.aiAssistantRuntimeId || '',
      },
      security: {
        requireMFA: false, // Enable in production
        maxSessionDuration: 43200, // 12 hours
        allowedOrigins: [
          'http://localhost:3000', // Development
          'https://*.bidopsai.com', // Production
        ],
      },
    };

    // Store Identity Configuration in SSM Parameter Store
    this.identityConfigParameter = new ssm.StringParameter(
      this,
      'IdentityConfigParameter',
      {
        parameterName: `/bidopsai/${props.environment}/agentcore/identity-config`,
        description: 'AgentCore Identity configuration',
        stringValue: JSON.stringify(identityConfig, null, 2),
        tier: ssm.ParameterTier.STANDARD,
      }
    );

    // Create SSM parameters for role ARNs
    new ssm.StringParameter(this, 'IdentityServiceRoleArnParameter', {
      parameterName: `/bidopsai/${props.environment}/agentcore/identity-service-role-arn`,
      description: 'ARN of the AgentCore Identity Service Role',
      stringValue: this.identityServiceRole.roleArn,
      tier: ssm.ParameterTier.STANDARD,
    });

    new ssm.StringParameter(this, 'AgentExecutionRoleArnParameter', {
      parameterName: `/bidopsai/${props.environment}/agentcore/agent-execution-role-arn`,
      description: 'ARN of the Agent Execution Role',
      stringValue: this.agentExecutionRole.roleArn,
      tier: ssm.ParameterTier.STANDARD,
    });

    // CloudFormation Outputs
    new cdk.CfnOutput(this, 'IdentityServiceRoleArn', {
      value: this.identityServiceRole.roleArn,
      description: 'ARN of the AgentCore Identity Service Role',
      exportName: `bidopsai-${props.environment}-identity-service-role-arn`,
    });

    new cdk.CfnOutput(this, 'AgentExecutionRoleArn', {
      value: this.agentExecutionRole.roleArn,
      description: 'ARN of the Agent Execution Role',
      exportName: `bidopsai-${props.environment}-agent-execution-role-arn`,
    });

    new cdk.CfnOutput(this, 'IdentityConfigParameterName', {
      value: this.identityConfigParameter.parameterName,
      description: 'SSM Parameter name for Identity Configuration',
      exportName: `bidopsai-${props.environment}-identity-config-param`,
    });

    new cdk.CfnOutput(this, 'CognitoUserPoolId', {
      value: props.cognitoUserPoolId,
      description: 'Cognito User Pool ID',
      exportName: `bidopsai-${props.environment}-cognito-user-pool-id`,
    });

    // Add tags
    cdk.Tags.of(this).add('Project', 'BidOpsAI');
    cdk.Tags.of(this).add('Environment', props.environment);
    cdk.Tags.of(this).add('Component', 'AgentCore-Identity');
    cdk.Tags.of(this).add('ManagedBy', 'CDK');
  }
}