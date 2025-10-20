import * as cdk from 'aws-cdk-lib';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

export interface ObservabilityStackProps extends cdk.StackProps {
  /**
   * Environment name (dev, staging, prod)
   */
  environment: string;

  /**
   * Workflow agent role for granting observability permissions
   * NOTE: Made optional to avoid circular dependency with IAM stack
   * Permissions are now self-contained in IAM stack
   */
  workflowAgentRole?: iam.IRole;

  /**
   * AI Assistant agent role for granting observability permissions
   * NOTE: Made optional to avoid circular dependency with IAM stack
   * Permissions are now self-contained in IAM stack
   */
  aiAssistantAgentRole?: iam.IRole;

  /**
   * LangFuse API key secret (optional, can be set later)
   */
  langfuseSecret?: secretsmanager.ISecret;
}

/**
 * Stack for comprehensive observability and monitoring
 * 
 * This stack configures:
 * 1. CloudWatch Logs - Centralized logging for all agents
 * 2. CloudWatch Metrics - Custom metrics and dashboards
 * 3. AWS X-Ray - Distributed tracing
 * 4. LangFuse Integration - LLM observability and evaluation
 * 
 * Features:
 * - Agent-specific log groups with appropriate retention
 * - Custom metrics for agent performance tracking
 * - Unified dashboard for monitoring
 * - X-Ray tracing for request flows
 * - LangFuse integration for LLM call tracking
 */
export class ObservabilityStack extends cdk.Stack {
  public readonly agentMetricNamespace: string = 'BidOpsAI/Agents';
  public readonly workflowAgentLogGroup: logs.ILogGroup;
  public readonly aiAssistantAgentLogGroup: logs.ILogGroup;
  public readonly systemLogGroup: logs.ILogGroup;
  public readonly dashboard: cloudwatch.Dashboard;

