"""Shared secret loading helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

VAULT_NAME = "CyberneticAgents"
FIELD_LABEL = "credential"


def has_onepassword_auth() -> bool:
    """Return True when a 1Password service account token or session is present."""
    if os.getenv("OP_SERVICE_ACCOUNT_TOKEN"):
        return True
    return _get_onepassword_session_env() is not None


def _get_onepassword_session_env() -> str | None:
    for key, value in os.environ.items():
        if key.startswith("OP_SESSION_") and value:
            return value
    return None


def load_secret_from_1password(
    item_name: str,
    *,
    vault_name: str = VAULT_NAME,
    field_label: str = FIELD_LABEL,
) -> str | None:
    if not shutil.which("op"):
        return None
    if not has_onepassword_auth():
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


def get_secret(name: str) -> str | None:
    """Return the secret from env or 1Password, caching to env when loaded."""
    value = os.getenv(name)
    if value:
        return value
    loaded = load_secret_from_1password(item_name=name)
    if loaded:
        os.environ.setdefault(name, loaded)
    return loaded


def store_secret_in_1password(
    item_name: str,
    value: str,
    *,
    vault_name: str = VAULT_NAME,
    field_label: str = FIELD_LABEL,
) -> bool:
    if not shutil.which("op"):
        return False
    if not has_onepassword_auth():
        return False
    create_result = subprocess.run(
        [
            "op",
            "item",
            "create",
            "--category",
            "API Credential",
            "--vault",
            vault_name,
            "--title",
            item_name,
            f"{field_label}={value}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if create_result.returncode == 0:
        return True
    edit_result = subprocess.run(
        [
            "op",
            "item",
            "edit",
            item_name,
            f"{field_label}={value}",
            "--vault",
            vault_name,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return edit_result.returncode == 0
