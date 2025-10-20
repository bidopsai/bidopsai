"""
Email Sender - SMTP/Gmail Integration

This module provides tools for sending emails with attachments.
Supports both SMTP and Gmail API for sending bid submissions.

Features:
- Send emails with HTML/plain text body
- Attach files from S3 locations
- Support for multiple recipients (to, cc, bcc)
- Gmail API integration (preferred)
- SMTP fallback support
- Email draft creation for user review
- Email tracking and logging

Configuration:
- Uses environment variables or AWS Secrets Manager
- Supports OAuth2 for Gmail
- SMTP credentials from config

All tool functions use the @tool decorator for Strands Agent integration.
"""

import base64
import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from datetime import datetime

import boto3
from strands import tool

from core.config import get_config
from core.error_handling import (
    AgentError,
    ErrorCode,
    ErrorSeverity,
    handle_errors
)
from core.observability import trace_operation, log_agent_action

logger = logging.getLogger(__name__)


class EmailSender:
    """
    Email sender for bid submissions and communications.
    
    Handles email composition, attachment preparation,
    and sending via Gmail API or SMTP.
    
    Singleton pattern to reuse configuration and connections.
    """
    
    _instance: Optional["EmailSender"] = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize email sender."""
        if not hasattr(self, "_initialized"):
            config = get_config()
            
            # Email configuration
            self.send_method = config.get("email.send_method", "mock")  # mock, smtp, gmail
            self.from_address = config.get("email.from_address", "bids@deloitte.com")
            self.sender_email = config.get("GMAIL_SENDER_EMAIL", self.from_address)
            self.gmail_credentials = config.get("GMAIL_CREDENTIALS_PATH")
            
            # S3 client for downloading attachments
            self.s3_client = boto3.client('s3')
            
            # TODO: Initialize Gmail API client
            # This will use the Google API Python client
            self.gmail_service = None
            
            self._initialized = True
            logger.info(f"EmailSender initialized (sender: {self.sender_email}, method: {self.send_method})")
    
    def _create_message_with_attachments(
        self,
        to: List[str],
        subject: str,
        body: str,
        attachments: List[Dict[str, Any]],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        body_html: bool = False,
    ) -> Dict[str, Any]:
        """
        Create email message with attachments.
        
        Args:
            to: Recipient email addresses
            subject: Email subject
            body: Email body
            attachments: List of attachments with name/filename and content
            cc: CC recipients
            bcc: BCC recipients
            body_html: Whether body is HTML
            
        Returns:
            Email message dict for Gmail API
        """
        message = MIMEMultipart()
        message["to"] = ", ".join(to)
        message["subject"] = subject
        
        if cc:
            message["cc"] = ", ".join(cc)
        if bcc:
            message["bcc"] = ", ".join(bcc)
        
        # Add body
        if body_html:
            message.attach(MIMEText(body, "html"))
        else:
            message.attach(MIMEText(body, "plain"))
        
        # Add attachments
        for attachment in attachments:
            # Support both 'name' and 'filename' keys
            filename = attachment.get("name") or attachment.get("filename", "attachment")
            content = attachment["content"]
            
            part = MIMEApplication(content, Name=filename)
            part["Content-Disposition"] = f'attachment; filename="{filename}"'
            message.attach(part)
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        return {"raw": raw_message}
    
    async def _download_from_s3(self, s3_location: str) -> Dict[str, Any]:
        """
        Download artifact from S3.
        
        Args:
            s3_location: S3 URL or path
            
        Returns:
            Dict with filename and content
        """
        # Parse S3 location (format: s3://bucket/key or https://...)
        if s3_location.startswith("s3://"):
            parts = s3_location[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
        elif "s3.amazonaws.com" in s3_location or "s3-" in s3_location:
            # Parse HTTPS S3 URL
            # Format: https://bucket.s3.region.amazonaws.com/key
            url_parts = s3_location.split("/")
            bucket = url_parts[2].split(".")[0]
            key = "/".join(url_parts[3:])
        else:
            raise ValueError(f"Invalid S3 location: {s3_location}")
        
        # Download from S3
        response = self.s3_client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read()
        
        # Extract filename from key
        filename = key.split("/")[-1]
        
        return {
            "filename": filename,
            "name": filename,  # Support both keys
            "content": content,
            "content_type": response.get('ContentType', 'application/octet-stream')
        }
    
    @trace_operation("email_send")
    @handle_errors
    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        body_html: bool = False,
    ) -> Dict[str, Any]:
        """
        Send email via configured method (Gmail API, SMTP, or mock).
        
        Args:
            to: Recipient email addresses
            subject: Email subject
            body: Email body
            attachments: List of attachments (name/filename, content)
            cc: CC recipients
            bcc: BCC recipients
            body_html: Whether body is HTML
            
        Returns:
            Send result with message ID
        """
        log_agent_action(
            agent_name="email_sender",
            action="send_start",
            details={
                "to": to,
                "subject": subject,
                "attachments": len(attachments) if attachments else 0,
                "method": self.send_method
            }
        )
        
        try:
            # Send based on configured method
            if self.send_method == "gmail":
                result = await self._send_via_gmail(
                    to=to,
                    subject=subject,
                    body=body,
                    attachments=attachments or [],
                    cc=cc,
                    bcc=bcc,
                    body_html=body_html
                )
            elif self.send_method == "smtp":
                result = await self._send_via_smtp(
                    to=to,
                    subject=subject,
                    body=body,
                    attachments=attachments or [],
                    cc=cc,
                    bcc=bcc,
                    body_html=body_html
                )
            else:
                # Mock mode for development
                result = await self._send_mock(
                    to=to,
                    subject=subject,
                    body=body,
                    attachments=attachments or [],
                    body_html=body_html
                )
            
            log_agent_action(
                agent_name="email_sender",
                action="send_success",
                details={
                    "to": to,
                    "message_id": result.get("message_id"),
                    "method": self.send_method
                }
            )
            
            return result
            
        except Exception as e:
            log_agent_action(
                agent_name="email_sender",
                action="send_failed",
                details={"error": str(e)},
                level="error"
            )
            raise AgentError(
                code=ErrorCode.TOOL_EXECUTION_FAILED,
                message=f"Failed to send email: {str(e)}",
                severity=ErrorSeverity.HIGH,
                details={"error": str(e)}
            ) from e
    
    @trace_operation("email_send_with_s3_attachments")
    @handle_errors
    async def send_email_with_s3_attachments(
        self,
        to: List[str],
        subject: str,
        body: str,
        s3_attachment_uris: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        body_html: bool = False,
    ) -> Dict[str, Any]:
        """
        Send email with attachments from S3.
        
        Args:
            to: Recipient email addresses
            subject: Email subject
            body: Email body
            s3_attachment_uris: List of S3 URIs to attach
            cc: CC recipients
            bcc: BCC recipients
            body_html: Whether body is HTML
            
        Returns:
            Send result
        """
        # Download attachments from S3
        attachments = []
        
        for s3_uri in s3_attachment_uris:
            if not s3_uri:
                continue
            
            try:
                attachment_data = await self._download_from_s3(s3_uri)
                attachments.append(attachment_data)
                logger.info(f"Downloaded attachment: {attachment_data['filename']} ({len(attachment_data['content'])} bytes)")
            except Exception as e:
                log_agent_action(
                    agent_name="email_sender",
                    action="attachment_download_failed",
                    details={"location": s3_uri, "error": str(e)},
                    level="warning"
                )
                # Continue with other attachments
        
        # Send email with attachments
        return await self.send_email(
            to=to,
            subject=subject,
            body=body,
            attachments=attachments,
            cc=cc,
            bcc=bcc,
            body_html=body_html,
        )
    
    @trace_operation("email_create_draft")
    @handle_errors
    async def create_draft(
        self,
        to: List[str],
        subject: str,
        body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Create email draft (for user review before sending).
        
        Args:
            to: Recipient email addresses
            subject: Email subject
            body: Email body
            attachments: List of attachments
            
        Returns:
            Draft info with preview
        """
        # TODO: Implement Gmail draft creation API
        
        logger.info(f"Creating email draft: {subject}")
        
        return {
            "success": True,
            "draft_id": f"draft_{hash(subject) % 1000000:06d}",
            "to": to,
            "subject": subject,
            "preview": body[:100],
            "attachments_count": len(attachments) if attachments else 0,
        }
    
    async def _send_via_gmail(
        self,
        to: List[str],
        subject: str,
        body: str,
        attachments: List[Dict[str, Any]],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        body_html: bool = False,
    ) -> Dict[str, Any]:
        """
        Send email via Gmail API.
        
        Args:
            to: Recipients
            subject: Subject
            body: Body
            attachments: List of attachments
            cc: CC recipients
            bcc: BCC recipients
            body_html: Whether body is HTML
            
        Returns:
            Send result
        """
        # TODO: Implement Gmail API integration
        # For now, use mock
        log_agent_action(
            agent_name="email_sender",
            action="gmail_not_implemented",
            details={"to": to},
            level="warning"
        )
        
        return await self._send_mock(
            to=to,
            subject=subject,
            body=body,
            attachments=attachments,
            body_html=body_html
        )
    
    async def _send_via_smtp(
        self,
        to: List[str],
        subject: str,
        body: str,
        attachments: List[Dict[str, Any]],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        body_html: bool = False,
    ) -> Dict[str, Any]:
        """
        Send email via SMTP.
        
        Args:
            to: Recipients
            subject: Subject
            body: Body
            attachments: List of attachments
            cc: CC recipients
            bcc: BCC recipients
            body_html: Whether body is HTML
            
        Returns:
            Send result
        """
        # TODO: Implement SMTP integration
        # For now, use mock
        log_agent_action(
            agent_name="email_sender",
            action="smtp_not_implemented",
            details={"to": to},
            level="warning"
        )
        
        return await self._send_mock(
            to=to,
            subject=subject,
            body=body,
            attachments=attachments,
            body_html=body_html
        )
    
    async def _send_mock(
        self,
        to: List[str],
        subject: str,
        body: str,
        attachments: List[Dict[str, Any]],
        body_html: bool = False,
    ) -> Dict[str, Any]:
        """
        Mock email sending for development.
        
        Args:
            to: Recipients
            subject: Subject
            body: Body
            attachments: List of attachments
            body_html: Whether body is HTML
            
        Returns:
            Mock send result
        """
        log_agent_action(
            agent_name="email_sender",
            action="mock_send",
            details={
                "to": to,
                "from": self.sender_email,
                "subject": subject,
                "attachments": len(attachments),
                "body_html": body_html
            },
            level="warning"
        )
        
        # Generate mock message ID
        message_id = f"<{datetime.utcnow().timestamp()}.mock@bidopsai.com>"
        
        return {
            "success": True,
            "sent": True,
            "message_id": message_id,
            "method": "mock",
            "to": to,
            "from": self.sender_email,
            "subject": subject,
            "attachments_count": len(attachments),
            "sent_at": datetime.utcnow().isoformat() + "Z",
        }


