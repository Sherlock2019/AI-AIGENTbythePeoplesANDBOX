"""
Supervisor Agent — Intelligent Engine Selection and Policy Enforcement
---------------------------------------------------------------------

Decides which model engine to use based on:
    - Prompt length
    - GPU availability
    - Cost constraints
    - Task requirements
    - Policy rules (Credit/Asset agents)
"""

import os
import logging
from typing import Dict, Any, Optional

from services.api.agent_manager import get_agent_manager

logger = logging.getLogger(__name__)

# Get singleton manager
manager = get_agent_manager()


def decide_engine(payload: Dict[str, Any], task: str = "generate") -> Optional[str]:
    """
    Intelligently decide which engine to use based on payload and context.
    
    Decision rules:
        - Prompt length < 50 → use local model (fast, no API cost)
        - Prompt length > 2000 → force HuggingFace API (better context handling)
        - GPU available → prefer local
        - Cost flag set → local only
        - Async/streaming needed → Ollama
        - Task-specific requirements
    
    Args:
        payload: Task payload (may contain prompt, text, question, etc.)
        task: Task type (generate, summarize, qa, etc.)
    
    Returns:
        Engine name ("local", "ollama", "hf_api") or None for auto-select
    """
    # Extract text length from payload
    text_length = 0
    if "prompt" in payload:
        text_length = len(payload["prompt"])
    elif "text" in payload:
        text_length = len(payload["text"])
    elif "question" in payload and "context" in payload:
        text_length = len(payload["question"]) + len(payload["context"])
    elif "question" in payload:
        text_length = len(payload["question"])
    elif "context" in payload:
        text_length = len(payload["context"])

    # Cost constraint: if cost flag is set, use local only
    if payload.get("cost_sensitive", False) or os.getenv("FORCE_LOCAL_ONLY", "").lower() == "true":
        logger.info("Cost-sensitive mode: forcing local engine")
        return "local"

    # Short prompts: use local (fast, no API cost)
    if text_length < 50:
        if manager.loaded_models.get("local") or manager.local_model_name:
            logger.info(f"Short prompt ({text_length} chars): using local engine")
            return "local"

    # Very long prompts: use HF API (better context handling)
    if text_length > 2000:
        logger.info(f"Long prompt ({text_length} chars): using HF API")
        return "hf_api"

    # GPU available: prefer local
    if manager.device == "cuda" and manager.loaded_models.get("local"):
        logger.info("GPU available: preferring local engine")
        return "local"

    # Streaming/async requirement: use Ollama
    if payload.get("stream", False) or payload.get("async", False):
        if manager.loaded_models.get("ollama"):
            logger.info("Streaming/async required: using Ollama")
            return "ollama"

    # Task-specific decisions
    if task in ["embedding", "classify", "summarize"]:
        # These tasks work well with HF pipelines
        logger.info(f"Task '{task}': using HF pipeline (auto)")
        return None  # Let manager decide (will use HF pipeline)

    # Default: auto-select (manager will try local → ollama → hf_api)
    logger.info("Auto-selecting engine based on availability")
    return None


def enforce_safety_filters(task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce safety filters for generation tasks.
    
    Args:
        task: Task type
        payload: Task payload
    
    Returns:
        Modified payload with safety constraints
    """
    if task not in ["generate", "text-generation"]:
        return payload

    # Limit max tokens for safety
    if "max_new_tokens" not in payload:
        payload["max_new_tokens"] = 500  # Default limit
    else:
        payload["max_new_tokens"] = min(payload["max_new_tokens"], 2000)  # Hard limit

    # Lower temperature for sensitive tasks
    if payload.get("sensitive", False):
        payload["temperature"] = min(payload.get("temperature", 0.7), 0.5)

    return payload


def enforce_policy(task: str, payload: Dict[str, Any], agent_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Enforce policy rules for Credit/Asset agents.
    
    Args:
        task: Task type
        payload: Task payload
        agent_type: Agent type ("credit", "asset", etc.)
    
    Returns:
        Modified payload with policy constraints
    """
    # Credit agent policies
    if agent_type == "credit":
        # Force deterministic outputs for credit scoring
        if task == "generate":
            payload["temperature"] = 0.1
            payload["top_p"] = 0.9
        logger.info("Credit agent policy: enforcing deterministic outputs")

    # Asset agent policies
    if agent_type == "asset":
        # Require local/ollama for sensitive asset data
        if not payload.get("engine"):
            payload["engine"] = "local" if manager.loaded_models.get("local") else "ollama"
        logger.info("Asset agent policy: using local/ollama for sensitive data")

    return payload


class SupervisorAgent:
    """
    Supervisor agent that coordinates model selection and policy enforcement.
    """

    def __init__(self):
        self.manager = get_agent_manager()
        logger.info("🤖 Supervisor Agent initialized")

    def run(
        self,
        task: str,
        payload: Dict[str, Any],
        agent_type: Optional[str] = None,
        enforce_safety: bool = True,
        enforce_policy_rules: bool = True,
    ) -> Dict[str, Any]:
        """
        Run a task with intelligent engine selection and policy enforcement.
        
        Args:
            task: Task type
            payload: Task payload
            agent_type: Agent type for policy enforcement ("credit", "asset", etc.)
            enforce_safety: Whether to apply safety filters
            enforce_policy_rules: Whether to apply policy rules
        
        Returns:
            Task result with metadata
        """
        # Apply safety filters
        if enforce_safety:
            payload = enforce_safety_filters(task, payload)

        # Apply policy rules
        if enforce_policy_rules and agent_type:
            payload = enforce_policy(task, payload, agent_type)

        # Decide engine
        engine = decide_engine(payload, task)
        if engine:
            payload["engine"] = engine

        # Execute task
        logger.info(f"Supervisor executing task '{task}' with engine={engine or 'auto'}")
        result = self.manager.run(task=task, **payload)

        # Add supervisor metadata
        result["supervisor"] = {
            "engine_selected": engine or "auto",
            "agent_type": agent_type,
            "safety_enforced": enforce_safety,
            "policy_enforced": enforce_policy_rules,
        }

        return result


# Singleton supervisor instance
_supervisor_instance: Optional[SupervisorAgent] = None


def get_supervisor() -> SupervisorAgent:
    """Get or create singleton SupervisorAgent instance."""
    global _supervisor_instance
    if _supervisor_instance is None:
        _supervisor_instance = SupervisorAgent()
    return _supervisor_instance
