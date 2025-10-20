import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cr from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';

export interface BedrockDataAutomationStackProps extends cdk.StackProps {
  /**
   * Environment name (dev, staging, prod)
   */
  environment: string;

  /**
   * S3 bucket for storing raw documents
   */
  sourceBucket: s3.IBucket;

  /**
   * IAM role for Bedrock Data Automation to assume
   */
  dataAutomationRole?: iam.IRole;
}

/**
 * Stack for AWS Bedrock Data Automation configuration
 * 
 * This stack configures Bedrock Data Automation for document processing,
 * which is used by the Parser Agent to extract structured data from
 * uploaded bid documents (PDFs, Word docs, Excel, etc.)
 * 
 * Features:
 * - Document parsing and text extraction
 * - Table extraction from documents
 * - Structured data extraction
 * - Integration with S3 for input/output
 */
export class BedrockDataAutomationStack extends cdk.Stack {
  public readonly dataAutomationProjectArn: string;
  public readonly dataAutomationRole: iam.IRole;
  public readonly processedDocumentsBucket: s3.IBucket;

  constructor(scope: Construct, id: string, props: BedrockDataAutomationStackProps) {
    super(scope, id, props);

    // Create S3 bucket for processed documents
    this.processedDocumentsBucket = new s3.Bucket(this, 'ProcessedDocuments', {
      bucketName: `bidopsai-processed-docs-${props.environment}-${this.account}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: props.environment === 'prod',
      lifecycleRules: [
        {
          id: 'DeleteOldProcessedDocs',
          enabled: true,
          expiration: cdk.Duration.days(props.environment === 'prod' ? 365 : 90),
          noncurrentVersionExpiration: cdk.Duration.days(30),
        },
        {
          id: 'TransitionToIA',
          enabled: props.environment === 'prod',
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(90),
            },
          ],
        },
      ],
      removalPolicy: props.environment === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: props.environment !== 'prod',
    });

    // Create IAM role for Bedrock Data Automation
    const dataAutomationRole = props.dataAutomationRole
      ? undefined
      : new iam.Role(this, 'DataAutomationRole', {
          assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
          description: 'Role for Bedrock Data Automation to access S3 and process documents',
        });

    this.dataAutomationRole = props.dataAutomationRole || dataAutomationRole!;

    // Grant permissions to read from source bucket
    props.sourceBucket.grantRead(this.dataAutomationRole);

    // Grant permissions to write to processed documents bucket
    this.processedDocumentsBucket.grantReadWrite(this.dataAutomationRole);

    // Grant Bedrock model invocation permissions (only if we created the role)
    if (dataAutomationRole) {
      dataAutomationRole.addToPolicy(new iam.PolicyStatement({
        sid: 'BedrockModelInvocation',
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-3-5-sonnet-*`,
          `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-3-sonnet-*`,
        ],
      }));
    }

    // Create IAM role for Custom Resource Lambda
    const customResourceRole = new iam.Role(this, 'CustomResourceRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Grant permissions to manage Bedrock Data Automation projects
    customResourceRole.addToPolicy(new iam.PolicyStatement({
      sid: 'BedrockDataAutomationManagement',
      actions: [
        'bedrock:CreateDataAutomationProject',
        'bedrock:UpdateDataAutomationProject',
        'bedrock:DeleteDataAutomationProject',
        'bedrock:GetDataAutomationProject',
        'bedrock:ListDataAutomationProjects',
      ],
      resources: ['*'],
    }));

    // Grant permissions to pass the data automation role
    customResourceRole.addToPolicy(new iam.PolicyStatement({
      sid: 'PassRoleToBedrock',
      actions: ['iam:PassRole'],
      resources: [this.dataAutomationRole.roleArn],
      conditions: {
        StringEquals: {
          'iam:PassedToService': 'bedrock.amazonaws.com',
        },
      },
    }));

    // Create Bedrock Data Automation Project
    const dataAutomationProject = new cr.AwsCustomResource(this, 'DataAutomationProject', {
      onCreate: {
        service: 'Bedrock',
        action: 'createDataAutomationProject',
        parameters: {
          projectName: `bidopsai-document-parser-${props.environment}`,
          projectDescription: `Document parsing project for BidOps AI ${props.environment} environment`,
          projectStage: props.environment === 'prod' ? 'PRODUCTION' : 'DEVELOPMENT',
          standardOutputConfig: {
            s3Uri: `s3://${this.processedDocumentsBucket.bucketName}/parsed-documents/`,
          },
          overrideConfiguration: {
            document: {
              splitter: {
                splitterConfiguration: {
                  characterSplitter: {
                    maxTokens: 8000,
                    overlapPercentage: 10,
                  },
                },
              },
            },
          },
          encryptionConfiguration: {
            kmsKeyArn: undefined, // Use AWS managed key
          },
          roleArn: this.dataAutomationRole.roleArn,
        },
        physicalResourceId: cr.PhysicalResourceId.fromResponse('projectArn'),
      },
      onUpdate: {
        service: 'Bedrock',
        action: 'updateDataAutomationProject',
        parameters: {
          projectIdentifier: new cr.PhysicalResourceIdReference(),
          projectStage: props.environment === 'prod' ? 'PRODUCTION' : 'DEVELOPMENT',
          standardOutputConfig: {
            s3Uri: `s3://${this.processedDocumentsBucket.bucketName}/parsed-documents/`,
          },
        },
        physicalResourceId: cr.PhysicalResourceId.fromResponse('projectArn'),
      },
      onDelete: {
        service: 'Bedrock',
        action: 'deleteDataAutomationProject',
        parameters: {
          projectIdentifier: new cr.PhysicalResourceIdReference(),
        },
      },
      policy: cr.AwsCustomResourcePolicy.fromSdkCalls({
        resources: cr.AwsCustomResourcePolicy.ANY_RESOURCE,
      }),
      role: customResourceRole,
      timeout: cdk.Duration.minutes(10),
    });

    this.dataAutomationProjectArn = dataAutomationProject.getResponseField('projectArn');

    // Output important information
    new cdk.CfnOutput(this, 'DataAutomationProjectArn', {
      value: this.dataAutomationProjectArn,
      description: 'Bedrock Data Automation Project ARN',
      exportName: `BidOpsAI-DataAutomationProjectArn-${props.environment}`,
    });

    new cdk.CfnOutput(this, 'ProcessedDocumentsBucket', {
      value: this.processedDocumentsBucket.bucketName,
      description: 'S3 Bucket for processed documents',
      exportName: `BidOpsAI-ProcessedDocsBucket-${props.environment}`,
    });

    new cdk.CfnOutput(this, 'DataAutomationRoleArn', {
      value: this.dataAutomationRole.roleArn,
      description: 'IAM Role ARN for Bedrock Data Automation',
      exportName: `BidOpsAI-DataAutomationRoleArn-${props.environment}`,
    });

    new cdk.CfnOutput(this, 'ProcessedDocsS3Uri', {
      value: `s3://${this.processedDocumentsBucket.bucketName}/parsed-documents/`,
      description: 'S3 URI for processed documents output',
    });

    // Add tags
    cdk.Tags.of(this).add('Environment', props.environment);
    cdk.Tags.of(this).add('Application', 'BidOpsAI');
    cdk.Tags.of(this).add('Component', 'DataAutomation');
    cdk.Tags.of(this).add('ManagedBy', 'CDK');
  }

  /**
   * Grant read access to the processed documents bucket
   */
  public grantProcessedDocsReadAccess(grantee: iam.IGrantable): iam.Grant {
    return this.processedDocumentsBucket.grantRead(grantee);
  }

  /**
   * Grant full access to the data automation project
   */
  public grantDataAutomationAccess(grantee: iam.IGrantable): iam.Grant {
    return iam.Grant.addToPrincipal({
      grantee,
      actions: [
        'bedrock:InvokeDataAutomationAsync',
        'bedrock:GetDataAutomationProject',
        'bedrock:ListDataAutomationProjects',
      ],
      resourceArns: [this.dataAutomationProjectArn],
    });
  }
}