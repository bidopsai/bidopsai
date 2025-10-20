"""
Prompt Manager for BidOpsAI AgentCore.

Manages system prompts for agents based on:
- Agent name (parser, analysis, content, etc.)
- Mode (workflow, ai_assistant)
- Dynamic context injection

Prompts are loaded from files and can be customized per deployment.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from core.config import get_config

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Centralized prompt management for agents.
    
    Loads and manages system prompts with support for:
    - Mode-specific prompts (workflow vs AI assistant)
    - Dynamic variable substitution
    - Prompt versioning
    - Fallback prompts
    """
    
    _instance: Optional["PromptManager"] = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize prompt manager."""
        if not hasattr(self, "_initialized"):
            config = get_config()
            
            # Prompt directory
            self.prompts_dir = Path(__file__).parent
            
            # Cache for loaded prompts
            self._prompt_cache: Dict[str, str] = {}
            
            # Load all prompts
            self._load_all_prompts()
            
            self._initialized = True
            logger.info(f"PromptManager initialized ({len(self._prompt_cache)} prompts loaded)")
    
    def _load_all_prompts(self):
        """Load all prompt files into cache."""
        # Load workflow mode prompts
        workflow_dir = self.prompts_dir / "workflow"
        if workflow_dir.exists():
            for prompt_file in workflow_dir.glob("*.txt"):
                agent_name = prompt_file.stem
                key = f"workflow_{agent_name}"
                self._prompt_cache[key] = prompt_file.read_text()
                logger.debug(f"Loaded prompt: {key}")
        
        # Load AI assistant mode prompts
        ai_assistant_dir = self.prompts_dir / "ai_assistant"
        if ai_assistant_dir.exists():
            for prompt_file in ai_assistant_dir.glob("*.txt"):
                agent_name = prompt_file.stem
                key = f"ai_assistant_{agent_name}"
                self._prompt_cache[key] = prompt_file.read_text()
                logger.debug(f"Loaded prompt: {key}")
        
        # Load supervisor prompts
        supervisor_file = self.prompts_dir / "workflow" / "supervisor.txt"
        if supervisor_file.exists():
            self._prompt_cache["workflow_supervisor"] = supervisor_file.read_text()
        
        ai_supervisor_file = self.prompts_dir / "ai_assistant" / "supervisor.txt"
        if ai_supervisor_file.exists():
            self._prompt_cache["ai_assistant_supervisor"] = ai_supervisor_file.read_text()
    
    def get_prompt(
        self,
        agent_name: str,
        mode: str = "workflow",
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Get prompt for an agent.
        
        Args:
            agent_name: Name of the agent (parser, analysis, content, etc.)
            mode: Execution mode (workflow or ai_assistant)
            context: Context variables for prompt substitution
            
        Returns:
            System prompt with context substituted
        """
        # Build cache key
        cache_key = f"{mode}_{agent_name}"
        
        # Get prompt from cache
        prompt_template = self._prompt_cache.get(cache_key)
        
        if not prompt_template:
            logger.warning(f"Prompt not found: {cache_key}, using fallback")
            prompt_template = self._get_fallback_prompt(agent_name)
        
        # Substitute context variables
        if context:
            try:
                prompt = prompt_template.format(**context)
            except KeyError as e:
                logger.warning(f"Missing context variable in prompt: {e}")
                prompt = prompt_template
        else:
            prompt = prompt_template
        
        return prompt
    
    def _get_fallback_prompt(self, agent_name: str) -> str:
        """Get fallback prompt if specific prompt not found."""
        return f"""You are the {agent_name} agent in the BidOpsAI system.

Your role is to {agent_name} documents and data according to the workflow requirements.

Follow these principles:
1. Be precise and accurate in your analysis
2. Use structured outputs when requested
3. Report errors clearly
4. Request clarification when needed
5. Maintain context throughout the workflow

Complete your task efficiently and return results in the expected format."""
    
    def reload_prompts(self):
        """Reload all prompts from disk."""
        self._prompt_cache.clear()
        self._load_all_prompts()
        logger.info("Prompts reloaded")
    
    def get_available_prompts(self) -> Dict[str, int]:
        """
        Get list of available prompts.
        
        Returns:
            Dictionary of prompt keys and their lengths
        """
        return {
            key: len(prompt)
            for key, prompt in self._prompt_cache.items()
        }
    
    def validate_prompts(self) -> Dict[str, Any]:
        """
        Validate all loaded prompts.
        
        Returns:
            Validation results
        """
        results = {
            "total_prompts": len(self._prompt_cache),
            "valid_prompts": [],
            "issues": [],
        }
        
        for key, prompt in self._prompt_cache.items():
            if not prompt or len(prompt) < 50:
                results["issues"].append(f"{key}: Prompt too short ({len(prompt)} chars)")
            else:
                results["valid_prompts"].append(key)
        
        return results


# Singleton instance
def get_prompt_manager() -> PromptManager:
    """Get singleton PromptManager instance."""
    return PromptManager()


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_agent_prompt(
    agent_name: str,
    mode: str = "workflow",
    **context
) -> str:
    """
    Convenience function to get agent prompt with context.
    
    Args:
        agent_name: Agent name
        mode: Execution mode
        **context: Context variables as keyword arguments
        
    Returns:
        Formatted prompt
    """
    pm = get_prompt_manager()
    return pm.get_prompt(agent_name, mode, context)


def build_context(
    project_name: str = "",
    user_name: str = "",
    current_step: str = "",
    previous_outputs: str = "",
    **extra
) -> Dict[str, Any]:
    """
    Build context dictionary for prompt substitution.
    
    Args:
        project_name: Name of current project
        user_name: Name of user
        current_step: Current workflow step
        previous_outputs: Summary of previous agent outputs
        **extra: Additional context variables
        
    Returns:
        Context dictionary
    """
    context = {
        "project_name": project_name,
        "user_name": user_name,
        "current_step": current_step,
        "previous_outputs": previous_outputs,
    }
    context.update(extra)
    return context