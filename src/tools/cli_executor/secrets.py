"""
Secrets resolution for OpenClaw tool execution.
"""

import os
from typing import Dict, List

TOOL_SECRET_ENV_VARS: Dict[str, List[str]] = {
    "web_search": ["BRAVE_API_KEY"],
}


def get_tool_secrets(tool_name: str) -> Dict[str, str]:
    """
    Resolve required secrets for a tool from environment variables.

    Args:
        tool_name: OpenClaw tool name (e.g., "web_search").

    Returns:
        Mapping of environment variable names to values.

    Raises:
        ValueError: If a required secret is missing from the environment.
    """
    required = TOOL_SECRET_ENV_VARS.get(tool_name, [])
    if not required:
        return {}

    missing = [key for key in required if not os.getenv(key)]
    if missing:
        missing_str = ", ".join(missing)
        raise ValueError(
            f"Missing required secrets for tool '{tool_name}': {missing_str}. "
            "Ensure your 1Password vault items use these exact secret names."
        )

    return {key: os.environ[key] for key in required}