  constructor(scope: Construct, id: string, props: ObservabilityStackProps) {
    super(scope, id, props);

    // Determine retention based on environment
    const logRetention = props.environment === 'prod'
      ? logs.RetentionDays.SIX_MONTHS
      : logs.RetentionDays.ONE_MONTH;

    // Create CloudWatch Log Groups
    this.workflowAgentLogGroup = new logs.LogGroup(this, 'WorkflowAgentLogs', {
      logGroupName: `/bidopsai/${props.environment}/agents/workflow`,
      retention: logRetention,
      removalPolicy: props.environment === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
    });

    this.aiAssistantAgentLogGroup = new logs.LogGroup(this, 'AIAssistantAgentLogs', {
      logGroupName: `/bidopsai/${props.environment}/agents/ai-assistant`,
      retention: logRetention,
      removalPolicy: props.environment === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
    });

    this.systemLogGroup = new logs.LogGroup(this, 'SystemLogs', {
      logGroupName: `/bidopsai/${props.environment}/system`,
      retention: logRetention,
      removalPolicy: props.environment === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
    });

    // Note: CloudWatch Logs permissions are already granted in IAM stack
    // to avoid circular dependencies. IAM roles have appropriate log group access.

    // Note: X-Ray permissions are already granted in IAM stack
    // to avoid circular dependencies.

    // Create CloudWatch Dashboard
    this.dashboard = this.createDashboard(props.environment);

    // Create CloudWatch Alarms (prod and staging only)
    if (props.environment === 'prod' || props.environment === 'staging') {
      this.createAlarms(props.environment);
    }

    // Outputs
    new cdk.CfnOutput(this, 'WorkflowAgentLogGroupName', {
      value: this.workflowAgentLogGroup.logGroupName,
      description: 'Workflow Agent CloudWatch Log Group',
      exportName: `BidOpsAI-WorkflowAgentLogGroup-${props.environment}`,
    });

    new cdk.CfnOutput(this, 'AIAssistantAgentLogGroupName', {
      value: this.aiAssistantAgentLogGroup.logGroupName,
      description: 'AI Assistant Agent CloudWatch Log Group',
      exportName: `BidOpsAI-AIAssistantAgentLogGroup-${props.environment}`,
    });

    new cdk.CfnOutput(this, 'DashboardName', {
      value: this.dashboard.dashboardName,
      description: 'CloudWatch Dashboard Name',
      exportName: `BidOpsAI-Dashboard-${props.environment}`,
    });

    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=${this.dashboard.dashboardName}`,
      description: 'CloudWatch Dashboard URL',
    });

    // Add tags
    cdk.Tags.of(this).add('Environment', props.environment);
    cdk.Tags.of(this).add('Application', 'BidOpsAI');
    cdk.Tags.of(this).add('Component', 'Observability');
    cdk.Tags.of(this).add('ManagedBy', 'CDK');
  }

  /**
   * Create CloudWatch Dashboard
   */
  private createDashboard(environment: string): cloudwatch.Dashboard {
    const dashboard = new cloudwatch.Dashboard(this, 'AgentsDashboard', {
      dashboardName: `BidOpsAI-Agents-${environment}`,
      defaultInterval: cdk.Duration.hours(1),
    });

    // Agent Execution Metrics
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Agent Task Executions',
        left: [
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'TaskExecutions',
            dimensionsMap: { Agent: 'Parser' },
            statistic: 'Sum',
            label: 'Parser',
          }),
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'TaskExecutions',
            dimensionsMap: { Agent: 'Analysis' },
            statistic: 'Sum',
            label: 'Analysis',
          }),
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'TaskExecutions',
            dimensionsMap: { Agent: 'Content' },
            statistic: 'Sum',
            label: 'Content',
          }),
        ],
        width: 12,
      }),
      new cloudwatch.GraphWidget({
        title: 'Agent Task Duration (ms)',
        left: [
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'TaskDuration',
            dimensionsMap: { Agent: 'Parser' },
            statistic: 'Average',
            label: 'Parser Avg',
          }),
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'TaskDuration',
            dimensionsMap: { Agent: 'Analysis' },
            statistic: 'Average',
            label: 'Analysis Avg',
          }),
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'TaskDuration',
            dimensionsMap: { Agent: 'Content' },
            statistic: 'Average',
            label: 'Content Avg',
          }),
        ],
        width: 12,
      })
    );

    // Error Metrics
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Agent Task Errors',
        left: [
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'TaskErrors',
            dimensionsMap: { Agent: 'ALL' },
            statistic: 'Sum',
            label: 'Total Errors',
            color: cloudwatch.Color.RED,
          }),
        ],
        width: 12,
      }),
      new cloudwatch.GraphWidget({
        title: 'Workflow Executions',
        left: [
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'WorkflowExecutions',
            dimensionsMap: { Status: 'Completed' },
            statistic: 'Sum',
            label: 'Completed',
            color: cloudwatch.Color.GREEN,
          }),
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'WorkflowExecutions',
            dimensionsMap: { Status: 'Failed' },
            statistic: 'Sum',
            label: 'Failed',
            color: cloudwatch.Color.RED,
          }),
        ],
        width: 12,
      })
    );

    // LLM Metrics
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'LLM Invocations',
        left: [
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'LLMInvocations',
            statistic: 'Sum',
            label: 'Total Invocations',
          }),
        ],
        width: 8,
      }),
      new cloudwatch.GraphWidget({
        title: 'LLM Token Usage',
        left: [
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'LLMTokensInput',
            statistic: 'Sum',
            label: 'Input Tokens',
          }),
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'LLMTokensOutput',
            statistic: 'Sum',
            label: 'Output Tokens',
          }),
        ],
        width: 8,
      }),
      new cloudwatch.GraphWidget({
        title: 'LLM Latency (ms)',
        left: [
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'LLMLatency',
            statistic: 'Average',
            label: 'Avg Latency',
          }),
          new cloudwatch.Metric({
            namespace: this.agentMetricNamespace,
            metricName: 'LLMLatency',
            statistic: 'Maximum',
            label: 'Max Latency',
            color: cloudwatch.Color.RED,
          }),
        ],
        width: 8,
      })
    );

    // Log Insights Queries
    dashboard.addWidgets(
      new cloudwatch.LogQueryWidget({
        title: 'Recent Error Logs',
        logGroupNames: [
          this.workflowAgentLogGroup.logGroupName,
          this.aiAssistantAgentLogGroup.logGroupName,
          this.systemLogGroup.logGroupName,
        ],
        queryLines: [
          'fields @timestamp, @message, @logStream',
          'filter @message like /ERROR|Error|error/',
          'sort @timestamp desc',
          'limit 20',
        ],
        width: 24,
      })
    );

    return dashboard;
  }

  /**
   * Create CloudWatch Alarms for critical metrics
   */
  private createAlarms(environment: string): void {
    // Alarm for high error rate
    new cloudwatch.Alarm(this, 'HighErrorRateAlarm', {
      alarmName: `BidOpsAI-HighErrorRate-${environment}`,
      alarmDescription: 'Alert when agent error rate is high',
      metric: new cloudwatch.Metric({
        namespace: this.agentMetricNamespace,
        metricName: 'TaskErrors',
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: environment === 'prod' ? 5 : 10,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Alarm for long task duration
    new cloudwatch.Alarm(this, 'LongTaskDurationAlarm', {
      alarmName: `BidOpsAI-LongTaskDuration-${environment}`,
      alarmDescription: 'Alert when agent tasks take too long',
      metric: new cloudwatch.Metric({
        namespace: this.agentMetricNamespace,
        metricName: 'TaskDuration',
        statistic: 'Average',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 300000, // 5 minutes in ms
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Alarm for high LLM latency
    new cloudwatch.Alarm(this, 'HighLLMLatencyAlarm', {
      alarmName: `BidOpsAI-HighLLMLatency-${environment}`,
      alarmDescription: 'Alert when LLM response times are high',
      metric: new cloudwatch.Metric({
        namespace: this.agentMetricNamespace,
        metricName: 'LLMLatency',
        statistic: 'Average',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 30000, // 30 seconds in ms
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
  }
}