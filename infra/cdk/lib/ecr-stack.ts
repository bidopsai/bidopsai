import * as cdk from 'aws-cdk-lib';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

/**
 * BidOps.AI ECR Stack
 * 
 * Creates and configures ECR repositories for:
 * - Workflow Supervisor Agent Docker images
 * - AI Assistant Supervisor Agent Docker images
 * 
 * Features:
 * - Lifecycle policies for image retention and cost optimization
 * - Image scanning on push for security
 * - Cross-account access policies for CI/CD
 * - Tag immutability for production images
 * - Encryption at rest
 */
export class ECRStack extends cdk.Stack {
  public readonly workflowAgentRepository: ecr.Repository;
  public readonly aiAssistantAgentRepository: ecr.Repository;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Get environment from stack name or default to 'dev'
    const environment = this.node.tryGetContext('environment') || 'dev';

    // Create ECR repository for Workflow Supervisor Agent
    this.workflowAgentRepository = new ecr.Repository(this, 'WorkflowAgentRepository', {
      repositoryName: `bidopsai-workflow-agent-${environment}`,
      
      // Image scanning on push
      imageScanOnPush: true,
      
      // Tag immutability (enabled for prod/staging)
      imageTagMutability: environment === 'prod' || environment === 'staging'
        ? ecr.TagMutability.IMMUTABLE
        : ecr.TagMutability.MUTABLE,
      
      // Encryption at rest
      encryption: ecr.RepositoryEncryption.AES_256,
      
      // Lifecycle policy for image retention
      lifecycleRules: [
        {
          description: 'Keep last 10 tagged images',
          rulePriority: 1,
          tagStatus: ecr.TagStatus.TAGGED,
          tagPrefixList: ['v'],
          maxImageCount: 10,
        },
        {
          description: 'Keep last 5 untagged images',
          rulePriority: 2,
          tagStatus: ecr.TagStatus.UNTAGGED,
          maxImageCount: 5,
        },
        {
          description: 'Remove images older than 90 days',
          rulePriority: 3,
          tagStatus: ecr.TagStatus.ANY,
          maxImageAge: cdk.Duration.days(90),
        },
      ],
      
      // Removal policy
      removalPolicy: environment === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      
      // Auto delete images on stack deletion (dev/staging only)
      autoDeleteImages: environment !== 'prod',
    });

    // Create ECR repository for AI Assistant Supervisor Agent
    this.aiAssistantAgentRepository = new ecr.Repository(this, 'AIAssistantAgentRepository', {
      repositoryName: `bidopsai-ai-assistant-agent-${environment}`,
      
      // Image scanning on push
      imageScanOnPush: true,
      
      // Tag immutability (enabled for prod/staging)
      imageTagMutability: environment === 'prod' || environment === 'staging'
        ? ecr.TagMutability.IMMUTABLE
        : ecr.TagMutability.MUTABLE,
      
      // Encryption at rest
      encryption: ecr.RepositoryEncryption.AES_256,
      
      // Lifecycle policy for image retention
      lifecycleRules: [
        {
          description: 'Keep last 10 tagged images',
          rulePriority: 1,
          tagStatus: ecr.TagStatus.TAGGED,
          tagPrefixList: ['v'],
          maxImageCount: 10,
        },
        {
          description: 'Keep last 5 untagged images',
          rulePriority: 2,
          tagStatus: ecr.TagStatus.UNTAGGED,
          maxImageCount: 5,
        },
        {
          description: 'Remove images older than 90 days',
          rulePriority: 3,
          tagStatus: ecr.TagStatus.ANY,
          maxImageAge: cdk.Duration.days(90),
        },
      ],
      
      // Removal policy
      removalPolicy: environment === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      
      // Auto delete images on stack deletion (dev/staging only)
      autoDeleteImages: environment !== 'prod',
    });

    // Add repository policies for CI/CD access
    this.addRepositoryPolicies();

