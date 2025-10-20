"""
SSE (Server-Sent Events) Manager for real-time workflow updates.

This module provides:
- SSE event streaming to frontend clients
- Automatic reconnection handling
- Event filtering and routing
- Event persistence for replay
- Integration with conversation history (Phase 9)
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, AsyncGenerator, Any
from uuid import UUID, uuid4

from sse_starlette import EventSourceResponse
from pydantic import BaseModel

from core.database import db_pool

logger = logging.getLogger(__name__)


class SSEEvent(BaseModel):
    """SSE event structure"""
    id: str
    event: str
    data: dict[str, Any]
    retry: Optional[int] = None  # Milliseconds for client retry


class SSEManager:
    """
    Manages SSE connections and event streaming.
    
    Features:
    - Event broadcasting to connected clients
    - Event filtering by workflow/project/session
    - Event persistence to database
    - Automatic client reconnection handling
    """
    
    def __init__(self):
        self._clients: dict[str, asyncio.Queue] = {}
        self._event_id_counter = 0
        
    def _generate_event_id(self) -> str:
        """Generate unique event ID for SSE."""
        self._event_id_counter += 1
        return f"{datetime.now().timestamp()}_{self._event_id_counter}"
    
    async def _persist_event(
        self,
        event_type: str,
        event_data: dict,
        workflow_execution_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Persist event to conversation_messages table for conversation history.
        
        Args:
            event_type: Type of SSE event
            event_data: Event data payload
            workflow_execution_id: Optional workflow reference
            project_id: Optional project reference
            session_id: Optional session reference
        """
        try:
            # Persist to conversation_messages only
            if project_id and session_id:
                query = """
                    INSERT INTO conversation_messages (
                        project_id, workflow_execution_id, session_id,
                        role, message_type, content, event_type, metadata
                    )
                    VALUES ($1, $2, $3, 'system', 'system_event', $4, $5, $6)
                """
                await db_pool.execute(
                    query,
                    project_id,
                    workflow_execution_id,
                    session_id,
                    json.dumps(event_data),
                    event_type,
                    json.dumps({"source": "sse_manager"})
                )
            
        except Exception as e:
            logger.error(f"Failed to persist SSE event {event_type}: {e}")
            # Don't fail the event send if persistence fails
    
    async def send_event(
        self,
        event_type: str,
        data: dict[str, Any],
        workflow_execution_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        persist: bool = True
    ) -> str:
        """
        Send SSE event to all connected clients.
        
        Args:
            event_type: Event type name (e.g., "workflow_created", "parser_started")
            data: Event data payload
            workflow_execution_id: Optional workflow reference for filtering
            project_id: Optional project reference for filtering
            session_id: Optional session reference for filtering
            persist: Whether to persist event to database (default: True)
            
        Returns:
            Event ID
        """
        event_id = self._generate_event_id()
        
        # Add metadata to event data
        enriched_data = {
            **data,
            "timestamp": datetime.now().isoformat(),
            "workflow_execution_id": str(workflow_execution_id) if workflow_execution_id else None,
            "project_id": str(project_id) if project_id else None,
            "session_id": session_id
        }
        
        event = SSEEvent(
            id=event_id,
            event=event_type,
            data=enriched_data,
            retry=3000  # 3 seconds retry for client reconnection
        )
        
        # Persist to database if enabled
        if persist:
            await self._persist_event(
                event_type,
                enriched_data,
                workflow_execution_id,
                project_id,
                session_id
            )
        
        # Broadcast to all connected clients
        # In production, filter by session_id/project_id
        disconnected_clients = []
        
        for client_id, queue in self._clients.items():
            try:
                await queue.put(event)
            except Exception as e:
                logger.warning(f"Failed to send event to client {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self._clients.pop(client_id, None)
            logger.info(f"Removed disconnected client: {client_id}")
        
        logger.debug(f"Sent SSE event {event_type} (id: {event_id}) to {len(self._clients)} clients")
        return event_id
    
    async def subscribe(
        self,
        session_id: str,
        last_event_id: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """
        Subscribe to SSE event stream.
        
        Args:
            session_id: Client session ID
            last_event_id: Last received event ID (for reconnection)
            
        Yields:
            SSE events as dictionaries
        """
        client_id = f"{session_id}_{uuid4().hex[:8]}"
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        self._clients[client_id] = queue
        logger.info(f"New SSE client connected: {client_id} (total: {len(self._clients)})")
        
        try:
            # If reconnecting, replay missed events
            if last_event_id:
                await self._replay_missed_events(queue, last_event_id)
            
            # Send initial connection event
            await queue.put(SSEEvent(
                id=self._generate_event_id(),
                event="connected",
                data={
                    "message": "SSE connection established",
                    "client_id": client_id,
                    "timestamp": datetime.now().isoformat()
                }
            ))
            
            # Stream events
            while True:
                event = await queue.get()
                
                # Format as SSE
                yield {
                    "id": event.id,
                    "event": event.event,
                    "data": json.dumps(event.data),
                    "retry": event.retry
                }
                
        except asyncio.CancelledError:
            logger.info(f"SSE client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Error in SSE stream for {client_id}: {e}")
        finally:
            # Clean up
            self._clients.pop(client_id, None)
            logger.info(f"Client {client_id} removed (remaining: {len(self._clients)})")
    
    async def _replay_missed_events(
        self,
        queue: asyncio.Queue,
        last_event_id: str
    ) -> None:
        """
        Replay events that were missed during disconnection.
        
        Args:
            queue: Client's event queue
            last_event_id: Last event ID client received
        """
        try:
            # Parse timestamp from event ID
            timestamp = float(last_event_id.split('_')[0])
            cutoff_time = datetime.fromtimestamp(timestamp)
            
            # Fetch missed events from conversation_messages table
            query = """
                SELECT event_type, content, created_at
                FROM conversation_messages
                WHERE created_at > $1
                    AND role = 'system'
                    AND message_type = 'system_event'
                ORDER BY created_at ASC
                LIMIT 100
            """
            
            rows = await db_pool.fetch(query, cutoff_time)
            
            if rows:
                logger.info(f"Replaying {len(rows)} missed events")
                
                for row in rows:
                    event = SSEEvent(
                        id=self._generate_event_id(),
                        event=row['event_type'],
                        data=json.loads(row['content'])
                    )
                    await queue.put(event)
                    
        except Exception as e:
            logger.error(f"Failed to replay missed events: {e}")
            # Continue streaming even if replay fails
    
    async def get_event_history(
        self,
        workflow_execution_id: UUID,
        limit: int = 100
    ) -> list[dict]:
        """
        Get event history for a workflow execution.
        
        Args:
            workflow_execution_id: Workflow execution ID
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        query = """
            SELECT id, event_type, content, created_at
            FROM conversation_messages
            WHERE workflow_execution_id = $1
                AND role = 'system'
                AND message_type = 'system_event'
            ORDER BY created_at DESC
            LIMIT $2
        """
        
        rows = await db_pool.fetch(query, workflow_execution_id, limit)
        
        return [
            {
                "id": str(row['id']),
                "event_type": row['event_type'],
                "data": json.loads(row['content']),
                "sent_at": row['created_at'].isoformat()
            }
            for row in rows
        ]
    
    def get_client_count(self) -> int:
        """Get number of connected clients."""
        return len(self._clients)
    
    async def disconnect_all(self) -> None:
        """Disconnect all clients (for shutdown)."""
        logger.info(f"Disconnecting all {len(self._clients)} SSE clients...")
        
        for client_id, queue in list(self._clients.items()):
            try:
                # Send disconnect event
                await queue.put(SSEEvent(
                    id=self._generate_event_id(),
                    event="server_shutdown",
                    data={
                        "message": "Server is shutting down",
                        "timestamp": datetime.now().isoformat()
                    }
                ))
            except Exception as e:
                logger.error(f"Error sending shutdown event to {client_id}: {e}")
        
        self._clients.clear()
        logger.info("All SSE clients disconnected")


# Global SSE manager instance
sse_manager = SSEManager()


def get_sse_manager() -> SSEManager:
    """
    Get the global SSE manager instance.
    
    Returns:
        Global SSEManager instance
    """
    return sse_manager


def create_sse_response(session_id: str, last_event_id: Optional[str] = None) -> EventSourceResponse:
    """
    Create SSE response for FastAPI endpoint.
    
    Usage:
        @app.get("/events")
        async def events(session_id: str, last_event_id: str = None):
            return create_sse_response(session_id, last_event_id)
    
    Args:
        session_id: Client session ID
        last_event_id: Last event ID for reconnection
        
    Returns:
        EventSourceResponse for streaming
    """
    return EventSourceResponse(
        sse_manager.subscribe(session_id, last_event_id),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )