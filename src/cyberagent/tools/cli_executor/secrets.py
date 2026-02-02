"""Secrets resolution for CLI tool execution."""

import os
from typing import Dict, Iterable, List

TOOL_SECRET_ENV_VARS: Dict[str, List[str]] = {
    "web_search": ["BRAVE_API_KEY"],
    "git_readonly_sync": [],
}


def get_tool_secrets(
    tool_name: str, required_env: Iterable[str] | None = None
) -> Dict[str, str]:
    """
    Resolve required secrets for a tool from environment variables.

    Args:
        tool_name: CLI tool name (e.g., "web_search").
        required_env: Additional required environment variable names.

    Returns:
        Mapping of environment variable names to values.

    Raises:
        ValueError: If a required secret is missing from the environment.
    """
    required = _merge_required_env(
        TOOL_SECRET_ENV_VARS.get(tool_name, []), required_env
    )
    if not required:
        return {}

    if not _has_onepassword_auth():
        raise ValueError(
            "1Password authentication is required for tool secrets. "
            "Run the process via `op run` with a service account token or session."
        )

    missing = [key for key in required if not os.getenv(key)]
    if missing:
        missing_str = ", ".join(missing)
        raise ValueError(
            f"Missing required secrets for tool '{tool_name}': {missing_str}. "
            "Ensure your 1Password vault items use these exact secret names."
        )

    return {key: os.environ[key] for key in required}


def _merge_required_env(
    tool_required: Iterable[str], extra_required: Iterable[str] | None
) -> List[str]:
    merged: List[str] = []
    for key in list(tool_required) + list(extra_required or []):
        if key and key not in merged:
            merged.append(key)
    return merged


def _has_onepassword_auth() -> bool:
    if os.getenv("OP_SERVICE_ACCOUNT_TOKEN"):
        return True
    for key, value in os.environ.items():
        if key.startswith("OP_SESSION_") and value:
            return True
    return False
