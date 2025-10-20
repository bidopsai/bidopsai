"""
Consolidated database tools for agent operations.

Provides all database CRUD operations needed by agents to interact with
the PostgreSQL database for projects, workflows, tasks, artifacts, etc.

These tools use the @tool decorator for proper Strands Agent integration.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from strands import tool

from core.database import get_database_manager

logger = logging.getLogger(__name__)


# ==============================================================================
# PROJECT TOOLS
# ==============================================================================

@tool
async def get_project(project_id: str) -> Dict[str, Any]:
    """
    Get project by ID from the database.
    
    Args:
        project_id: Project UUID as string
        
    Returns:
        Project data as dictionary including name, status, progress, metadata
    """
    db = get_database_manager()
    
    query = """
        SELECT id, name, description, status, value, deadline,
               progress_percentage, created_by, completed_by,
               created_at, updated_at, completed_at, metadata
        FROM projects
        WHERE id = $1
    """
    
    row = await db.fetch_one(query, UUID(project_id))
    
    if not row:
        raise ValueError(f"Project {project_id} not found")
    
    return dict(row)


@tool
async def update_project(
    project_id: str,
    status: Optional[str] = None,
    progress_percentage: Optional[int] = None,
    completed_by: Optional[str] = None,
    completed_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update project fields.
    
    Args:
        project_id: Project UUID
        status: New status (OPEN/INPROGRESS/COMPLETED/CANCELLED)
        progress_percentage: Progress (0-100)
        completed_by: User UUID who completed
        completed_at: Completion timestamp
        metadata: Additional metadata
        
    Returns:
        Updated project data
    """
    db = get_database_manager()
    
    # Build dynamic update query
    updates = ["updated_at = CURRENT_TIMESTAMP"]
    params = [UUID(project_id)]
    param_idx = 2
    
    if status is not None:
        updates.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1
    
    if progress_percentage is not None:
        updates.append(f"progress_percentage = ${param_idx}")
        params.append(progress_percentage)
        param_idx += 1
    
    if completed_by is not None:
        updates.append(f"completed_by = ${param_idx}")
        params.append(UUID(completed_by))
        param_idx += 1
    
    if completed_at is not None:
        updates.append(f"completed_at = ${param_idx}")
        params.append(datetime.fromisoformat(completed_at))
        param_idx += 1
    
    if metadata is not None:
        updates.append(f"metadata = ${param_idx}")
        params.append(json.dumps(metadata))
        param_idx += 1
    
    query = f"""
        UPDATE projects
        SET {', '.join(updates)}
        WHERE id = $1
        RETURNING *
    """
    
    row = await db.fetch_one(query, *params)
    return dict(row)


