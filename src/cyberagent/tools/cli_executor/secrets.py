"""Secrets resolution for CLI tool execution."""

import json
import os
import shutil
import subprocess
from typing import Dict, Iterable, List

TOOL_SECRET_ENV_VARS: Dict[str, List[str]] = {
    # Tool names used by skills (and common variants).
    "web_search": ["BRAVE_API_KEY"],
    "web-search": ["BRAVE_API_KEY"],
    "web_fetch": [],
    "web-fetch": [],
    "file_reader": [],
    "file-reader": [],
    "git_readonly_sync": [],
    "git-readonly-sync": [],
}
VAULT_NAME = "CyberneticAgents"
FIELD_LABEL = "credential"


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

    secrets_map: Dict[str, str] = {}
    missing: list[str] = []
    for key in required:
        value = os.getenv(key)
        if value:
            secrets_map[key] = value
            continue
        loaded = _load_secret_from_1password(
            vault_name=VAULT_NAME,
            item_name=key,
            field_label=FIELD_LABEL,
        )
        if loaded:
            secrets_map[key] = loaded
        else:
            missing.append(key)
    if missing:
        missing_str = ", ".join(missing)
        raise ValueError(
            f"Missing required secrets for tool '{tool_name}': {missing_str}. "
            "Ensure your 1Password vault items use these exact secret names."
        )

    return secrets_map


def _merge_required_env(
    tool_required: Iterable[str], extra_required: Iterable[str] | None
) -> List[str]:
    merged: List[str] = []
    for key in list(tool_required) + list(extra_required or []):
        if key and key not in merged:
            merged.append(key)
    return merged


def _has_onepassword_auth() -> bool:
    return bool(os.getenv("OP_SERVICE_ACCOUNT_TOKEN"))


def _load_secret_from_1password(
    vault_name: str, item_name: str, field_label: str
) -> str | None:
    if not shutil.which("op"):
        return None
    if not _has_onepassword_auth():
        return None
    result = subprocess.run(
        [
            "op",
            "item",
            "get",
            item_name,
            "--vault",
            vault_name,
            "--fields",
            f"label={field_label}",
            "--reveal",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, list) and payload:
        value = payload[0].get("value") if isinstance(payload[0], dict) else None
        return value if isinstance(value, str) and value else None
    if isinstance(payload, dict):
        value = payload.get("value")
        return value if isinstance(value, str) and value else None
    return None