    // Stack outputs
    this.createOutputs(environment);

    // Add tags
    cdk.Tags.of(this).add('Environment', environment);
    cdk.Tags.of(this).add('Project', 'BidOpsAI');
    cdk.Tags.of(this).add('ManagedBy', 'CDK');
    cdk.Tags.of(this).add('Component', 'AgentCore');
  }

  /**
   * Add repository policies for cross-account access and CI/CD
   */
  private addRepositoryPolicies(): void {
    // Allow ECR pull from same account
    const pullPolicy = new iam.PolicyStatement({
      sid: 'AllowPull',
      effect: iam.Effect.ALLOW,
      principals: [new iam.AccountPrincipal(this.account)],
      actions: [
        'ecr:GetDownloadUrlForLayer',
        'ecr:BatchGetImage',
        'ecr:BatchCheckLayerAvailability',
      ],
    });

    // Allow ECR push from same account (for CI/CD)
    const pushPolicy = new iam.PolicyStatement({
      sid: 'AllowPush',
      effect: iam.Effect.ALLOW,
      principals: [new iam.AccountPrincipal(this.account)],
      actions: [
        'ecr:PutImage',
        'ecr:InitiateLayerUpload',
        'ecr:UploadLayerPart',
        'ecr:CompleteLayerUpload',
      ],
    });

    // Add policies to both repositories
    this.workflowAgentRepository.addToResourcePolicy(pullPolicy);
    this.workflowAgentRepository.addToResourcePolicy(pushPolicy);
    
    this.aiAssistantAgentRepository.addToResourcePolicy(pullPolicy);
    this.aiAssistantAgentRepository.addToResourcePolicy(pushPolicy);
  }

  /**
   * Create CloudFormation outputs
   */
  private createOutputs(environment: string): void {
    // Workflow Agent Repository Outputs
    new cdk.CfnOutput(this, 'WorkflowAgentRepositoryName', {
      value: this.workflowAgentRepository.repositoryName,
      description: 'ECR repository name for Workflow Agent',
      exportName: `BidOpsAI-WorkflowAgentRepo-${environment}`,
    });

    new cdk.CfnOutput(this, 'WorkflowAgentRepositoryUri', {
      value: this.workflowAgentRepository.repositoryUri,
      description: 'ECR repository URI for Workflow Agent',
      exportName: `BidOpsAI-WorkflowAgentRepoUri-${environment}`,
    });

    new cdk.CfnOutput(this, 'WorkflowAgentRepositoryArn', {
      value: this.workflowAgentRepository.repositoryArn,
      description: 'ECR repository ARN for Workflow Agent',
      exportName: `BidOpsAI-WorkflowAgentRepoArn-${environment}`,
    });

    // AI Assistant Agent Repository Outputs
    new cdk.CfnOutput(this, 'AIAssistantAgentRepositoryName', {
      value: this.aiAssistantAgentRepository.repositoryName,
      description: 'ECR repository name for AI Assistant Agent',
      exportName: `BidOpsAI-AIAssistantAgentRepo-${environment}`,
    });

    new cdk.CfnOutput(this, 'AIAssistantAgentRepositoryUri', {
      value: this.aiAssistantAgentRepository.repositoryUri,
      description: 'ECR repository URI for AI Assistant Agent',
      exportName: `BidOpsAI-AIAssistantAgentRepoUri-${environment}`,
    });

    new cdk.CfnOutput(this, 'AIAssistantAgentRepositoryArn', {
      value: this.aiAssistantAgentRepository.repositoryArn,
      description: 'ECR repository ARN for AI Assistant Agent',
      exportName: `BidOpsAI-AIAssistantAgentRepoArn-${environment}`,
    });

    // Region output
    new cdk.CfnOutput(this, 'ECRRegion', {
      value: this.region,
      description: 'AWS Region for ECR repositories',
      exportName: `BidOpsAI-ECRRegion-${environment}`,
    });
  }
}