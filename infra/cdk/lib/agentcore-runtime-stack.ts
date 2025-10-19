import * as cdk from 'aws-cdk-lib';
import * as bedrockagentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export interface AgentCoreRuntimeStackProps extends cdk.StackProps {
  /**
   * Environment name (dev, staging, prod)
   */
  environment: string;

  /**
   * IAM execution role for the workflow agent
   */
  workflowAgentRole: iam.IRole;

  /**
   * IAM execution role for the AI assistant agent
   */
  aiAssistantAgentRole: iam.IRole;

  /**
   * ECR image URI for workflow agent (including tag)
   * Optional - only required if deploying workflow agent
   */
  workflowAgentImageUri?: string;

  /**
   * ECR image URI for AI assistant agent (including tag)
   * Optional - only required if deploying AI assistant agent
   */
  aiAssistantAgentImageUri?: string;

  /**
   * Enable detailed monitoring and tracing
   */
  enableDetailedMonitoring?: boolean;
}

/**
 * Stack for deploying AWS Bedrock AgentCore Runtimes
 *
 * This stack creates two AgentCore runtime deployments:
 * 1. Workflow Agent Runtime - Handles bid processing workflows
 * 2. AI Assistant Agent Runtime - Handles conversational AI assistance
 *
 * Uses the native bedrockagentcore.CfnRuntime CDK construct following
 * AWS best practices from the official AgentCore examples.
 */
export class AgentCoreRuntimeStack extends cdk.Stack {
  public readonly workflowRuntimeArn: string;
  public readonly aiAssistantRuntimeArn: string;

  constructor(scope: Construct, id: string, props: AgentCoreRuntimeStackProps) {
    super(scope, id, props);

    const enableMonitoring = props.enableDetailedMonitoring ?? true;
    
    // Determine which agents to deploy based on provided image URIs
    const deployWorkflow = !!props.workflowAgentImageUri;
    const deployAIAssistant = !!props.aiAssistantAgentImageUri;

    // Workflow Agent Runtime (conditional)
    let workflowRuntime: bedrockagentcore.CfnRuntime | undefined;
    if (deployWorkflow) {
      const workflowVersion = props.workflowAgentImageUri!.split(':').pop() || 'latest';
      
      workflowRuntime = new bedrockagentcore.CfnRuntime(this, 'WorkflowAgentRuntime', {
        agentRuntimeName: `bidopsai_workflow_agent_${props.environment}`,
        description: `BidOps AI Workflow Agent Runtime for ${props.environment} environment`,
        roleArn: props.workflowAgentRole.roleArn,

        // Container configuration
        agentRuntimeArtifact: {
          containerConfiguration: {
            containerUri: props.workflowAgentImageUri!,
          },
        },

        // Network configuration - PUBLIC for internet access
        networkConfiguration: {
          networkMode: 'PUBLIC',
        },

        // Protocol configuration
        protocolConfiguration: 'HTTP',

        // Environment variables
        environmentVariables: {
          LOG_LEVEL: enableMonitoring ? 'INFO' : 'DEBUG',
          ENVIRONMENT: props.environment,
          IMAGE_VERSION: workflowVersion,
          AGENT_TYPE: 'workflow',
        },

        tags: {
          Environment: props.environment,
          Application: 'BidOpsAI',
          AgentType: 'WorkflowSupervisor',
          ManagedBy: 'CDK',
        },
      });

      // Store ARN
      this.workflowRuntimeArn = workflowRuntime.attrAgentRuntimeArn;

      // Output runtime information
      new cdk.CfnOutput(this, 'WorkflowAgentRuntimeId', {
        value: workflowRuntime.attrAgentRuntimeId,
        description: 'Workflow Agent Runtime ID',
        exportName: `BidOpsAI-WorkflowRuntimeId-${props.environment}`,
      });

      new cdk.CfnOutput(this, 'WorkflowAgentRuntimeArn', {
        value: workflowRuntime.attrAgentRuntimeArn,
        description: 'Workflow Agent Runtime ARN',
        exportName: `BidOpsAI-WorkflowRuntimeArn-${props.environment}`,
      });

      new cdk.CfnOutput(this, 'WorkflowAgentRuntimeName', {
        value: workflowRuntime.agentRuntimeName || `bidopsai-workflow-agent-${props.environment}`,
        description: 'Workflow Agent Runtime Name',
      });
    }

    // AI Assistant Agent Runtime (conditional)
    let aiAssistantRuntime: bedrockagentcore.CfnRuntime | undefined;
    if (deployAIAssistant) {
      const aiAssistantVersion = props.aiAssistantAgentImageUri!.split(':').pop() || 'latest';
      
      aiAssistantRuntime = new bedrockagentcore.CfnRuntime(this, 'AIAssistantAgentRuntime', {
        agentRuntimeName: `bidopsai_ai_assistant_agent_${props.environment}`,
        description: `BidOps AI Assistant Agent Runtime for ${props.environment} environment`,
        roleArn: props.aiAssistantAgentRole.roleArn,

        // Container configuration
        agentRuntimeArtifact: {
          containerConfiguration: {
            containerUri: props.aiAssistantAgentImageUri!,
          },
        },

        // Network configuration - PUBLIC for internet access
        networkConfiguration: {
          networkMode: 'PUBLIC',
        },

        // Protocol configuration
        protocolConfiguration: 'HTTP',

        // Environment variables
        environmentVariables: {
          LOG_LEVEL: enableMonitoring ? 'INFO' : 'DEBUG',
          ENVIRONMENT: props.environment,
          IMAGE_VERSION: aiAssistantVersion,
          AGENT_TYPE: 'ai_assistant',
        },

        tags: {
          Environment: props.environment,
          Application: 'BidOpsAI',
          AgentType: 'AIAssistantSupervisor',
          ManagedBy: 'CDK',
        },
      });

      // Store ARN
      this.aiAssistantRuntimeArn = aiAssistantRuntime.attrAgentRuntimeArn;

      // Output runtime information
      new cdk.CfnOutput(this, 'AIAssistantAgentRuntimeId', {
        value: aiAssistantRuntime.attrAgentRuntimeId,
        description: 'AI Assistant Agent Runtime ID',
        exportName: `BidOpsAI-AIAssistantRuntimeId-${props.environment}`,
      });

      new cdk.CfnOutput(this, 'AIAssistantAgentRuntimeArn', {
        value: aiAssistantRuntime.attrAgentRuntimeArn,
        description: 'AI Assistant Agent Runtime ARN',
        exportName: `BidOpsAI-AIAssistantRuntimeArn-${props.environment}`,
      });

      new cdk.CfnOutput(this, 'AIAssistantAgentRuntimeName', {
        value: aiAssistantRuntime.agentRuntimeName || `bidopsai-ai-assistant-agent-${props.environment}`,
        description: 'AI Assistant Agent Runtime Name',
      });
    }

    new cdk.CfnOutput(this, 'EndpointName', {
      value: 'DEFAULT',
      description: 'Runtime Endpoint Name (DEFAULT auto-created by AgentCore)',
    });

    // Add tags to the stack
    cdk.Tags.of(this).add('Environment', props.environment);
    cdk.Tags.of(this).add('Application', 'BidOpsAI');
    cdk.Tags.of(this).add('Component', 'AgentCore');
    cdk.Tags.of(this).add('ManagedBy', 'CDK');
  }
}