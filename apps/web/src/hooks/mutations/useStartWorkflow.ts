/**
 * useStartWorkflow Hook
 * 
 * TanStack Query mutation hook for initiating workflow execution.
 * Uses BFF pattern via centralized agent-client library.
 * 
 * Architecture:
 * - Calls invokeBFFAgent() from agent-client library
 * - Agent client handles BFF route URL
 * - BFF determines mode (local/remote) via environment variables
 * - No hardcoded URLs in hook
 */

import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { generateSessionId, invokeBFFAgent } from '@/lib/api/agent-client';

// ============================================
// Types
// ============================================

export interface StartWorkflowPayload {
  projectId: string;
  userId: string;
  sessionId?: string; // Optional - will be generated if not provided
}

export interface StartWorkflowResponse {
  success: boolean;
  sessionId: string;
  message?: string;
}

// ============================================
// API Client Function
// ============================================

/**
 * Starts workflow via BFF using centralized agent-client
 */
async function startWorkflow(payload: StartWorkflowPayload): Promise<StartWorkflowResponse> {
  const sessionId = payload.sessionId || generateSessionId();
  
  console.log('[useStartWorkflow] Starting workflow with session:', sessionId);
  
  // Use centralized BFF client - no hardcoded URLs
  await invokeBFFAgent({
    project_id: payload.projectId,
    user_id: payload.userId,
    session_id: sessionId,
    start: true, // This is a new workflow start
    agent_type: 'workflow', // Explicitly specify workflow agent
  });

  // For streaming responses, we don't wait for completion here
  // The hook just confirms invocation was initiated
  return {
    success: true,
    sessionId,
    message: 'Workflow started successfully',
  };
}

// ============================================
// Mutation Hook
// ============================================

export function useStartWorkflow() {
  return useMutation({
    mutationFn: startWorkflow,
    
    onSuccess: (data) => {
      console.log('[useStartWorkflow] Workflow started:', data);
      toast.success('Workflow started successfully', {
        description: `Session ID: ${data.sessionId}`,
      });
    },
    
    onError: (error: Error) => {
      console.error('[useStartWorkflow] Failed to start workflow:', error);
      toast.error('Failed to start workflow', {
        description: error.message,
      });
    },
  });
}