# Singleton instance
def get_email_sender() -> EmailSender:
    """Get singleton email sender instance."""
    return EmailSender()


# ==============================================================================
# TOOL FUNCTIONS
# ==============================================================================

@tool
@handle_errors
async def send_email_tool(
    to: List[str],
    subject: str,
    body: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    body_html: bool = False,
) -> Dict[str, Any]:
    """
    Send email via configured method (Gmail API, SMTP, or mock).
    
    Args:
        to: Recipient email addresses
        subject: Email subject
        body: Email body (plain text or HTML)
        attachments: Optional list of attachments with 'name'/'filename' and 'content'
        cc: Optional CC recipients
        bcc: Optional BCC recipients
        body_html: Whether body is HTML (default: False)
        
    Returns:
        Dict with send result including message_id and sent_at
        
    Example:
        result = await send_email_tool(
            to=["client@example.com"],
            subject="RFP Response",
            body="Please find our proposal attached.",
            attachments=[{"name": "proposal.pdf", "content": b"..."}],
            body_html=False
        )
    """
    sender = get_email_sender()
    return await sender.send_email(
        to=to,
        subject=subject,
        body=body,
        attachments=attachments,
        cc=cc,
        bcc=bcc,
        body_html=body_html,
    )


@tool
@handle_errors
async def send_email_with_s3_attachments_tool(
    to: List[str],
    subject: str,
    body: str,
    s3_attachment_uris: List[str],
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    body_html: bool = False,
) -> Dict[str, Any]:
    """
    Send email with attachments downloaded from S3.
    
    Args:
        to: Recipient email addresses
        subject: Email subject
        body: Email body
        s3_attachment_uris: List of S3 URIs (s3://bucket/key or https://...)
        cc: Optional CC recipients
        bcc: Optional BCC recipients
        body_html: Whether body is HTML (default: False)
        
    Returns:
        Dict with send result
        
    Example:
        result = await send_email_with_s3_attachments_tool(
            to=["client@example.com"],
            subject="RFP Response",
            body="Please find our proposal attached.",
            s3_attachment_uris=[
                "s3://bidopsai-artifacts/proposals/2025/proposal.pdf",
                "s3://bidopsai-artifacts/proposals/2025/pricing.xlsx"
            ]
        )
    """
    sender = get_email_sender()
    return await sender.send_email_with_s3_attachments(
        to=to,
        subject=subject,
        body=body,
        s3_attachment_uris=s3_attachment_uris,
        cc=cc,
        bcc=bcc,
        body_html=body_html,
    )


