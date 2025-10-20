"""
Intent Classifier for AI Assistant

Uses LLM to classify user queries into predefined intent types.
Extracts entities and determines confidence for routing decisions.
"""

import json
import logging
from typing import Dict, Any

from anthropic import Anthropic
from pydantic import ValidationError

from core.config import get_config
from supervisors.ai_assistant.state_models import (
    IntentClassification,
    IntentType,
)

logger = logging.getLogger(__name__)


# Intent classification prompt
INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for a bid management AI assistant.

Given a user's question, classify it into ONE of these intent types:

1. **query_project_status**: User asking about project progress, workflow status, task completion, or timeline
   Examples:
   - "What's the status of the XYZ project?"
   - "How far along are we with the ABC bid?"
   - "Is the compliance check done yet?"
   - "Show me the progress of project 123"

2. **ask_about_rfp**: User asking about RFP content, requirements, past bids, or best practices
   Examples:
   - "What are the key requirements in this RFP?"
   - "Have we bid on similar projects before?"
   - "What's our success rate with financial services clients?"
   - "How should we approach the security section?"

3. **request_artifact_edit**: User wants to edit, review, or modify generated artifacts
   Examples:
   - "Can you update the executive summary?"
   - "Change the pricing table to include..."
   - "Review the compliance matrix"
   - "Add more details to the technical approach"

4. **general_question**: General questions about the system, process, or capabilities
   Examples:
   - "How does the bid workflow work?"
   - "What can you help me with?"
   - "Explain the compliance checking process"
   - "What integrations are available?"

5. **clarification_needed**: Query is ambiguous or lacks context
   Examples:
   - "Status?"
   - "What about it?"
   - "Fix that"

Analyze the query and respond with a JSON object matching this schema:
{
  "intent": "<intent_type>",
  "confidence": <float 0-1>,
  "entities": {
    "project_id": "<uuid if mentioned>",
    "project_name": "<name if mentioned>",
    "artifact_type": "<type if mentioned>",
    "specific_request": "<details if mentioned>"
  },
  "reasoning": "<brief explanation of classification>",
  "requires_context": <true if needs project/workflow context>
}

User Query: {query}

Conversation Context (if available):
- Current Project: {project_name}
- Project ID: {project_id}
- Active Workflow: {workflow_id}

Classify the intent:"""


async def classify_intent(
    user_query: str,
    context: Dict[str, Any] = None
) -> IntentClassification:
    """
    Classify user query into intent type using LLM
    
    Args:
        user_query: User's natural language question
        context: Optional conversation context (project_id, workflow_id, etc.)
    
    Returns:
        IntentClassification with intent type, confidence, and entities
    
    Raises:
        ValueError: If classification fails after retries
    """
    config = get_config()
    client = Anthropic(api_key=config.anthropic_api_key)
    
    # Prepare context for prompt
    context = context or {}
    project_name = context.get("project_name", "None")
    project_id = context.get("project_id", "None")
    workflow_id = context.get("workflow_id", "None")
    
    # Format prompt
    prompt = INTENT_CLASSIFICATION_PROMPT.format(
        query=user_query,
        project_name=project_name,
        project_id=project_id,
        workflow_id=workflow_id
    )
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Call LLM for classification
            response = client.messages.create(
                model=config.default_model,
                max_tokens=500,
                temperature=0.3,  # Lower temperature for consistent classification
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Extract JSON from response
            content = response.content[0].text
            
            # Try to find JSON in response (may have markdown formatting)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            classification_data = json.loads(content)
            
            # Validate and create IntentClassification
            classification = IntentClassification(**classification_data)
            
            logger.info(
                f"Classified intent: {classification.intent} "
                f"(confidence: {classification.confidence:.2f})"
            )
            
            return classification
            
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(
                f"Intent classification attempt {attempt + 1} failed: {e}"
            )
            if attempt == max_retries - 1:
                # Fallback to general_question on final failure
                logger.error(
                    f"Intent classification failed after {max_retries} attempts, "
                    "defaulting to general_question"
                )
                return IntentClassification(
                    intent=IntentType.GENERAL_QUESTION,
                    confidence=0.5,
                    entities={},
                    reasoning="Classification failed, defaulted to general question",
                    requires_context=False
                )
        except Exception as e:
            logger.error(f"Unexpected error in intent classification: {e}")
            if attempt == max_retries - 1:
                return IntentClassification(
                    intent=IntentType.GENERAL_QUESTION,
                    confidence=0.3,
                    entities={},
                    reasoning=f"Error during classification: {str(e)}",
                    requires_context=False
                )


def get_clarification_prompt(query: str) -> str:
    """
    Generate clarification question when intent is unclear
    
    Args:
        query: Original ambiguous query
    
    Returns:
        Clarification question for user
    """
    return (
        f"I need a bit more information to help you with '{query}'. "
        "Could you clarify:\n\n"
        "1. Are you asking about a specific project's status?\n"
        "2. Do you want information about RFP requirements or past bids?\n"
        "3. Would you like to edit or review generated artifacts?\n"
        "4. Is this a general question about the system?\n\n"
        "Please provide more details so I can assist you better."
    )


def validate_context_availability(
    classification: IntentClassification,
    context: Dict[str, Any]
) -> bool:
    """
    Check if required context is available for classified intent
    
    Args:
        classification: Classified intent
        context: Available conversation context
    
    Returns:
        True if required context is available, False otherwise
    """
    if not classification.requires_context:
        return True
    
    # Check if project_id is available when required
    if classification.intent in [
        IntentType.QUERY_PROJECT_STATUS,
        IntentType.REQUEST_ARTIFACT_EDIT
    ]:
        return context.get("project_id") is not None
    
    return True