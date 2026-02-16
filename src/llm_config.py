# -*- coding: utf-8 -*-
"""
LLM Configuration Module

This module provides configuration management for multiple LLM providers
(Groq, Mistral, and OpenAI) in the Cybernetic Agents system.
"""

import os
from dataclasses import dataclass
from typing import Optional

from src.cyberagent.secrets import get_secret
from src.rbac.system_types import SystemTypes


@dataclass
class LLMConfig:
    """
    Configuration for LLM providers.

    Attributes:
        provider: LLM provider name ("groq", "mistral", or "openai")
        model: Model name to use
        api_key: API key for the provider
        temperature: Temperature setting (0.0-1.0)
        max_tokens: Maximum tokens for responses
        top_p: Top-p sampling (optional)
        random_seed: Random seed for reproducibility (optional)
        safe_prompt: Enable safe prompt filtering
        base_url: Base URL for API (Groq-specific)
        api_type: API type for Mistral (Mistral-specific)
    """

    provider: str = "openai"
    model: str = "gpt-5-nano-2025-08-07"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: Optional[float] = None
    random_seed: Optional[int] = None
    safe_prompt: bool = True
    base_url: Optional[str] = None
    api_type: Optional[str] = None


# Default model mapping for different system types
SYSTEM_TYPE_MODEL_MAPPING = {
    SystemTypes.SYSTEM_1_OPERATIONS: {
        "groq": "llama-3.3-70b-versatile",
        "mistral": "mistral-small-latest",
        "openai": "gpt-5-nano-2025-08-07",
    },
    SystemTypes.SYSTEM_2_COORDINATION: {
        "groq": "llama-3.3-70b-versatile",
        "mistral": "mistral-medium-latest",
        "openai": "gpt-5-nano-2025-08-07",
    },
    SystemTypes.SYSTEM_3_CONTROL: {
        "groq": "llama-3.3-70b-versatile",
        "mistral": "mistral-medium-latest",
        "openai": "gpt-5-nano-2025-08-07",
    },
    SystemTypes.SYSTEM_4_INTELLIGENCE: {
        "groq": "llama-3.3-70b-versatile",
        "mistral": "mistral-large-latest",
        "openai": "gpt-5-nano-2025-08-07",
    },
    SystemTypes.SYSTEM_5_POLICY: {
        "groq": "llama-3.3-70b-versatile",
        "mistral": "mistral-large-latest",
        "openai": "gpt-5-nano-2025-08-07",
    },
}


def load_llm_config() -> LLMConfig:
    """
    Load LLM configuration from environment variables.

    Returns:
        LLMConfig instance with loaded configuration
    """
    # Determine provider from environment or use default
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()

    # Load API keys
    groq_api_key = get_secret("GROQ_API_KEY") or ""
    mistral_api_key = get_secret("MISTRAL_API_KEY") or ""
    openai_api_key = get_secret("OPENAI_API_KEY") or ""

    # Validate that the required API key is available
    if provider == "groq" and not groq_api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable is required for Groq provider"
        )
    if provider == "mistral" and not mistral_api_key:
        raise ValueError(
            "MISTRAL_API_KEY environment variable is required for Mistral provider"
        )
    if provider == "openai" and not openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required for OpenAI provider"
        )

    # Load common configuration
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "4096"))
    safe_prompt = os.environ.get("LLM_SAFE_PROMPT", "true").lower() == "true"

    # Load optional parameters
    top_p = None
    if "LLM_TOP_P" in os.environ:
        top_p_value = os.environ.get("LLM_TOP_P")
        if top_p_value:
            top_p = float(top_p_value)

    random_seed = None
    if "LLM_RANDOM_SEED" in os.environ:
        random_seed_value = os.environ.get("LLM_RANDOM_SEED")
        if random_seed_value:
            random_seed = int(random_seed_value)

    # Create base configuration
    config = LLMConfig(
        provider=provider,
        model=os.environ.get("LLM_MODEL", "mistral-small-latest"),
        api_key=(
            groq_api_key
            if provider == "groq"
            else mistral_api_key if provider == "mistral" else openai_api_key
        ),
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        random_seed=random_seed,
        safe_prompt=safe_prompt,
    )

    # Set provider-specific configuration
    if provider == "groq":
        config.base_url = os.environ.get(
            "GROQ_BASE_URL", "https://api.groq.com/openai/v1"
        )
        config.model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    elif provider == "mistral":
        config.api_type = "mistral"
        config.model = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
    elif provider == "openai":
        config.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        config.model = os.environ.get("OPENAI_MODEL", "gpt-5-nano-2025-08-07")

    return config


def get_model_for_system_type(system_type: str, provider: str) -> str:
    """
    Get the appropriate model for a system type and provider.

    Args:
        system_type: The system type (e.g., SystemTypes.SYSTEM_1_OPERATIONS)
        provider: The LLM provider ("groq", "mistral", or "openai")

    Returns:
        The recommended model name for the system type and provider
    """
    # Check if system type has specific model mapping
    if system_type in SYSTEM_TYPE_MODEL_MAPPING:
        provider_models = SYSTEM_TYPE_MODEL_MAPPING[system_type]
        if provider in provider_models:
            return provider_models[provider]

    # Fallback to default model for the provider
    if provider == "groq":
        return "llama-3.3-70b-versatile"
    if provider == "openai":
        return "gpt-5-nano-2025-08-07"
    return "mistral-small-latest"


def determine_system_type(agent_id: str) -> str:
    """
    Determine the system type from an agent ID.

    Args:
        agent_id: The agent ID string

    Returns:
        The system type constant from SystemTypes
    """
    if SystemTypes.SYSTEM_1_OPERATIONS in agent_id:
        return SystemTypes.SYSTEM_1_OPERATIONS
    elif SystemTypes.SYSTEM_2_COORDINATION in agent_id:
        return SystemTypes.SYSTEM_2_COORDINATION
    elif SystemTypes.SYSTEM_3_CONTROL in agent_id:
        return SystemTypes.SYSTEM_3_CONTROL
    elif SystemTypes.SYSTEM_4_INTELLIGENCE in agent_id:
        return SystemTypes.SYSTEM_4_INTELLIGENCE
    elif SystemTypes.SYSTEM_5_POLICY in agent_id:
        return SystemTypes.SYSTEM_5_POLICY
    else:
        # Default to System 1 if unknown
        return SystemTypes.SYSTEM_1_OPERATIONS
