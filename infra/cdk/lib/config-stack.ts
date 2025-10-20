import * as cdk from 'aws-cdk-lib';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

/**
 * BidOps.AI Configuration Stack
 * 
 * Creates and configures:
 * - SSM Parameter Store for agent configurations (non-sensitive)
 * - Secrets Manager for sensitive credentials
 * 
 * Features:
 * - Environment-specific parameter paths
 * - Automatic secret rotation policies
 * - Encryption at rest for secrets
 * - IAM policies for agent runtime access
 */
export class ConfigStack extends cdk.Stack {
  public readonly agentConfigParameterPath: string;
  public databaseSecretArn: string;
  public awsCredentialsSecretArn: string;
  public slackSecretArn: string;
  public langfuseSecretArn: string;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Get environment from stack name or default to 'dev'
    const environment = this.node.tryGetContext('environment') || 'dev';

    // Define base parameter path
    this.agentConfigParameterPath = `/bidopsai/${environment}/agents`;

    // Create SSM Parameters for Agent Configurations
    this.createAgentConfigParameters(environment);

    // Create Secrets Manager secrets
    this.createSecrets(environment);

    // Stack outputs
    this.createOutputs(environment);

    // Add tags
    cdk.Tags.of(this).add('Environment', environment);
    cdk.Tags.of(this).add('Project', 'BidOpsAI');
    cdk.Tags.of(this).add('ManagedBy', 'CDK');
    cdk.Tags.of(this).add('Component', 'Configuration');
  }

  /**
   * Create SSM Parameters for agent configurations
   */
  private createAgentConfigParameters(environment: string): void {
    // Workflow Supervisor Configuration
    new ssm.StringParameter(this, 'WorkflowSupervisorConfig', {
      parameterName: `${this.agentConfigParameterPath}/workflow-supervisor/config`,
      description: 'Workflow Supervisor Agent configuration',
      stringValue: JSON.stringify({
        enabled: true,
        max_tokens: 4096,
        temperature: 0.7,
        model_name: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
        timeout_seconds: 300,
        retry_attempts: 3,
        port: 8000,
      }),
      tier: ssm.ParameterTier.STANDARD,
    });

    // AI Assistant Supervisor Configuration
    new ssm.StringParameter(this, 'AIAssistantSupervisorConfig', {
      parameterName: `${this.agentConfigParameterPath}/ai-assistant-supervisor/config`,
      description: 'AI Assistant Supervisor Agent configuration',
      stringValue: JSON.stringify({
        enabled: true,
        max_tokens: 4096,
        temperature: 0.7,
        model_name: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
        timeout_seconds: 180,
        retry_attempts: 3,
        port: 8001,
      }),
      tier: ssm.ParameterTier.STANDARD,
    });

    // Parser Agent Configuration
    new ssm.StringParameter(this, 'ParserAgentConfig', {
      parameterName: `${this.agentConfigParameterPath}/parser/config`,
      description: 'Parser Agent configuration',
      stringValue: JSON.stringify({
        enabled: true,
        max_tokens: 8192,
        temperature: 0.3,
        model_name: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      }),
      tier: ssm.ParameterTier.STANDARD,
    });

    // Analysis Agent Configuration
    new ssm.StringParameter(this, 'AnalysisAgentConfig', {
      parameterName: `${this.agentConfigParameterPath}/analysis/config`,
      description: 'Analysis Agent configuration',
      stringValue: JSON.stringify({
        enabled: true,
        max_tokens: 8192,
        temperature: 0.5,
        model_name: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      }),
      tier: ssm.ParameterTier.STANDARD,
    });

    // Knowledge Agent Configuration
    new ssm.StringParameter(this, 'KnowledgeAgentConfig', {
      parameterName: `${this.agentConfigParameterPath}/knowledge/config`,
      description: 'Knowledge Agent configuration',
      stringValue: JSON.stringify({
        enabled: true,
        max_tokens: 4096,
        temperature: 0.5,
        model_name: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      }),
      tier: ssm.ParameterTier.STANDARD,
    });

    // Content Agent Configuration
    new ssm.StringParameter(this, 'ContentAgentConfig', {
      parameterName: `${this.agentConfigParameterPath}/content/config`,
      description: 'Content Agent configuration',
      stringValue: JSON.stringify({
        enabled: true,
        max_tokens: 16384,
        temperature: 0.7,
        model_name: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      }),
      tier: ssm.ParameterTier.STANDARD,
    });

    // Compliance Agent Configuration
    new ssm.StringParameter(this, 'ComplianceAgentConfig', {
      parameterName: `${this.agentConfigParameterPath}/compliance/config`,
      description: 'Compliance Agent configuration',
      stringValue: JSON.stringify({
        enabled: true,
        max_tokens: 8192,
        temperature: 0.3,
        model_name: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      }),
      tier: ssm.ParameterTier.STANDARD,
    });

    // QA Agent Configuration
    new ssm.StringParameter(this, 'QAAgentConfig', {
      parameterName: `${this.agentConfigParameterPath}/qa/config`,
      description: 'QA Agent configuration',
      stringValue: JSON.stringify({
        enabled: true,
        max_tokens: 8192,
        temperature: 0.3,
        model_name: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      }),
      tier: ssm.ParameterTier.STANDARD,
    });

    // Comms Agent Configuration
    new ssm.StringParameter(this, 'CommsAgentConfig', {
      parameterName: `${this.agentConfigParameterPath}/comms/config`,
      description: 'Communications Agent configuration',
      stringValue: JSON.stringify({
        enabled: true,
        max_tokens: 4096,
        temperature: 0.7,
        model_name: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      }),
      tier: ssm.ParameterTier.STANDARD,
    });

    // Submission Agent Configuration
    new ssm.StringParameter(this, 'SubmissionAgentConfig', {
      parameterName: `${this.agentConfigParameterPath}/submission/config`,
      description: 'Submission Agent configuration',
      stringValue: JSON.stringify({
        enabled: true,
        max_tokens: 4096,
        temperature: 0.5,
        model_name: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      }),
      tier: ssm.ParameterTier.STANDARD,
    });

    // AgentCore Memory Configuration
    new ssm.StringParameter(this, 'AgentCoreMemoryConfig', {
      parameterName: `${this.agentConfigParameterPath}/memory/config`,
      description: 'AgentCore Memory system configuration',
      stringValue: JSON.stringify({
        workflow_memory_ttl_hours: 72,
        project_memory_ttl_days: 90,
        user_preference_memory_ttl_days: 365,
        agent_learning_memory_ttl_days: 180,
        session_memory_ttl_hours: 1,
      }),
      tier: ssm.ParameterTier.STANDARD,
    });

    // Observability Configuration
    new ssm.StringParameter(this, 'ObservabilityConfig', {
      parameterName: `${this.agentConfigParameterPath}/observability/config`,
      description: 'Observability and monitoring configuration',
      stringValue: JSON.stringify({
        langfuse_enabled: true,
        cloudwatch_logs_enabled: true,
        xray_tracing_enabled: true,
        log_level: environment === 'prod' ? 'INFO' : 'DEBUG',
        metrics_namespace: 'BidOpsAI/AgentCore',
      }),
      tier: ssm.ParameterTier.STANDARD,
    });
  }

  /**
   * Create Secrets Manager secrets for sensitive data
   */
  private createSecrets(environment: string): void {
    // Database credentials secret
    const databaseSecret = new secretsmanager.Secret(this, 'DatabaseSecret', {
      secretName: `bidopsai/${environment}/database/credentials`,
      description: 'PostgreSQL database credentials for AgentCore',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({
          username: 'bidopsai_agent',
          host: '<RDS_ENDPOINT>',
          port: 5432,
          dbname: 'bidopsai',
        }),
        generateStringKey: 'password',
        passwordLength: 32,
        excludePunctuation: true,
      },
    });
    this.databaseSecretArn = databaseSecret.secretArn;

    // AWS Credentials secret (for services not using IAM roles)
    const awsCredentialsSecret = new secretsmanager.Secret(this, 'AWSCredentialsSecret', {
      secretName: `bidopsai/${environment}/aws/credentials`,
      description: 'AWS access credentials for external integrations',
      secretObjectValue: {
        aws_access_key_id: cdk.SecretValue.unsafePlainText('<PLACEHOLDER>'),
        aws_secret_access_key: cdk.SecretValue.unsafePlainText('<PLACEHOLDER>'),
        aws_region: cdk.SecretValue.unsafePlainText(this.region),
      },
    });
    this.awsCredentialsSecretArn = awsCredentialsSecret.secretArn;

    // Slack integration secret
    const slackSecret = new secretsmanager.Secret(this, 'SlackSecret', {
      secretName: `bidopsai/${environment}/integrations/slack`,
      description: 'Slack integration credentials for notifications',
      secretObjectValue: {
        bot_token: cdk.SecretValue.unsafePlainText('<PLACEHOLDER>'),
        signing_secret: cdk.SecretValue.unsafePlainText('<PLACEHOLDER>'),
        app_token: cdk.SecretValue.unsafePlainText('<PLACEHOLDER>'),
        workspace_id: cdk.SecretValue.unsafePlainText('<PLACEHOLDER>'),
      },
    });
    this.slackSecretArn = slackSecret.secretArn;

    // LangFuse API credentials secret
    const langfuseSecret = new secretsmanager.Secret(this, 'LangFuseSecret', {
      secretName: `bidopsai/${environment}/observability/langfuse`,
      description: 'LangFuse API credentials for observability',
      secretObjectValue: {
        public_key: cdk.SecretValue.unsafePlainText('<PLACEHOLDER>'),
        secret_key: cdk.SecretValue.unsafePlainText('<PLACEHOLDER>'),
        host: cdk.SecretValue.unsafePlainText('https://cloud.langfuse.com'),
      },
    });
    this.langfuseSecretArn = langfuseSecret.secretArn;

    // Add automatic rotation for database secret (if needed)
    if (environment === 'prod') {
      // Note: Automatic rotation requires Lambda function setup
      // This is a placeholder for future implementation
    }
  }

  /**
   * Create CloudFormation outputs
   */
  private createOutputs(environment: string): void {
    // SSM Parameter Path
    new cdk.CfnOutput(this, 'AgentConfigParameterPath', {
      value: this.agentConfigParameterPath,
      description: 'Base SSM parameter path for agent configurations',
      exportName: `BidOpsAI-AgentConfigPath-${environment}`,
    });

    // Database Secret ARN
    new cdk.CfnOutput(this, 'DatabaseSecretArn', {
      value: this.databaseSecretArn,
      description: 'Secrets Manager ARN for database credentials',
      exportName: `BidOpsAI-DatabaseSecretArn-${environment}`,
    });

    // AWS Credentials Secret ARN
    new cdk.CfnOutput(this, 'AWSCredentialsSecretArn', {
      value: this.awsCredentialsSecretArn,
      description: 'Secrets Manager ARN for AWS credentials',
      exportName: `BidOpsAI-AWSCredentialsSecretArn-${environment}`,
    });

    // Slack Secret ARN
    new cdk.CfnOutput(this, 'SlackSecretArn', {
      value: this.slackSecretArn,
      description: 'Secrets Manager ARN for Slack integration',
      exportName: `BidOpsAI-SlackSecretArn-${environment}`,
    });

    // LangFuse Secret ARN
    new cdk.CfnOutput(this, 'LangFuseSecretArn', {
      value: this.langfuseSecretArn,
      description: 'Secrets Manager ARN for LangFuse credentials',
      exportName: `BidOpsAI-LangFuseSecretArn-${environment}`,
    });
  }

  /**
   * Grant read access to SSM parameters for a given role
   */
  public grantParameterReadAccess(role: iam.IRole): void {
    role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'ssm:GetParameter',
          'ssm:GetParameters',
          'ssm:GetParametersByPath',
        ],
        resources: [
          `arn:aws:ssm:${this.region}:${this.account}:parameter${this.agentConfigParameterPath}/*`,
        ],
      })
    );
  }

  /**
   * Grant read access to secrets for a given role
   */
  public grantSecretsReadAccess(role: iam.IRole): void {
    role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'secretsmanager:GetSecretValue',
          'secretsmanager:DescribeSecret',
        ],
        resources: [
          this.databaseSecretArn,
          this.awsCredentialsSecretArn,
          this.slackSecretArn,
          this.langfuseSecretArn,
        ],
      })
    );
  }
}