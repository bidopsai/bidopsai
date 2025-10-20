'use client';

import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import type { SSEEvent } from '@/types/sse.types';
import { SSEEventType } from '@/types/sse.types';

interface UseWorkflowStreamOptions {
  projectId: string;
  userId: string;
  sessionId?: string;
  workflowExecutionId?: string;
  agentType?: 'workflow' | 'ai-assistant'; // Default: workflow
  enabled?: boolean;
  onEvent?: (event: SSEEvent) => void;
  onError?: (error: Error) => void;
}

interface WorkflowStreamState {
  isConnected: boolean;
  isConnecting: boolean;
  error: Error | null;
  lastEvent: SSEEvent | null;
  sessionId: string | null;
}

/**
 * Hook for streaming workflow/agent updates via Server-Sent Events (SSE)
 *
 * This hook follows the AWS AgentCore streaming pattern:
 * 1. Makes POST request to BFF endpoint with payload
 * 2. Receives streaming response in SSE format with "data:" prefix
 * 3. Parses each event and updates React Query cache
 * 4. Maintains session ID for conversation context
 *
 * For local mode: BFF proxies to Docker FastAPI (URL-based)
 * For remote mode: BFF uses AWS SDK to invoke AgentCore Runtime
 */
export function useWorkflowStream({
  projectId,
  userId,
  sessionId: providedSessionId,
  workflowExecutionId,
  agentType = 'workflow',
  enabled = true,
  onEvent,
  onError,
}: UseWorkflowStreamOptions) {
  const queryClient = useQueryClient();
  const abortControllerRef = useRef<AbortController | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  
  // Generate session ID on mount if not provided
  const [sessionId] = useState(() => providedSessionId || `session-${Date.now()}-${Math.random().toString(36).substring(2, 15)}`);

  const [state, setState] = useState<WorkflowStreamState>({
    isConnected: false,
    isConnecting: false,
    error: null,
    lastEvent: null,
    sessionId,
  });

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const connect = async () => {
      // Clean up existing connection
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();
      setState((prev) => ({ ...prev, isConnecting: true, error: null }));

      try {
        // POST request to BFF with streaming enabled
        const response = await fetch('/api/workflow-agents/invocations', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
          },
          body: JSON.stringify({
            project_id: projectId,
            user_id: userId,
            session_id: sessionId,
            start: !workflowExecutionId, // true if new workflow, false if continuing
            agent_type: agentType,
          }),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        if (!response.body) {
          throw new Error('No response body received');
        }

        setState((prev) => ({
          ...prev,
          isConnected: true,
          isConnecting: false,
          error: null,
        }));
        reconnectAttemptsRef.current = 0;

        // Read the stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            console.log('[Stream] Connection closed gracefully');
            break;
          }

          // Decode chunk and add to buffer
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;

          // Process complete lines (split by \n)
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer

          for (const line of lines) {
            const trimmedLine = line.trim();

            if (trimmedLine === '') {
              continue; // Skip empty lines
            }

            // Handle SSE format: "data: {json}"
            if (trimmedLine.startsWith('data:')) {
              const dataContent = trimmedLine.substring(5).trim(); // Remove "data:" prefix

              try {
                const sseEvent: SSEEvent = JSON.parse(dataContent);

                setState((prev) => ({ ...prev, lastEvent: sseEvent }));

                // Call custom event handler
                onEvent?.(sseEvent);

                // Update TanStack Query cache
                handleCacheUpdate(sseEvent);
              } catch (parseError) {
                console.warn('[Stream] Failed to parse SSE event:', dataContent, parseError);
              }
            } else {
              // Try parsing as JSON (no "data:" prefix)
              try {
                const sseEvent: SSEEvent = JSON.parse(trimmedLine);

                setState((prev) => ({ ...prev, lastEvent: sseEvent }));
                onEvent?.(sseEvent);
                handleCacheUpdate(sseEvent);
              } catch (parseError) {
                console.warn('[Stream] Failed to parse line:', trimmedLine, parseError);
              }
            }
          }
        }

        // Connection closed
        setState((prev) => ({
          ...prev,
          isConnected: false,
          isConnecting: false,
        }));

      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
          console.log('[Stream] Connection aborted');
          return;
        }

        console.error('[Stream] Connection error:', error);

        setState((prev) => ({
          ...prev,
          isConnected: false,
          isConnecting: false,
          error: error instanceof Error ? error : new Error('Stream connection failed'),
        }));

        // Attempt reconnection with exponential backoff
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          reconnectAttemptsRef.current += 1;

          console.log(`[Stream] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else {
          const err = new Error('Max reconnection attempts reached');
          setState((prev) => ({ ...prev, error: err }));
          onError?.(err);
        }
      }
    };

    // Handle cache updates based on SSE event types
    const handleCacheUpdate = (event: SSEEvent) => {
      switch (event.type) {
        case SSEEventType.WORKFLOW_CREATED:
        case SSEEventType.WORKFLOW_UPDATED:
        case SSEEventType.WORKFLOW_COMPLETED:
        case SSEEventType.WORKFLOW_COMPLETED_WITHOUT_COMMS:
        case SSEEventType.WORKFLOW_COMPLETED_WITHOUT_SUBMISSION:
          // Invalidate workflow execution queries
          queryClient.invalidateQueries({
            queryKey: ['workflowExecution', workflowExecutionId],
          });
          queryClient.invalidateQueries({
            queryKey: ['project', projectId],
          });
          break;

        case SSEEventType.AGENT_TASK_UPDATED:
          // Invalidate agent tasks queries
          queryClient.invalidateQueries({
            queryKey: ['agentTasks', workflowExecutionId],
          });
          break;

        case SSEEventType.ARTIFACTS_READY:
        case SSEEventType.ARTIFACTS_EXPORTED:
          // Invalidate artifacts queries
          queryClient.invalidateQueries({
            queryKey: ['artifacts', projectId],
          });
          break;

        case SSEEventType.PARSER_STARTED:
        case SSEEventType.PARSER_COMPLETED:
        case SSEEventType.PARSER_FAILED:
        case SSEEventType.ANALYSIS_STARTED:
        case SSEEventType.ANALYSIS_COMPLETED:
        case SSEEventType.ANALYSIS_FAILED:
        case SSEEventType.ANALYSIS_RESTARTED:
        case SSEEventType.CONTENT_STARTED:
        case SSEEventType.CONTENT_COMPLETED:
        case SSEEventType.CONTENT_FAILED:
        case SSEEventType.RETURNING_TO_CONTENT:
        case SSEEventType.COMPLIANCE_STARTED:
        case SSEEventType.COMPLIANCE_COMPLETED:
        case SSEEventType.COMPLIANCE_FAILED:
        case SSEEventType.QA_STARTED:
        case SSEEventType.QA_COMPLETED:
        case SSEEventType.QA_FAILED:
        case SSEEventType.COMMS_STARTED:
        case SSEEventType.COMMS_COMPLETED:
        case SSEEventType.COMMS_FAILED:
        case SSEEventType.SUBMISSION_STARTED:
        case SSEEventType.SUBMISSION_COMPLETED:
        case SSEEventType.SUBMISSION_FAILED:
          // Invalidate workflow execution and project progress
          queryClient.invalidateQueries({
            queryKey: ['workflowExecution', workflowExecutionId],
          });
          queryClient.invalidateQueries({
            queryKey: ['project', projectId],
          });
          break;

        default:
          // For unknown events, just log them
          console.debug('Unhandled SSE event:', event.type);
      }
    };

    // Initial connection
    connect();

    // Cleanup on unmount
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [enabled, projectId, userId, sessionId, workflowExecutionId, agentType, onEvent, onError, queryClient]);

  const disconnect = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    setState({
      isConnected: false,
      isConnecting: false,
      error: null,
      lastEvent: null,
      sessionId,
    });
  };

  return {
    ...state,
    disconnect,
  };
}