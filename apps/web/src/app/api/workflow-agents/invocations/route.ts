/**
 * BFF API Route: Agent Invocations
 *
 * This Backend-for-Frontend (BFF) route handles all agent invocations
 * for both Workflow and AI Assistant agents. It provides:
 *
 * 1. POST /api/workflow-agents/invocations
 *    - Invokes agents with proper payload validation and session ID management
 *    - Local mode: URL-based streaming to Docker FastAPI endpoints
 *    - Remote mode: AWS SDK-based streaming to AgentCore Runtime
 *    - Returns Server-Sent Events (SSE) stream with "data:" prefix format
 *
 * Session ID Management:
 * - Session IDs follow AWS AgentCore pattern: session-{timestamp}-{random}
 * - Passed via X-Amzn-Bedrock-AgentCore-Runtime-Session-Id header (remote)
 * - Included in payload for local mode
 * - Maintains conversation context across multiple invocations
 *
 * Security:
 * - All AWS SDK calls happen server-side only
 * - Client credentials never exposed to frontend
 * - Authentication via Cognito tokens (future enhancement)
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  invokeAgentWithRetry,
  generateSessionId,
  parseAgentError,
  AgentInvocationError,
  type AgentInvocationPayload,
  type AgentType,
  getAgentConfig,
  invokeRemoteAgentStream,
} from '@/lib/api/agent-client';

// ============================================
// Types
// ============================================

interface InvocationRequestBody extends AgentInvocationPayload {
  agent_type?: AgentType; // Optional, defaults to 'workflow'
}

// ============================================
// POST Handler: Invoke Agent
// ============================================

export async function POST(request: NextRequest) {
  try {
    // Parse request body
    const body: InvocationRequestBody = await request.json();
    
    // Validate required fields
    const { project_id, user_id, session_id, start, user_input, agent_type = 'workflow' } = body;
    
    if (!project_id) {
      return NextResponse.json(
        { error: 'Missing required field: project_id' },
        { status: 400 }
      );
    }
    
    if (!user_id) {
      return NextResponse.json(
        { error: 'Missing required field: user_id' },
        { status: 400 }
      );
    }
    
    // Generate session ID if not provided
    const sessionId = session_id || generateSessionId();
    
    // Prepare agent payload
    const payload: AgentInvocationPayload = {
      project_id,
      user_id,
      session_id: sessionId,
      start: start ?? false,
      user_input,
    };
    
    // Get agent configuration to determine mode
    const config = getAgentConfig(agent_type);
    
    // Log mode with clear visual indicator
    console.log(`\n${'='.repeat(60)}`);
    console.log(`🤖 AGENT MODE: ${config.mode.toUpperCase()}`);
    console.log(`📋 Agent Type: ${agent_type}`);
    console.log(`${config.mode === 'local' ? '🏠 Local URL: ' + config.localUrl : '☁️  Runtime ARN: ' + config.runtimeArn}`);
    console.log(`${'='.repeat(60)}\n`);
    
    console.log(`[BFF] Invoking ${agent_type} agent in ${config.mode} mode`, {
      project_id,
      user_id,
      session_id: sessionId,
      start: payload.start,
    });
    
    // Invoke agent based on mode (local vs remote)
    if (config.mode === 'local') {
      // Local mode: URL-based streaming to Docker FastAPI
      console.log(`[BFF] 🏠 LOCAL MODE: URL-based streaming to ${config.localUrl}`);
      
      const response = await invokeAgentWithRetry(agent_type, payload, {
        maxAttempts: 3,
        initialDelay: 1000,
      });
      
      if (response instanceof Response) {
        const contentType = response.headers.get('content-type') || '';
        
        // Streaming response - proxy it through
        if (contentType.includes('text/event-stream') || contentType.includes('application/x-ndjson')) {
          return new NextResponse(response.body, {
            status: 200,
            headers: {
              'Content-Type': 'text/event-stream',
              'Cache-Control': 'no-cache',
              'Connection': 'keep-alive',
              'X-Accel-Buffering': 'no', // Disable nginx buffering
            },
          });
        }
        
        // JSON response
        const data = await response.json();
        return NextResponse.json(data, { status: 200 });
      }
      
      throw new Error('Unexpected response type from local agent');
    } else {
      // Remote mode: AWS SDK-based streaming to AgentCore Runtime
      console.log(`[BFF] ☁️  REMOTE MODE: AWS SDK-based streaming to AgentCore Runtime`);
      
      const stream = await invokeRemoteAgentStream(agent_type, payload);
      
      // Return SSE stream with proper headers
      return new NextResponse(stream, {
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no', // Disable nginx buffering
        },
      });
    }
    
  } catch (error) {
    console.error('[BFF] Agent invocation error:', error);
    
    // Handle structured errors
    if (error instanceof AgentInvocationError) {
      const statusCode = getStatusCodeForErrorType(error.type);
      return NextResponse.json(
        {
          error: error.message,
          type: error.type,
        },
        { status: statusCode }
      );
    }
    
    // Parse AWS SDK errors
    const parsedError = parseAgentError(error);
    const statusCode = getStatusCodeForErrorType(parsedError.type);
    
    return NextResponse.json(
      {
        error: parsedError.message,
        type: parsedError.type,
      },
      { status: statusCode }
    );
  }
}

// ============================================
// Note: GET endpoint removed
// ============================================
// All streaming now happens through POST endpoint with immediate SSE response.
// This follows AWS AgentCore pattern where invocation and streaming are combined.
// Frontend uses POST with immediate ReadableStream response (SSE format).

// ============================================
// Utility Functions
// ============================================

/**
 * Maps error types to HTTP status codes
 */
function getStatusCodeForErrorType(
  type: 'validation' | 'not_found' | 'access_denied' | 'throttling' | 'unknown'
): number {
  switch (type) {
    case 'validation':
      return 400;
    case 'not_found':
      return 404;
    case 'access_denied':
      return 403;
    case 'throttling':
      return 429;
    case 'unknown':
    default:
      return 500;
  }
}

// ============================================
// Route Configuration
// ============================================

// Disable body size limit for file uploads
export const config = {
  api: {
    bodyParser: {
      sizeLimit: '100mb',
    },
  },
};

// Enable edge runtime for better streaming performance (optional)
// export const runtime = 'edge';