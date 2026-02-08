# -*- coding: utf-8 -*-
"""
Model Client Factory

This module provides a factory for creating model clients for different LLM providers.
"""

from typing import Any

from autogen_core.models import ModelInfo
from autogen_ext.models.openai import OpenAIChatCompletionClient

from src.llm_config import LLMConfig


def create_model_client(config: LLMConfig) -> Any:
    """
    Create a model client based on the provided configuration.

    Args:
        config: LLM configuration

    Returns:
        Model client instance

    Raises:
        ValueError: If provider is not supported
    """
    if config.provider == "groq":
        return _create_groq_client(config)
    elif config.provider == "openai":
        return _create_openai_client(config)
    elif config.provider == "mistral":
        return _create_mistral_client(config)
    else:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")


def _create_groq_client(config: LLMConfig) -> OpenAIChatCompletionClient:
    """
    Create a Groq model client using OpenAI-compatible API.

    Args:
        config: LLM configuration

    Returns:
        OpenAIChatCompletionClient configured for Groq
    """
    return OpenAIChatCompletionClient(
        model=config.model,
        base_url=config.base_url or "https://api.groq.com/openai/v1",
        api_key=config.api_key,
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=False,
            family="unknown",
            structured_output=False,
        ),
    )


def _create_openai_client(config: LLMConfig) -> OpenAIChatCompletionClient:
    """
    Create an OpenAI model client.

    Args:
        config: LLM configuration

    Returns:
        OpenAIChatCompletionClient configured for OpenAI
    """
    return OpenAIChatCompletionClient(
        model=config.model,
        base_url=config.base_url or "https://api.openai.com/v1",
        api_key=config.api_key,
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=False,
            family="unknown",
            structured_output=False,
        ),
    )


def _create_mistral_client(config: LLMConfig) -> Any:
    """
    Create a Mistral model client.

    Args:
        config: LLM configuration

    Returns:
        Mistral model client instance

    Note:
        This implementation uses the Mistral AI client class from AutoGen.
        The actual implementation may need to be adjusted based on the
        available Mistral client in the autogen-ext package.
    """
    try:
        # Try to import Mistral client from autogen-ext
        from autogen_ext.models.mistral import (  # type: ignore[import]
            MistralChatCompletionClient,
        )

        # Create Mistral client configuration
        mistral_config = {
            "model": config.model,
            "api_key": config.api_key,
            "api_type": "mistral",
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }

        # Add optional parameters if specified
        if config.top_p is not None:
            mistral_config["top_p"] = config.top_p
        if config.random_seed is not None:
            mistral_config["random_seed"] = config.random_seed
        if config.safe_prompt is not None:
            mistral_config["safe_prompt"] = config.safe_prompt

        return MistralChatCompletionClient(**mistral_config)

    except ImportError:
        # Fallback: Use OpenAI-compatible approach for Mistral
        # This may not support all Mistral-specific features
        return OpenAIChatCompletionClient(
            model=config.model,
            base_url="https://api.mistral.ai/v1",
            api_key=config.api_key,
            model_info=ModelInfo(
                vision=False,
                function_calling=True,
                json_output=False,
                family="unknown",
                structured_output=False,
            ),
        )


def get_available_providers() -> list:
    """
    Get list of available LLM providers.

    Returns:
        List of available provider names
    """
    return ["groq", "mistral", "openai"]


def validate_config(config: LLMConfig) -> bool:
    """
    Validate LLM configuration.

    Args:
        config: LLM configuration to validate

    Returns:
        True if configuration is valid, False otherwise
    """
    if not config.provider:
        return False

    if config.provider not in get_available_providers():
        return False

    if not config.api_key:
        return False

    if not config.model:
        return False

    if config.temperature < 0 or config.temperature > 1:
        return False

    if config.max_tokens <= 0:
        return False

    return True


# Now let me update the VSM agent to use the new configuration system:
