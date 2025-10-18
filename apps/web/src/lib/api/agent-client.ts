/**
 * Agent Client Library - BFF Pattern Implementation
 * 
 * This library provides a unified interface for invoking AI agents in both
 * local (docker-compose) and remote (AWS AgentCore Runtime) environments.
 * 
 * Architecture:
 * - Local Mode: Direct HTTP calls to FastAPI endpoints (localhost:8001, localhost:8002)
 * - Remote Mode: AWS SDK calls to AgentCore Runtime with proper IAM authentication
 * 
 * Security:
 * - All agent invocations go through Next.js BFF API routes (not direct from client)
 * - AWS credentials are server-side only
 * - Client uses fetch to Next.js API routes which handle the actual agent calls
 */

import { 
  BedrockAgentCoreClient, 
  InvokeAgentRuntimeCommand,
  type InvokeAgentRuntimeCommandInput 
} from '@aws-sdk/client-bedrock-agentcore';

// ============================================
// Types
// ============================================

export type AgentMode = 'local' | 'remote';

export type AgentType = 'workflow' | 'ai-assistant';

export interface AgentInvocationPayload {
  project_id: string;
  user_id: string;
  session_id: string;
  start: boolean;
  user_input?: {
    chat?: string;
    content_edits?: Record<string, any>;
  };
}

export interface AgentConfig {
  mode: AgentMode;
  type: AgentType;
  // Local mode config
  localUrl?: string;
  // Remote mode config
  runtimeArn?: string;
  endpointName?: string;
  region?: string;
}

export interface StreamChunk {
  type: 'event' | 'data' | 'error' | 'complete';
  data?: any;
  error?: string;
}

// ============================================
// Session ID Generation
// ============================================

/**
 * Generates a unique session ID for agent conversations
 * Format: session-{timestamp}-{random}
 */
export function generateSessionId(): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 15);
  return `session-${timestamp}-${random}`;
}

// ============================================
// Environment Configuration
// ============================================

/**
 * Gets agent configuration from environment variables
 */
export function getAgentConfig(type: AgentType): AgentConfig {
  const mode = (process.env.NEXT_PUBLIC_AGENT_MODE || 'local') as AgentMode;
  
  if (mode === 'local') {
    const localUrl = type === 'workflow' 
      ? process.env.NEXT_PUBLIC_WORKFLOW_AGENT_URL || 'http://localhost:8001'
      : process.env.NEXT_PUBLIC_AI_ASSISTANT_AGENT_URL || 'http://localhost:8002';
    
    return {
      mode,
      type,
      localUrl,
    };
  }
  
  // Remote mode
  const runtimeArn = type === 'workflow'
    ? process.env.WORKFLOW_AGENT_RUNTIME_ARN
    : process.env.AI_ASSISTANT_AGENT_RUNTIME_ARN;
  
  const endpointName = type === 'workflow'
    ? process.env.WORKFLOW_AGENT_ENDPOINT_NAME || 'workflow-supervisor'
    : process.env.AI_ASSISTANT_AGENT_ENDPOINT_NAME || 'ai-assistant-supervisor';
  
  const region = process.env.AWS_REGION || 'ap-southeast-2';
  
  if (!runtimeArn) {
    throw new Error(`Missing ${type.toUpperCase()}_AGENT_RUNTIME_ARN for remote mode`);
  }
  
  return {
    mode,
    type,
    runtimeArn,
    endpointName,
    region,
  };
}

// ============================================
// Local Agent Client
// ============================================

/**
 * Invokes agent in local docker-compose environment
 */
async function invokeLocalAgent(
  config: AgentConfig,
  payload: AgentInvocationPayload
): Promise<Response> {
  if (!config.localUrl) {
    throw new Error('Local URL not configured');
  }
  
  const url = `${config.localUrl}/invocations`;
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Local agent invocation failed: ${response.status} ${errorText}`);
  }
  
  return response;
}

/**
 * Opens SSE stream to local agent
 */
export function streamLocalAgent(
  config: AgentConfig,
  projectId: string,
  workflowExecutionId: string
): EventSource {
  if (!config.localUrl) {
    throw new Error('Local URL not configured');
  }
  
  const url = new URL(`${config.localUrl}/invocations/stream`);
  url.searchParams.set('projectId', projectId);
  url.searchParams.set('workflowExecutionId', workflowExecutionId);
  
  return new EventSource(url.toString());
}

// ============================================
// Remote Agent Client (AWS SDK)
// ============================================

/**
 * Creates AWS SDK client for AgentCore
 * Server-side only - uses IAM credentials
 */
function createAgentCoreClient(region: string): BedrockAgentCoreClient {
  return new BedrockAgentCoreClient({
    region,
    // In production, credentials are provided by IAM role
    // In development, can use environment variables:
    // AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
  });
}

/**
 * Invokes agent in remote AWS AgentCore Runtime with SDK-based streaming
 * Server-side only
 *
 * This follows the AWS AgentCore pattern where:
 * 1. Session ID is passed via runtimeSessionId parameter
 * 2. Response is streamed as Server-Sent Events (SSE)
 * 3. Each event has "data:" prefix followed by JSON
 */
export async function invokeRemoteAgent(
  config: AgentConfig,
  payload: AgentInvocationPayload
): Promise<ReadableStream<Uint8Array>> {
  if (!config.runtimeArn || !config.region) {
    throw new Error('Remote agent configuration incomplete');
  }
  
  const client = createAgentCoreClient(config.region);
  
  // Encode payload as binary
  const payloadBytes = new TextEncoder().encode(JSON.stringify(payload));
  
  const input: InvokeAgentRuntimeCommandInput = {
    agentRuntimeArn: config.runtimeArn,
    runtimeSessionId: payload.session_id, // Session ID for conversation context
    payload: payloadBytes,
  };
  
  console.log('[Remote Agent] Invoking with session:', payload.session_id);
  
  const command = new InvokeAgentRuntimeCommand(input);
  const response = await client.send(command);
  
  if (!response.response) {
    throw new Error('No response stream received from AgentCore');
  }
  
  // Convert AWS SDK stream to Web ReadableStream with SSE formatting
  return convertAWSStreamToSSE(response.response);
}

/**
 * Stream version for POST endpoint - returns SSE formatted stream
 * This is the main function used by the BFF for remote mode streaming
 */
export async function invokeRemoteAgentStream(
  type: AgentType,
  payload: AgentInvocationPayload
): Promise<ReadableStream<Uint8Array>> {
  const config = getAgentConfig(type);
  
  if (config.mode !== 'remote') {
    throw new Error('invokeRemoteAgentStream should only be called in remote mode');
  }
  
  return invokeRemoteAgent(config, payload);
}

/**
 * Converts AWS SDK stream to Web ReadableStream with SSE format
 * Ensures each event has "data:" prefix for proper SSE parsing
 */
async function convertAWSStreamToSSE(
  awsStream: unknown
): Promise<ReadableStream<Uint8Array>> {
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  
  return new ReadableStream({
    async start(controller) {
      try {
        // AWS SDK stream is AsyncIterable
        const stream = awsStream as AsyncIterable<Uint8Array>;
        
        for await (const chunk of stream) {
          // Decode the chunk
          const text = decoder.decode(chunk, { stream: true });
          
          // Parse if JSON and re-format with SSE prefix
          try {
            const event = JSON.parse(text);
            // Format as SSE: "data: {json}\n\n"
            const sseData = `data: ${JSON.stringify(event)}\n\n`;
            controller.enqueue(encoder.encode(sseData));
          } catch {
            // Not JSON, send as-is but ensure it has data: prefix if it doesn't
            if (!text.startsWith('data:')) {
              const sseData = `data: ${text}\n\n`;
              controller.enqueue(encoder.encode(sseData));
            } else {
              controller.enqueue(chunk);
            }
          }
        }
        
        controller.close();
      } catch (error) {
        console.error('[Stream Conversion] Error:', error);
        controller.error(error);
      }
    }
  });
}

// ============================================
// Unified Client Interface
// ============================================

/**
 * Invokes an agent with automatic mode detection
 * This function should be called from Next.js API routes only (server-side)
 */
export async function invokeAgent(
  type: AgentType,
  payload: AgentInvocationPayload
): Promise<Response | ReadableStream<Uint8Array>> {
  const config = getAgentConfig(type);
  
  if (config.mode === 'local') {
    return invokeLocalAgent(config, payload);
  } else {
    return invokeRemoteAgent(config, payload);
  }
}

/**
 * Opens an SSE stream for agent updates
 * For local mode, connects directly to agent SSE endpoint
 * For remote mode, should connect through BFF proxy
 */
export function streamAgent(
  type: AgentType,
  projectId: string,
  workflowExecutionId: string
): EventSource | null {
  const config = getAgentConfig(type);
  
  if (config.mode === 'local') {
    return streamLocalAgent(config, projectId, workflowExecutionId);
  } else {
    // For remote mode, streaming is handled through the BFF proxy
    // Return null - client should use BFF route instead
    return null;
  }
}

// ============================================
// Error Handling Utilities
// ============================================

export class AgentInvocationError extends Error {
  constructor(
    message: string,
    public readonly type: 'validation' | 'not_found' | 'access_denied' | 'throttling' | 'unknown',
    public readonly originalError?: Error
  ) {
    super(message);
    this.name = 'AgentInvocationError';
  }
}

/**
 * Parses AWS SDK errors into structured error types
 */
export function parseAgentError(error: any): AgentInvocationError {
  const errorName = error.name || error.__type || 'Unknown';
  const errorMessage = error.message || 'Unknown error';
  
  switch (errorName) {
    case 'ValidationException':
      return new AgentInvocationError(
        `Invalid request: ${errorMessage}`,
        'validation',
        error
      );
    case 'ResourceNotFoundException':
      return new AgentInvocationError(
        `Agent not found: ${errorMessage}`,
        'not_found',
        error
      );
    case 'AccessDeniedException':
      return new AgentInvocationError(
        `Access denied: ${errorMessage}`,
        'access_denied',
        error
      );
    case 'ThrottlingException':
      return new AgentInvocationError(
        `Rate limit exceeded: ${errorMessage}`,
        'throttling',
        error
      );
    default:
      return new AgentInvocationError(
        `Agent invocation failed: ${errorMessage}`,
        'unknown',
        error
      );
  }
}

// ============================================
// Retry Logic
// ============================================

export interface RetryOptions {
  maxAttempts?: number;
  initialDelay?: number;
  maxDelay?: number;
  backoffMultiplier?: number;
}

const defaultRetryOptions: Required<RetryOptions> = {
  maxAttempts: 3,
  initialDelay: 1000,
  maxDelay: 30000,
  backoffMultiplier: 2,
};

/**
 * Retries agent invocation with exponential backoff
 */
export async function invokeAgentWithRetry(
  type: AgentType,
  payload: AgentInvocationPayload,
  options: RetryOptions = {}
): Promise<Response | ReadableStream<Uint8Array>> {
  const opts = { ...defaultRetryOptions, ...options };
  let lastError: Error | null = null;
  
  for (let attempt = 1; attempt <= opts.maxAttempts; attempt++) {
    try {
      return await invokeAgent(type, payload);
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      
      // Don't retry on validation or access errors
      if (error instanceof AgentInvocationError) {
        if (error.type === 'validation' || error.type === 'access_denied' || error.type === 'not_found') {
          throw error;
        }
      }
      
      // Calculate delay with exponential backoff
      if (attempt < opts.maxAttempts) {
        const delay = Math.min(
          opts.initialDelay * Math.pow(opts.backoffMultiplier, attempt - 1),
          opts.maxDelay
        );
        
        console.warn(`Agent invocation attempt ${attempt} failed, retrying in ${delay}ms...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  
  throw lastError || new Error('Agent invocation failed after all retry attempts');
}