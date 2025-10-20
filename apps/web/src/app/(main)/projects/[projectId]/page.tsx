'use client';

import { AgentChatInterface } from '@/components/projects/AgentChat/AgentChatInterface';
import type { ChatMessageProps } from '@/components/projects/AgentChat/ChatMessage';
import { WorkflowProgress } from '@/components/projects/WorkflowProgress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/hooks/useAuth';
import { useProject } from '@/hooks/queries/useProject';
import { useWorkflowExecution } from '@/hooks/queries/useWorkflowExecution';
import { useWorkflowStream } from '@/hooks/streams/useWorkflowStream';
import { useStartWorkflow, useSendAgentMessage } from '@/hooks/mutations';
import type { SSEEvent } from '@/types/sse.types';
import { SSEEventType } from '@/types/sse.types';
import type { WorkflowStep } from '@/types/workflow.types';
import { AgentTaskStatus } from '@/types/workflow.types';
import { formatDate } from '@/utils/date';
import { AlertCircle, ArrowLeft, Loader2, Play, Users } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useMemo, useState } from 'react';
import { toast } from 'sonner';

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  // Get current user
  const { user } = useAuth();

  // State for chat messages
  const [messages, setMessages] = useState<ChatMessageProps[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [currentAgentName, setCurrentAgentName] = useState<string>();

  // Fetch project data
  const { data: project, isLoading: projectLoading, error: projectError } = useProject(projectId);

  // Get the latest workflow execution for this project
  const latestWorkflowId = project?.workflowExecutions?.[0]?.id;

  // Fetch workflow execution
  const {
    data: workflowExecution,
    isLoading: workflowLoading,
    error: workflowError,
  } = useWorkflowExecution(latestWorkflowId);

  // Handle SSE events
  const handleSSEEvent = useCallback((event: SSEEvent) => {
    console.log('SSE Event:', event);

    // Update streaming/thinking states based on event type
    switch (event.type) {
      case SSEEventType.PARSER_STARTED:
      case SSEEventType.ANALYSIS_STARTED:
      case SSEEventType.CONTENT_STARTED:
      case SSEEventType.COMPLIANCE_STARTED:
      case SSEEventType.QA_STARTED:
      case SSEEventType.COMMS_STARTED:
      case SSEEventType.SUBMISSION_STARTED:
        setIsThinking(true);
        setCurrentAgentName(getAgentDisplayName(event.type));
        break;

      case SSEEventType.PARSER_COMPLETED:
      case SSEEventType.ANALYSIS_COMPLETED:
      case SSEEventType.CONTENT_COMPLETED:
      case SSEEventType.COMPLIANCE_COMPLETED:
      case SSEEventType.QA_COMPLETED:
      case SSEEventType.COMMS_COMPLETED:
      case SSEEventType.SUBMISSION_COMPLETED:
        setIsThinking(false);
        break;

      case SSEEventType.PARSER_FAILED:
      case SSEEventType.ANALYSIS_FAILED:
      case SSEEventType.CONTENT_FAILED:
      case SSEEventType.COMPLIANCE_FAILED:
      case SSEEventType.QA_FAILED:
      case SSEEventType.COMMS_FAILED:
      case SSEEventType.SUBMISSION_FAILED:
        setIsThinking(false);
        setIsStreaming(false);
        toast.error('Agent task failed', {
          description: (event.data as Record<string, unknown>)?.errorMessage as string || 'An error occurred',
        });
        break;

      case SSEEventType.AWAITING_FEEDBACK:
      case SSEEventType.AWAITING_REVIEW:
      case SSEEventType.REVIEW_PROMPT:
        setIsStreaming(false);
        setIsThinking(false);
        break;
    }

    // Add agent message to chat
    const agentMessage = formatSSEEventAsMessage(event);
    if (agentMessage) {
      setMessages((prev) => [...prev, agentMessage]);
    }
  }, []);

  // Connect to SSE stream when workflow exists
  const { isConnected, error: sseError } = useWorkflowStream({
    projectId,
    userId: user?.userId || '',
    sessionId: latestWorkflowId,
    workflowExecutionId: latestWorkflowId,
    enabled: !!latestWorkflowId && !!user?.userId,
    onEvent: handleSSEEvent,
    onError: (error) => {
      toast.error('Connection lost', {
        description: error.message,
      });
    },
  });

  // Start workflow mutation
  const startWorkflowMutation = useStartWorkflow();

  // Handle starting workflow
  const handleStartWorkflow = useCallback(async () => {
    if (!user?.userId) {
      toast.error('You must be signed in to start a workflow');
      return;
    }

    // Set UI states
    setIsStreaming(true);
    setIsThinking(true);
    setCurrentAgentName('Supervisor Agent');

    // Add initial system message
    const initialMessage: ChatMessageProps = {
      id: `msg-${Date.now()}`,
      type: 'agent',
      content: '🚀 Workflow started! Initializing agents and setting up tasks...',
      timestamp: new Date(),
      agentName: 'System',
    };
    setMessages([initialMessage]);

    // Call mutation
    await startWorkflowMutation.mutateAsync({
      projectId,
      userId: user.userId,
    });

    // The streaming will be handled by useWorkflowStream hook
    // which will auto-connect when latestWorkflowId becomes available
  }, [projectId, user, startWorkflowMutation]);

  // Send message mutation
  const sendMessageMutation = useSendAgentMessage();

  // Handle sending messages
  const handleSendMessage = useCallback(
    async (message: string) => {
      if (!user?.userId || !latestWorkflowId) {
        toast.error('Cannot send message: session not initialized');
        return;
      }

      // Add user message to chat with sending status
      const messageId = `msg-${Date.now()}`;
      const userMessage: ChatMessageProps = {
        id: messageId,
        type: 'user',
        content: message,
        timestamp: new Date(),
        status: 'sending',
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsStreaming(true);

      try {
        // Send message via mutation hook
        await sendMessageMutation.mutateAsync({
          projectId,
          userId: user.userId,
          sessionId: latestWorkflowId,
          message,
        });

        // Update message status to sent
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === messageId ? { ...msg, status: 'sent' as const } : msg
          )
        );
      } catch {
        // Update message status to error (error is handled by mutation hook)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === messageId ? { ...msg, status: 'error' as const } : msg
          )
        );
        setIsStreaming(false);
      }
    },
    [projectId, latestWorkflowId, user, sendMessageMutation]
  );

  // Map workflow execution to progress steps
  const workflowSteps = useMemo<WorkflowStep[]>(() => {
    if (!workflowExecution) return [];

    const agentTasks = workflowExecution.agentTasks || [];

    return [
      {
        id: 'upload',
        name: 'Upload',
        status: AgentTaskStatus.COMPLETED,
        description: 'Files uploaded',
      },
      {
        id: 'parsing',
        name: 'Parsing',
        status: agentTasks.find((t) => t.agent === 'PARSER')?.status || AgentTaskStatus.OPEN,
        description: 'Extract content',
      },
      {
        id: 'analysis',
        name: 'Analysis',
        status: agentTasks.find((t) => t.agent === 'ANALYSIS')?.status || AgentTaskStatus.OPEN,
        description: 'Analyze requirements',
      },
      {
        id: 'content',
        name: 'Content',
        status: agentTasks.find((t) => t.agent === 'CONTENT')?.status || AgentTaskStatus.OPEN,
        description: 'Generate artifacts',
      },
      {
        id: 'compliance',
        name: 'Compliance',
        status: agentTasks.find((t) => t.agent === 'COMPLIANCE')?.status || AgentTaskStatus.OPEN,
        description: 'Verify compliance',
      },
      {
        id: 'qa',
        name: 'QA',
        status: agentTasks.find((t) => t.agent === 'QA')?.status || AgentTaskStatus.OPEN,
        description: 'Quality review',
      },
      {
        id: 'comms',
        name: 'Comms',
        status: agentTasks.find((t) => t.agent === 'COMMS')?.status || AgentTaskStatus.OPEN,
        description: 'Send notifications',
      },
      {
        id: 'bidding',
        name: 'Bidding',
        status: agentTasks.find((t) => t.agent === 'SUBMISSION')?.status || AgentTaskStatus.OPEN,
        description: 'Submit proposal',
      },
    ];
  }, [workflowExecution]);

  // Loading state
  if (projectLoading || workflowLoading) {
    return (
      <div className="container mx-auto p-6 space-y-6">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  // Error state
  if (projectError || workflowError) {
    return (
      <div className="container mx-auto p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Failed to load project details. Please try again.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="container mx-auto p-6">
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>Project not found.</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link href="/projects/all">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <h1 className="text-3xl font-bold">{project.name}</h1>
            <Badge
              variant={
                project.status === 'COMPLETED'
                  ? 'default'
                  : project.status === 'IN_PROGRESS'
                    ? 'secondary'
                    : 'outline'
              }
            >
              {project.status}
            </Badge>
          </div>
          {project.description && (
            <p className="text-muted-foreground">{project.description}</p>
          )}
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>Created: {formatDate(project.createdAt)}</span>
            {project.deadline && <span>Deadline: {formatDate(project.deadline)}</span>}
            <span>Progress: {project.progressPercentage}%</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">
            <Users className="h-4 w-4 mr-2" />
            Manage Team
          </Button>
          {!workflowExecution && (
            <Button
              size="sm"
              onClick={handleStartWorkflow}
              disabled={startWorkflowMutation.isPending || !user?.userId}
            >
              {startWorkflowMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Start Workflow
                </>
              )}
            </Button>
          )}
        </div>
      </div>

      <Separator />

      {/* Workflow Progress */}
      {workflowExecution && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Workflow Progress</span>
              {isConnected ? (
                <Badge variant="outline" className="bg-green-500/10 text-green-500">
                  Connected
                </Badge>
              ) : (
                <Badge variant="outline" className="bg-yellow-500/10 text-yellow-500">
                  Connecting...
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <WorkflowProgress
              steps={workflowSteps}
              currentStep={getCurrentStepId(workflowSteps)}
              workflowStatus={workflowExecution.status}
            />
          </CardContent>
        </Card>
      )}

      {/* Agent Chat Interface */}
      <Card className="flex flex-col h-[600px]">
        <CardHeader>
          <CardTitle>Agent Console</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 p-0">
          <AgentChatInterface
            messages={messages}
            onSendMessage={handleSendMessage}
            isStreaming={isStreaming}
            isThinking={isThinking}
            currentAgentName={currentAgentName}
            disabled={!workflowExecution}
          />
        </CardContent>
      </Card>

      {sseError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{sseError.message}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}

// Helper functions
function getAgentDisplayName(eventType: SSEEventType): string {
  const agentMap: Record<string, string> = {
    [SSEEventType.PARSER_STARTED]: 'Parser Agent',
    [SSEEventType.ANALYSIS_STARTED]: 'Analysis Agent',
    [SSEEventType.CONTENT_STARTED]: 'Content Agent',
    [SSEEventType.COMPLIANCE_STARTED]: 'Compliance Agent',
    [SSEEventType.QA_STARTED]: 'QA Agent',
    [SSEEventType.COMMS_STARTED]: 'Communications Agent',
    [SSEEventType.SUBMISSION_STARTED]: 'Submission Agent',
  };
  return agentMap[eventType] || 'AI Agent';
}

function formatSSEEventAsMessage(event: SSEEvent): ChatMessageProps | null {
  // Only create messages for specific event types
  const messageTypes = [
    SSEEventType.ANALYSIS_COMPLETED,
    SSEEventType.AWAITING_FEEDBACK,
    SSEEventType.AWAITING_REVIEW,
    SSEEventType.REVIEW_PROMPT,
    SSEEventType.COMMS_PERMISSION,
    SSEEventType.SUBMISSION_PERMISSION,
    SSEEventType.EMAIL_DRAFT,
  ];

  if (!messageTypes.includes(event.type)) {
    return null;
  }

  let content = '';
  switch (event.type) {
    case SSEEventType.ANALYSIS_COMPLETED:
      content = (event.data as Record<string, unknown>)?.analysisMarkdown as string || 'Analysis completed';
      break;
    case SSEEventType.AWAITING_FEEDBACK:
    case SSEEventType.AWAITING_REVIEW:
    case SSEEventType.REVIEW_PROMPT:
      content = (event.data as Record<string, unknown>)?.message as string || 'Awaiting your input';
      break;
    default:
      content = JSON.stringify(event.data, null, 2);
  }

  return {
    id: event.id || `event-${Date.now()}`,
    type: 'agent',
    content,
    timestamp: new Date(event.timestamp),
    agentName: getAgentDisplayName(event.type),
  };
}

function getCurrentStepId(steps: WorkflowStep[]): string | undefined {
  const inProgressStep = steps.find((s) => s.status === 'IN_PROGRESS');
  const waitingStep = steps.find((s) => s.status === 'WAITING');
  return inProgressStep?.id || waitingStep?.id || steps[steps.length - 1]?.id;
}