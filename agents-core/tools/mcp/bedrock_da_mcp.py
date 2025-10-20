"""
Bedrock Data Automation MCP Integration - Direct MCP Client Access

This module provides MCP client initialization for AWS Bedrock Data Automation
integration. NO WRAPPERS - agents receive native MCP tools directly.

Bedrock Data Automation provides document parsing capabilities:
- Extract text from PDFs, Word docs, images
- Structured data extraction
- Table detection and extraction
- Form field recognition

Architecture Pattern (CORRECT):
1. Initialize MCP client during startup
2. Retrieve native tool list from MCP server
3. Pass native tools directly to agents
4. Agents invoke MCP tools natively (no Python function calls)

Reference:
- Bedrock Data Automation: https://docs.aws.amazon.com/bedrock/latest/userguide/data-automation.html
- AWS MCP Server: https://github.com/aws/aws-mcp-server

Usage:
    ```python
    from tools.mcp.bedrock_da_mcp import initialize_bedrock_da_mcp
    from tools.tool_manager import get_tool_manager
    
    # Initialize Bedrock DA MCP client
    await initialize_bedrock_da_mcp()
    
    # Tools are now available via tool_manager
    tool_manager = get_tool_manager()
    parser_tools = tool_manager.get_agent_tools("parser", mode="workflow")
    # parser_tools will include native Bedrock DA MCP tools
    ```
"""

import logging
from typing import Optional

from mcp import StdioServerParameters

from core.config import get_config
from core.error_handling import AgentError, ErrorCode, ErrorSeverity
from core.observability import log_agent_action
from tools.tool_manager import get_tool_manager

logger = logging.getLogger(__name__)


async def initialize_bedrock_da_mcp() -> None:
    """
    Initialize Bedrock Data Automation MCP client.
    
    This function:
    1. Creates MCP client connection to AWS MCP server
    2. Retrieves native Bedrock DA tool list (parse_document, extract_tables, etc.)
    3. Stores tools in ToolManager for agent access
    
    Agents will receive these tools natively - NO Python wrapper functions.
    
    Raises:
        AgentError: If initialization fails
    """
    log_agent_action(
        agent_name="system",
        action="bedrock_da_mcp_init_start",
        details={"client": "bedrock_da_mcp"}
    )
    
    try:
        config = get_config()
        
        # Get AWS configuration
        aws_region = config.get("aws.region", "us-east-1")
        aws_profile = config.get("aws.profile", "default")
        
        # Create MCP server parameters for AWS MCP server
        # The AWS MCP server provides access to Bedrock services including Data Automation
        server_params = StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@aws/mcp-server-aws",
                "--region", aws_region,
                "--profile", aws_profile,
            ],
            env={
                "AWS_REGION": aws_region,
                # AWS SDK will use default credential chain
            }
        )
        
        # Initialize MCP client and retrieve native tools
        tool_manager = get_tool_manager()
        await tool_manager.initialize_mcp_client(
            client_name="bedrock_da_mcp",
            server_params=server_params
        )
        
        log_agent_action(
            agent_name="system",
            action="bedrock_da_mcp_init_success",
            details={
                "client": "bedrock_da_mcp",
                "region": aws_region
            }
        )
        
        logger.info(
            f"Bedrock Data Automation MCP client initialized successfully "
            f"(region: {aws_region})"
        )
        
    except Exception as e:
        log_agent_action(
            agent_name="system",
            action="bedrock_da_mcp_init_failed",
            details={"error": str(e)},
            level="error"
        )
        
        logger.error(f"Failed to initialize Bedrock DA MCP: {e}", exc_info=True)
        
        raise AgentError(
            code=ErrorCode.TOOL_INITIALIZATION_ERROR,
            message=f"Failed to initialize Bedrock DA MCP client: {str(e)}",
            severity=ErrorSeverity.HIGH,
            details={"error": str(e)}
        ) from e


def get_bedrock_da_mcp_system_prompt() -> str:
    """
    Get system prompt instructions for using Bedrock Data Automation MCP tools.
    
    This prompt teaches agents how to use native Bedrock DA MCP tools correctly.
    Include this in agent system prompts when they have Bedrock DA access.
    
    Returns:
        System prompt text for Bedrock DA MCP tool usage
    """
    return """
## Bedrock Data Automation Tools

You have access to native AWS Bedrock Data Automation MCP tools for document processing.
Use these tools to:
- Parse PDF, Word, Excel documents
- Extract text content from documents
- Extract tables and structured data
- Process scanned images with OCR

### Available Bedrock DA Tools

1. **bedrock_data_automation_parse_document** - Parse document and extract content
   - Use for: Extracting text from uploaded project documents
   - Required: s3_uri (S3 location of document)
   - Optional: output_s3_uri (where to save processed output)
   - Returns: Extracted text, tables, metadata

2. **bedrock_data_automation_extract_tables** - Extract tables from document
   - Use for: Getting structured table data from documents
   - Required: s3_uri (S3 location of document)
   - Returns: Table data in structured format

3. **bedrock_data_automation_analyze_document** - Advanced document analysis
   - Use for: Complex document understanding tasks
   - Required: s3_uri (S3 location), analysis_type
   - Returns: Detailed analysis results

### Document Processing Pattern

**Step 1: Parse Document**
```
Call: bedrock_data_automation_parse_document
Args: {
  "s3_uri": "s3://project-docs/2025/01/15/rfp-document.pdf",
  "output_s3_uri": "s3://processed-docs/2025/01/15/rfp-document/"
}
Result: {
  "text": "Full document text...",
  "tables": [...],
  "metadata": {...}
}
```

**Step 2: Update Database**
After successful parsing, update the `project_documents` table:
- Set `processed_file_location` to output S3 URI
- Store metadata in `metadata` JSONB field

**Step 3: Return to Supervisor**
Provide parsing results in `output_data` for next agent in workflow.

### S3 URI Format

- Input: `s3://{bucket}/{yyyy}/{mm}/{dd}/{project_name}_{timestamp}/{filename}`
- Output: `s3://{bucket}/processed/{yyyy}/{mm}/{dd}/{project_name}_{timestamp}/{filename}/`

### Error Handling

If parsing fails:
1. Check S3 URI is accessible
2. Verify document format is supported (PDF, DOCX, XLSX, images)
3. Check document isn't corrupted or password-protected
4. Update `error_log` in agent task with details
5. Return failure status to supervisor

### Supported Document Types

- **PDF**: Text extraction, table detection, form fields
- **Word (DOCX)**: Full text, tables, images
- **Excel (XLSX)**: Sheets, tables, formulas
- **Images (PNG, JPG)**: OCR text extraction
- **Scanned Documents**: OCR + layout analysis
"""


# Legacy compatibility - mark deprecated
async def parse_document_with_bedrock(*args, **kwargs):
    """DEPRECATED: Wrapper functions removed. Use native MCP tools."""
    raise NotImplementedError(
        "Python wrapper functions are deprecated. "
        "Agents use native MCP tool 'bedrock_data_automation_parse_document' directly."
    )


async def extract_tables_from_document(*args, **kwargs):
    """DEPRECATED: Wrapper functions removed. Use native MCP tools."""
    raise NotImplementedError(
        "Python wrapper functions are deprecated. "
        "Agents use native MCP tool 'bedrock_data_automation_extract_tables' directly."
    )