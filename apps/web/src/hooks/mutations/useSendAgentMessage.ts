/**
 * useSendAgentMessage Hook
 * 
 * TanStack Query mutation hook for sending user messages to agents during workflow.
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
import { invokeBFFAgent } from '@/lib/api/agent-client';

// ============================================
// Types
// ============================================

export interface SendAgentMessagePayload {
  projectId: string;
  userId: string;
  sessionId: string; // Required for continuation
  message?: string; // Chat message
  contentEdits?: Record<string, unknown>; // Content edits from artifact viewer
}

export interface SendAgentMessageResponse {
  success: boolean;
  message?: string;
}

// ============================================
// API Client Function
// ============================================

/**
 * Sends message to agent via BFF using centralized agent-client
 */
async function sendAgentMessage(payload: SendAgentMessagePayload): Promise<SendAgentMessageResponse> {
  console.log('[useSendAgentMessage] Sending message with session:', payload.sessionId);
  
  // Use centralized BFF client - no hardcoded URLs
  await invokeBFFAgent({
    project_id: payload.projectId,
    user_id: payload.userId,
    session_id: payload.sessionId,
    start: false, // This is a continuation, not a new workflow
    user_input: {
      chat: payload.message,
      content_edits: payload.contentEdits,
    },
    agent_type: 'workflow', // Explicitly specify workflow agent
  });

  // For streaming responses, we don't wait for completion here
  // The hook just confirms message was sent
  return {
    success: true,
    message: 'Message sent successfully',
  };
}

// ============================================
// Mutation Hook
// ============================================

export function useSendAgentMessage() {
  return useMutation({
    mutationFn: sendAgentMessage,
    
    onSuccess: (data) => {
      console.log('[useSendAgentMessage] Message sent:', data);
      // Don't show toast for every message - keeps UI clean
      // The streaming response will update the UI
    },
    
    onError: (error: Error) => {
      console.error('[useSendAgentMessage] Failed to send message:', error);
      toast.error('Failed to send message', {
        description: error.message,
      });
    },
  });
}