@tool
async def get_project_documents(
    project_id: str,
    parsing_status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get project documents.
    
    Args:
        project_id: Project UUID
        parsing_status: Filter by parsing status (PENDING/PROCESSING/COMPLETED/FAILED)
        
    Returns:
        List of project documents
    """
    db = get_database_manager()
    
    if parsing_status:
        query = """
            SELECT * FROM project_documents
            WHERE project_id = $1 AND parsing_status = $2
            ORDER BY uploaded_at DESC
        """
        rows = await db.fetch_all(query, UUID(project_id), parsing_status)
    else:
        query = """
            SELECT * FROM project_documents
            WHERE project_id = $1
            ORDER BY uploaded_at DESC
        """
        rows = await db.fetch_all(query, UUID(project_id))
    
    return [dict(row) for row in rows]


@tool
async def update_project_document(
    document_id: str,
    processed_file_location: Optional[str] = None,
    parsing_status: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update project document.
    
    Args:
        document_id: Document UUID
        processed_file_location: S3 location of processed file
        parsing_status: New parsing status
        metadata: Additional metadata
        
    Returns:
        Updated document data
    """
    db = get_database_manager()
    
    updates = []
    params = [UUID(document_id)]
    param_idx = 2
    
    if processed_file_location is not None:
        updates.append(f"processed_file_location = ${param_idx}")
        params.append(processed_file_location)
        param_idx += 1
    
    if parsing_status is not None:
        updates.append(f"parsing_status = ${param_idx}")
        params.append(parsing_status)
        param_idx += 1
    
    if metadata is not None:
        updates.append(f"metadata = ${param_idx}")
        params.append(json.dumps(metadata))
        param_idx += 1
    
    query = f"""
        UPDATE project_documents
        SET {', '.join(updates)}
        WHERE id = $1
        RETURNING *
    """
    
    row = await db.fetch_one(query, *params)
    return dict(row)


# ==============================================================================
# WORKFLOW TOOLS
# ==============================================================================

@tool
async def create_workflow_execution(
    project_id: str,
    session_id: str,
    initiated_by: str,
    workflow_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create new workflow execution.
    
    Args:
        project_id: Project UUID
        session_id: AgentCore session ID
        initiated_by: User UUID
        workflow_config: Workflow configuration
        
    Returns:
        Created workflow execution
    """
    db = get_database_manager()
    
    query = """
        INSERT INTO workflow_executions (
            project_id, session_id, status, initiated_by,
            started_at, last_updated_at, workflow_config
        )
        VALUES ($1, $2, 'OPEN', $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, $4)
        RETURNING *
    """
    
    row = await db.fetch_one(
        query,
        UUID(project_id),
        session_id,
        UUID(initiated_by),
        json.dumps(workflow_config) if workflow_config else None
    )
    
    return dict(row)


@tool
async def get_workflow_execution(workflow_execution_id: str) -> Dict[str, Any]:
    """Get workflow execution by ID."""
    db = get_database_manager()
    
    query = "SELECT * FROM workflow_executions WHERE id = $1"
    row = await db.fetch_one(query, UUID(workflow_execution_id))
    
    if not row:
        raise ValueError(f"Workflow execution {workflow_execution_id} not found")
    
    return dict(row)


@tool
async def update_workflow_execution(
    workflow_execution_id: str,
    status: Optional[str] = None,
    handled_by: Optional[str] = None,
    completed_by: Optional[str] = None,
    completed_at: Optional[str] = None,
    results: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    error_log: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Update workflow execution."""
    db = get_database_manager()
    
    updates = ["last_updated_at = CURRENT_TIMESTAMP"]
    params = [UUID(workflow_execution_id)]
    param_idx = 2
    
    if status is not None:
        updates.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1
    
    if handled_by is not None:
        updates.append(f"handled_by = ${param_idx}")
        params.append(UUID(handled_by))
        param_idx += 1
    
    if completed_by is not None:
        updates.append(f"completed_by = ${param_idx}")
        params.append(UUID(completed_by))
        param_idx += 1
    
    if completed_at is not None:
        updates.append(f"completed_at = ${param_idx}")
        params.append(datetime.fromisoformat(completed_at))
        param_idx += 1
    
    if results is not None:
        updates.append(f"results = ${param_idx}")
        params.append(json.dumps(results))
        param_idx += 1
    
    if error_message is not None:
        updates.append(f"error_message = ${param_idx}")
        params.append(error_message)
        param_idx += 1
    
    if error_log is not None:
        updates.append(f"error_log = ${param_idx}")
        params.append(json.dumps(error_log))
        param_idx += 1
    
    query = f"""
        UPDATE workflow_executions
        SET {', '.join(updates)}
        WHERE id = $1
        RETURNING *
    """
    
    row = await db.fetch_one(query, *params)
    return dict(row)


@tool
async def create_agent_task(
    workflow_execution_id: str,
    agent: str,
    sequence_order: int,
    initiated_by: str,
    input_data: Optional[Dict[str, Any]] = None,
    task_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create new agent task."""
    db = get_database_manager()
    
    query = """
        INSERT INTO agent_tasks (
            workflow_execution_id, agent, sequence_order, status,
            initiated_by, input_data, task_config
        )
        VALUES ($1, $2, $3, 'OPEN', $4, $5, $6)
        RETURNING *
    """
    
    row = await db.fetch_one(
        query,
        UUID(workflow_execution_id),
        agent,
        sequence_order,
        UUID(initiated_by),
        json.dumps(input_data) if input_data else None,
        json.dumps(task_config) if task_config else None
    )
    
    return dict(row)


@tool
async def get_agent_task(task_id: str) -> Dict[str, Any]:
    """Get agent task by ID."""
    db = get_database_manager()
    
    query = "SELECT * FROM agent_tasks WHERE id = $1"
    row = await db.fetch_one(query, UUID(task_id))
    
    if not row:
        raise ValueError(f"Agent task {task_id} not found")
    
    return dict(row)


@tool
async def get_agent_tasks_by_workflow(
    workflow_execution_id: str,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get all agent tasks for a workflow."""
    db = get_database_manager()
    
    if status:
        query = """
            SELECT * FROM agent_tasks
            WHERE workflow_execution_id = $1 AND status = $2
            ORDER BY sequence_order
        """
        rows = await db.fetch_all(query, UUID(workflow_execution_id), status)
    else:
        query = """
            SELECT * FROM agent_tasks
            WHERE workflow_execution_id = $1
            ORDER BY sequence_order
        """
        rows = await db.fetch_all(query, UUID(workflow_execution_id))
    
    return [dict(row) for row in rows]


@tool
async def update_agent_task(
    task_id: str,
    status: Optional[str] = None,
    handled_by: Optional[str] = None,
    completed_by: Optional[str] = None,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    output_data: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    error_log: Optional[List[Dict[str, Any]]] = None,
    retry_count: Optional[int] = None,
    execution_time_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Update agent task."""
    db = get_database_manager()
    
    updates = []
    params = [UUID(task_id)]
    param_idx = 2
    
    if status is not None:
        updates.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1
    
    if handled_by is not None:
        updates.append(f"handled_by = ${param_idx}")
        params.append(UUID(handled_by))
        param_idx += 1
    
    if completed_by is not None:
        updates.append(f"completed_by = ${param_idx}")
        params.append(UUID(completed_by))
        param_idx += 1
    
    if started_at is not None:
        updates.append(f"started_at = ${param_idx}")
        params.append(datetime.fromisoformat(started_at))
        param_idx += 1
    
    if completed_at is not None:
        updates.append(f"completed_at = ${param_idx}")
        params.append(datetime.fromisoformat(completed_at))
        param_idx += 1
    
    if output_data is not None:
        updates.append(f"output_data = ${param_idx}")
        params.append(json.dumps(output_data))
        param_idx += 1
    
    if error_message is not None:
        updates.append(f"error_message = ${param_idx}")
        params.append(error_message)
        param_idx += 1
    
    if error_log is not None:
        updates.append(f"error_log = ${param_idx}")
        params.append(json.dumps(error_log))
        param_idx += 1
    
    if retry_count is not None:
        updates.append(f"retry_count = ${param_idx}")
        params.append(retry_count)
        param_idx += 1
    
    if execution_time_seconds is not None:
        updates.append(f"execution_time_seconds = ${param_idx}")
        params.append(execution_time_seconds)
        param_idx += 1
    
    query = f"""
        UPDATE agent_tasks
        SET {', '.join(updates)}
        WHERE id = $1
        RETURNING *
    """
    
    row = await db.fetch_one(query, *params)
    return dict(row)


@tool
async def reset_agent_tasks(
    workflow_execution_id: str,
    agent_names: List[str],
    reset_by: str
) -> List[Dict[str, Any]]:
    """
    Reset agent tasks back to OPEN status for retry.
    
    This is used when validation fails (compliance/QA) and we need to
    re-run certain agent tasks. The supervisor calls this to reset
    the DB state before routing back to the failed agent.
    
    Args:
        workflow_execution_id: Workflow execution ID
        agent_names: List of agent names to reset (e.g., ["content", "compliance", "qa"])
        reset_by: User ID who triggered the reset
        
    Returns:
        List of reset agent tasks
    """
    db = get_database_manager()
    
    query = """
        UPDATE agent_tasks
        SET
            status = 'OPEN',
            handled_by = NULL,
            completed_by = NULL,
            started_at = NULL,
            completed_at = NULL,
            output_data = NULL,
            error_message = NULL,
            error_log = NULL,
            execution_time_seconds = NULL
        WHERE workflow_execution_id = $1
        AND agent = ANY($2)
        RETURNING *
    """
    
    rows = await db.fetch_all(
        query,
        UUID(workflow_execution_id),
        agent_names
    )
    
    logger.info(
        f"Reset {len(rows)} agent tasks for workflow {workflow_execution_id}: {agent_names}"
    )
    
    return [dict(row) for row in rows]


# ==============================================================================
# ARTIFACT TOOLS
# ==============================================================================

@tool
async def get_next_incomplete_task(
    workflow_execution_id: str,
    agent: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get the next incomplete task for a workflow.
    
    Args:
        workflow_execution_id: Workflow execution ID
        agent: Optional agent name filter
        
    Returns:
        Next incomplete task or None
    """
    db = get_database_manager()
    
    if agent:
        query = """
            SELECT * FROM agent_tasks
            WHERE workflow_execution_id = $1
            AND agent = $2
            AND status IN ('OPEN', 'IN_PROGRESS')
            ORDER BY sequence_order
            LIMIT 1
        """
        row = await db.fetch_one(query, UUID(workflow_execution_id), agent)
    else:
        query = """
            SELECT * FROM agent_tasks
            WHERE workflow_execution_id = $1
            AND status IN ('OPEN', 'IN_PROGRESS')
            ORDER BY sequence_order
            LIMIT 1
        """
        row = await db.fetch_one(query, UUID(workflow_execution_id))
    
    return dict(row) if row else None


@tool
async def create_artifact(
    project_id: str,
    name: str,
    type: str,
    category: str,
    created_by: str,
    tags: Optional[List[str]] = None,
    status: str = "DRAFT",
) -> Dict[str, Any]:
    """Create new artifact."""
    db = get_database_manager()
    
    query = """
        INSERT INTO artifacts (
            project_id, name, type, category, status, created_by, created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
        RETURNING *
    """
    
    row = await db.fetch_one(
        query,
        UUID(project_id),
        name,
        type,
        category,
        status,
        UUID(created_by)
    )
    
    return dict(row)


@tool
async def get_artifact(artifact_id: str) -> Dict[str, Any]:
    """Get artifact by ID."""
    db = get_database_manager()
    
    query = "SELECT * FROM artifacts WHERE id = $1"
    row = await db.fetch_one(query, UUID(artifact_id))
    
    if not row:
        raise ValueError(f"Artifact {artifact_id} not found")
    
    return dict(row)


@tool
async def get_artifacts_by_project(project_id: str) -> List[Dict[str, Any]]:
    """Get all artifacts for a project."""
    db = get_database_manager()
    
    query = """
        SELECT * FROM artifacts
        WHERE project_id = $1
        ORDER BY created_at DESC
    """
    rows = await db.fetch_all(query, UUID(project_id))
    
    return [dict(row) for row in rows]


@tool
async def create_artifact_version(
    artifact_id: str,
    version_number: int,
    content: Dict[str, Any],
    created_by: str,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """Create new artifact version."""
    db = get_database_manager()
    
    query = """
        INSERT INTO artifact_versions (
            artifact_id, version_number, content, created_by,
            created_at, location
        )
        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, $5)
        RETURNING *
    """
    
    row = await db.fetch_one(
        query,
        UUID(artifact_id),
        version_number,
        json.dumps(content),
        UUID(created_by),
        location
    )
    
    return dict(row)


@tool
async def update_artifact_version(
    version_id: str,
    location: Optional[str] = None,
    content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update artifact version.
    
    Args:
        version_id: Version UUID
        location: S3 location of exported file
        content: Updated content
        
    Returns:
        Updated artifact version
    """
    db = get_database_manager()
    
    updates = []
    params = [UUID(version_id)]
    param_idx = 2
    
    if location is not None:
        updates.append(f"location = ${param_idx}")
        params.append(location)
        param_idx += 1
    
    if content is not None:
        updates.append(f"content = ${param_idx}")
        params.append(json.dumps(content))
        param_idx += 1
    
    if not updates:
        # If no updates, just return current version
        query = "SELECT * FROM artifact_versions WHERE id = $1"
        row = await db.fetch_one(query, UUID(version_id))
        return dict(row) if row else {}
    
    query = f"""
        UPDATE artifact_versions
        SET {', '.join(updates)}
        WHERE id = $1
        RETURNING *
    """
    
    row = await db.fetch_one(query, *params)
    return dict(row)


@tool
async def get_latest_artifact_version(artifact_id: str) -> Dict[str, Any]:
    """Get latest version of an artifact."""
    db = get_database_manager()
    
    query = """
        SELECT * FROM artifact_versions
        WHERE artifact_id = $1
        ORDER BY version_number DESC
        LIMIT 1
    """
    row = await db.fetch_one(query, UUID(artifact_id))
    
    if not row:
        raise ValueError(f"No versions found for artifact {artifact_id}")
    
    return dict(row)


# ==============================================================================
# CONVERSATION TOOLS
# ==============================================================================

@tool
async def save_conversation_message(
    project_id: str,
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    agent_name: Optional[str] = None,
    event_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Save conversation message."""
    db = get_database_manager()
    
    query = """
        INSERT INTO conversation_messages (
            project_id, session_id, user_id, role, content,
            agent_name, event_type, metadata, created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, CURRENT_TIMESTAMP)
        RETURNING *
    """
    
    row = await db.fetch_one(
        query,
        UUID(project_id),
        session_id,
        UUID(user_id),
        role,
        content,
        agent_name,
        event_type,
        json.dumps(metadata) if metadata else None
    )
    
    return dict(row)


@tool
async def get_conversation_history(
    project_id: str,
    session_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get conversation history."""
    db = get_database_manager()
    
    if session_id:
        query = """
            SELECT * FROM conversation_messages
            WHERE project_id = $1 AND session_id = $2
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
        """
        rows = await db.fetch_all(query, UUID(project_id), session_id, limit, offset)
    else:
        query = """
            SELECT * FROM conversation_messages
            WHERE project_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        rows = await db.fetch_all(query, UUID(project_id), limit, offset)
    
    return [dict(row) for row in rows]


# ==============================================================================
# GENERIC QUERY TOOL
# ==============================================================================

@tool
async def execute_custom_query(
    query: str,
    params: Optional[List[Any]] = None,
    fetch_one: bool = False
) -> Any:
    """
    Execute custom SQL query (use with caution).
    
    Args:
        query: SQL query string
        params: Query parameters
        fetch_one: Whether to fetch one row or all rows
        
    Returns:
        Query results
    """
    db = get_database_manager()
    
    if fetch_one:
        row = await db.fetch_one(query, *(params or []))
        return dict(row) if row else None
    else:
        rows = await db.fetch_all(query, *(params or []))
        return [dict(row) for row in rows]

# ==============================================================================
# PROJECT MEMBER AND NOTIFICATION TOOLS
# ==============================================================================

@tool
async def get_project_members(project_id: str) -> List[Dict[str, Any]]:
    """
    Get all members of a project with user details.
    
    Args:
        project_id: Project ID
        
    Returns:
        List of project members with user info
    """
    db = get_database_manager()
    
    query = """
        SELECT 
            pm.id,
            pm.project_id,
            pm.user_id,
            pm.added_by_id,
            pm.joined_at,
            u.email,
            u.username,
            u.first_name,
            u.last_name
        FROM project_members pm
        JOIN users u ON pm.user_id = u.id
        WHERE pm.project_id = $1
        ORDER BY pm.joined_at ASC
    """
    
    rows = await db.fetch_all(query, UUID(project_id))
    return [dict(row) for row in rows]


@tool
async def create_notification(
    user_id: str,
    type: str,
    title: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a notification for a user.
    
    Args:
        user_id: User ID
        type: Notification type
        title: Notification title
        message: Notification message
        metadata: Optional metadata
        
    Returns:
        Created notification record
    """
    db = get_database_manager()
    
    query = """
        INSERT INTO notifications (
            user_id, type, title, message, read, metadata, created_at
        ) VALUES (
            $1, $2, $3, $4, false, $5, CURRENT_TIMESTAMP
        )
        RETURNING *
    """
    
    row = await db.fetch_one(
        query,
        UUID(user_id),
        type,
        title,
        message,
        json.dumps(metadata) if metadata else None
    )
    return dict(row)


@tool
async def create_submission_record(
    project_id: str,
    artifact_id: str,
    portal_name: str,
    submission_id: Optional[str],
    status: str,
    submitted_by: str,
    submission_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a submission record.
    
    Args:
        project_id: Project ID
        artifact_id: Primary artifact ID
        portal_name: Portal/method name
        submission_id: External submission ID
        status: Submission status
        submitted_by: User ID who submitted
        submission_metadata: Optional metadata
        
    Returns:
        Created submission record
    """
    db = get_database_manager()
    
    query = """
        INSERT INTO submission_records (
            project_id, artifact_id, portal_name, submission_id,
            status, submitted_by, submitted_at, submission_metadata
        ) VALUES (
            $1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP, $7
        )
        RETURNING *
    """
    
    row = await db.fetch_one(
        query,
        UUID(project_id),
        UUID(artifact_id),
        portal_name,
        submission_id,
        status,
        UUID(submitted_by),
        json.dumps(submission_metadata) if submission_metadata else None
    )
    return dict(row)


@tool
async def get_artifact_versions(project_id: str) -> List[Dict[str, Any]]:
    """
    Get all artifact versions for a project (latest version of each artifact).
    
    Args:
        project_id: Project ID
        
    Returns:
        List of artifact versions with artifact details
    """
    db = get_database_manager()
    
    query = """
        SELECT 
            av.*,
            a.name,
            a.type,
            a.category,
            a.status as artifact_status,
            a.id as artifact_id
        FROM artifact_versions av
        JOIN artifacts a ON av.artifact_id = a.id
        WHERE a.project_id = $1
        AND av.version_number = (
            SELECT MAX(version_number)
            FROM artifact_versions av2
            WHERE av2.artifact_id = av.artifact_id
        )
        ORDER BY a.created_at DESC
    """
    
    rows = await db.fetch_all(query, UUID(project_id))
    return [dict(row) for row in rows]