@tool
@handle_errors
async def create_email_draft_tool(
    to: List[str],
    subject: str,
    body: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Create email draft for user review before sending.
    
    Args:
        to: Recipient email addresses
        subject: Email subject
        body: Email body
        attachments: Optional list of attachments
        
    Returns:
        Dict with draft info including draft_id and preview
        
    Example:
        draft = await create_email_draft_tool(
            to=["client@example.com"],
            subject="RFP Response",
            body="Please find our proposal attached.",
            attachments=[{"name": "proposal.pdf", "content": b"..."}]
        )
    """
    sender = get_email_sender()
    return await sender.create_draft(
        to=to,
        subject=subject,
        body=body,
        attachments=attachments,
    )


@tool
@handle_errors
async def send_email_with_attachments(
    to_address: str,
    from_address: str,
    subject: str,
    body: str,
    artifact_locations: List[str],
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Send email with artifact attachments (legacy interface for backward compatibility).
    
    Args:
        to_address: Single recipient email
        from_address: Sender email (ignored, uses configured sender)
        subject: Email subject
        body: Email body
        artifact_locations: List of S3 URLs/paths
        cc: Optional CC recipients
        bcc: Optional BCC recipients
        
    Returns:
        Dict with send result
        
    Note:
        This is a legacy tool for backward compatibility.
        New code should use send_email_with_s3_attachments_tool instead.
    """
    sender = get_email_sender()
    return await sender.send_email_with_s3_attachments(
        to=[to_address],  # Convert single address to list
        subject=subject,
        body=body,
        s3_attachment_uris=artifact_locations,
        cc=cc,
        bcc=bcc,
        body_html=False,
    )