"""
Conversation History Manager for Phase 9.

This module provides:
- Conversation persistence (user inputs + agent responses)
- Conversation retrieval with pagination
- SSE event replay functionality
- Audit trail for workflow execution
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from core.database import db_pool

logger = logging.getLogger(__name__)

# Message types
MessageRole = Literal["user", "agent", "system"]
MessageType = Literal["chat", "content_edit", "agent_output", "system_event"]


class ConversationMessage(BaseModel):
    """Conversation message structure"""
    id: Optional[UUID] = None
    project_id: UUID
    workflow_execution_id: Optional[UUID] = None
    session_id: str
    user_id: Optional[UUID] = None
    
    # Message details
    role: MessageRole = Field(description="Who sent the message")
    message_type: MessageType = Field(description="Type of message")
    content: str = Field(description="Message content (text or JSON)")
    
    # Metadata
    agent_name: Optional[str] = Field(None, description="Agent name if role=agent")
    event_type: Optional[str] = Field(None, description="SSE event type if system")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConversationThread(BaseModel):
    """Complete conversation thread for a project"""
    project_id: UUID
    workflow_execution_id: Optional[UUID] = None
    total_messages: int
    messages: List[ConversationMessage]
    
    # Pagination
    page: int = 1
    page_size: int = 50
    has_more: bool = False


class ConversationManager:
    """
    Manages conversation history persistence and retrieval.
    
    Features:
    - Store user inputs (chat, content edits)
    - Store agent responses (all SSE events)
    - Retrieve conversation with pagination
    - Replay SSE events for workflow
    - Search conversations
    """
    
    @staticmethod
    async def add_user_message(
        project_id: UUID,
        session_id: str,
        user_id: UUID,
        content: str,
        message_type: Literal["chat", "content_edit"] = "chat",
        workflow_execution_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Add user message to conversation history.
        
        Args:
            project_id: Project ID
            session_id: Session ID
            user_id: User ID
            content: Message content
            message_type: Type of user input
            workflow_execution_id: Optional workflow ID
            metadata: Optional additional data
            
        Returns:
            Message ID
        """
        try:
            query = """
                INSERT INTO conversation_messages (
                    project_id, workflow_execution_id, session_id, user_id,
                    role, message_type, content, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """
            
            result = await db_pool.fetchrow(
                query,
                project_id,
                workflow_execution_id,
                session_id,
                user_id,
                "user",
                message_type,
                content,
                json.dumps(metadata or {})
            )
            
            message_id = result['id']
            logger.info(f"User message added: {message_id} (project: {project_id})")
            return message_id
            
        except Exception as e:
            logger.error(f"Failed to add user message: {e}")
            raise
    
    @staticmethod
    async def add_agent_message(
        project_id: UUID,
        session_id: str,
        agent_name: str,
        content: str,
        workflow_execution_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        message_type: Literal["agent_output", "system_event"] = "agent_output",
        event_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Add agent message to conversation history.
        
        Args:
            project_id: Project ID
            session_id: Session ID
            agent_name: Name of agent
            content: Message content
            workflow_execution_id: Optional workflow ID
            user_id: Optional user ID
            message_type: Type of message
            event_type: Optional SSE event type
            metadata: Optional additional data
            
        Returns:
            Message ID
        """
        try:
            query = """
                INSERT INTO conversation_messages (
                    project_id, workflow_execution_id, session_id, user_id,
                    role, message_type, content, agent_name, event_type, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
            """
            
            result = await db_pool.fetchrow(
                query,
                project_id,
                workflow_execution_id,
                session_id,
                user_id,
                "agent",
                message_type,
                content,
                agent_name,
                event_type,
                json.dumps(metadata or {})
            )
            
            message_id = result['id']
            logger.debug(f"Agent message added: {message_id} (agent: {agent_name})")
            return message_id
            
        except Exception as e:
            logger.error(f"Failed to add agent message: {e}")
            raise
    
    @staticmethod
    async def add_system_message(
        project_id: UUID,
        session_id: str,
        content: str,
        event_type: str,
        workflow_execution_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Add system message (SSE event) to conversation history.
        
        Args:
            project_id: Project ID
            session_id: Session ID
            content: Event data as JSON
            event_type: SSE event type
            workflow_execution_id: Optional workflow ID
            metadata: Optional additional data
            
        Returns:
            Message ID
        """
        try:
            query = """
                INSERT INTO conversation_messages (
                    project_id, workflow_execution_id, session_id,
                    role, message_type, content, event_type, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """
            
            result = await db_pool.fetchrow(
                query,
                project_id,
                workflow_execution_id,
                session_id,
                "system",
                "system_event",
                content,
                event_type,
                json.dumps(metadata or {})
            )
            
            message_id = result['id']
            logger.debug(f"System message added: {message_id} (event: {event_type})")
            return message_id
            
        except Exception as e:
            logger.error(f"Failed to add system message: {e}")
            raise
    
    @staticmethod
    async def get_conversation(
        project_id: UUID,
        workflow_execution_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 50,
        include_system_events: bool = True
    ) -> ConversationThread:
        """
        Retrieve conversation history with pagination.
        
        Args:
            project_id: Project ID
            workflow_execution_id: Optional workflow ID filter
            page: Page number (1-indexed)
            page_size: Messages per page
            include_system_events: Include system messages
            
        Returns:
            ConversationThread with messages
        """
        try:
            # Build query
            base_query = """
                SELECT id, project_id, workflow_execution_id, session_id, user_id,
                       role, message_type, content, agent_name, event_type, metadata,
                       created_at
                FROM conversation_messages
                WHERE project_id = $1
            """
            
            params: List[Any] = [project_id]
            param_idx = 2
            
            if workflow_execution_id:
                base_query += f" AND workflow_execution_id = ${param_idx}"
                params.append(workflow_execution_id)
                param_idx += 1
            
            if not include_system_events:
                base_query += f" AND role != 'system'"
            
            # Count total
            count_query = f"SELECT COUNT(*) as total FROM ({base_query}) as filtered"
            count_result = await db_pool.fetchrow(count_query, *params)
            total_messages = count_result['total']
            
            # Get paginated messages
            offset = (page - 1) * page_size
            paginated_query = f"""
                {base_query}
                ORDER BY created_at ASC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            params.extend([page_size, offset])
            
            rows = await db_pool.fetch(paginated_query, *params)
            
            # Convert to messages
            messages = []
            for row in rows:
                messages.append(ConversationMessage(
                    id=row['id'],
                    project_id=row['project_id'],
                    workflow_execution_id=row['workflow_execution_id'],
                    session_id=row['session_id'],
                    user_id=row['user_id'],
                    role=row['role'],
                    message_type=row['message_type'],
                    content=row['content'],
                    agent_name=row['agent_name'],
                    event_type=row['event_type'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    created_at=row['created_at']
                ))
            
            has_more = (offset + len(messages)) < total_messages
            
            thread = ConversationThread(
                project_id=project_id,
                workflow_execution_id=workflow_execution_id,
                total_messages=total_messages,
                messages=messages,
                page=page,
                page_size=page_size,
                has_more=has_more
            )
            
            logger.info(
                f"Retrieved conversation: project={project_id}, "
                f"messages={len(messages)}/{total_messages}, page={page}"
            )
            
            return thread
            
        except Exception as e:
            logger.error(f"Failed to retrieve conversation: {e}")
            raise
    
    @staticmethod
    async def get_workflow_events(
        workflow_execution_id: UUID,
        event_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all SSE events for a workflow (for replay).
        
        Args:
            workflow_execution_id: Workflow ID
            event_types: Optional filter by event types
            
        Returns:
            List of event dictionaries
        """
        try:
            query = """
                SELECT event_type, content, metadata, created_at
                FROM conversation_messages
                WHERE workflow_execution_id = $1
                  AND role = 'system'
                  AND message_type = 'system_event'
            """
            
            params: List[Any] = [workflow_execution_id]
            
            if event_types:
                placeholders = ', '.join(f'${i+2}' for i in range(len(event_types)))
                query += f" AND event_type IN ({placeholders})"
                params.extend(event_types)
            
            query += " ORDER BY created_at ASC"
            
            rows = await db_pool.fetch(query, *params)
            
            events = []
            for row in rows:
                events.append({
                    "event_type": row['event_type'],
                    "data": json.loads(row['content']) if row['content'] else {},
                    "metadata": json.loads(row['metadata']) if row['metadata'] else {},
                    "timestamp": row['created_at'].isoformat()
                })
            
            logger.info(f"Retrieved {len(events)} events for workflow {workflow_execution_id}")
            return events
            
        except Exception as e:
            logger.error(f"Failed to retrieve workflow events: {e}")
            raise
    
    @staticmethod
    async def search_conversations(
        project_id: UUID,
        query: str,
        limit: int = 20
    ) -> List[ConversationMessage]:
        """
        Search conversation messages by content.
        
        Args:
            project_id: Project ID
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching messages
        """
        try:
            sql_query = """
                SELECT id, project_id, workflow_execution_id, session_id, user_id,
                       role, message_type, content, agent_name, event_type, metadata,
                       created_at,
                       ts_rank(to_tsvector('english', content), plainto_tsquery('english', $2)) as rank
                FROM conversation_messages
                WHERE project_id = $1
                  AND to_tsvector('english', content) @@ plainto_tsquery('english', $2)
                ORDER BY rank DESC, created_at DESC
                LIMIT $3
            """
            
            rows = await db_pool.fetch(sql_query, project_id, query, limit)
            
            messages = []
            for row in rows:
                messages.append(ConversationMessage(
                    id=row['id'],
                    project_id=row['project_id'],
                    workflow_execution_id=row['workflow_execution_id'],
                    session_id=row['session_id'],
                    user_id=row['user_id'],
                    role=row['role'],
                    message_type=row['message_type'],
                    content=row['content'],
                    agent_name=row['agent_name'],
                    event_type=row['event_type'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    created_at=row['created_at']
                ))
            
            logger.info(f"Search found {len(messages)} messages for query: {query}")
            return messages
            
        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
            raise
    
    @staticmethod
    async def delete_conversation(
        project_id: UUID,
        workflow_execution_id: Optional[UUID] = None
    ) -> int:
        """
        Delete conversation messages.
        
        Args:
            project_id: Project ID
            workflow_execution_id: Optional workflow ID (deletes all if None)
            
        Returns:
            Number of messages deleted
        """
        try:
            if workflow_execution_id:
                query = """
                    DELETE FROM conversation_messages
                    WHERE project_id = $1 AND workflow_execution_id = $2
                """
                result = await db_pool.execute(query, project_id, workflow_execution_id)
            else:
                query = """
                    DELETE FROM conversation_messages
                    WHERE project_id = $1
                """
                result = await db_pool.execute(query, project_id)
            
            # Extract count from result string like "DELETE 42"
            count = int(result.split()[-1]) if result else 0
            
            logger.info(f"Deleted {count} messages for project {project_id}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            raise


# Global conversation manager instance
conversation_manager = ConversationManager()


# Convenience functions
async def add_user_input(
    project_id: UUID,
    session_id: str,
    user_id: UUID,
    content: str,
    message_type: Literal["chat", "content_edit"] = "chat",
    workflow_execution_id: Optional[UUID] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> UUID:
    """Add user input to conversation."""
    return await conversation_manager.add_user_message(
        project_id, session_id, user_id, content,
        message_type, workflow_execution_id, metadata
    )


async def add_agent_response(
    project_id: UUID,
    session_id: str,
    agent_name: str,
    content: str,
    workflow_execution_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> UUID:
    """Add agent response to conversation."""
    return await conversation_manager.add_agent_message(
        project_id, session_id, agent_name, content,
        workflow_execution_id, user_id, "agent_output", None, metadata
    )


async def add_sse_event(
    project_id: UUID,
    session_id: str,
    event_type: str,
    event_data: Dict[str, Any],
    workflow_execution_id: Optional[UUID] = None
) -> UUID:
    """Add SSE event to conversation."""
    return await conversation_manager.add_system_message(
        project_id, session_id, json.dumps(event_data),
        event_type, workflow_execution_id
    )


async def get_project_conversation(
    project_id: UUID,
    page: int = 1,
    page_size: int = 50
) -> ConversationThread:
    """Get conversation for project."""
    return await conversation_manager.get_conversation(
        project_id, page=page, page_size=page_size
    )


async def get_workflow_conversation(
    workflow_execution_id: UUID,
    page: int = 1,
    page_size: int = 50
) -> ConversationThread:
    """Get conversation for specific workflow."""
    # Need to get project_id first
    query = "SELECT project_id FROM workflow_executions WHERE id = $1"
    row = await db_pool.fetchrow(query, workflow_execution_id)
    
    if not row:
        raise ValueError(f"Workflow {workflow_execution_id} not found")
    
    return await conversation_manager.get_conversation(
        row['project_id'],
        workflow_execution_id=workflow_execution_id,
        page=page,
        page_size=page_size
    )