from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

VAULT_NAME = "CyberneticAgents"


def has_onepassword_auth() -> bool:
    if not os.getenv("OP_SERVICE_ACCOUNT_TOKEN"):
        _load_service_account_token_from_env_file()
    return bool(os.getenv("OP_SERVICE_ACCOUNT_TOKEN")) or bool(
        get_onepassword_session_env()
    )


def get_onepassword_session_env() -> str | None:
    for key, value in os.environ.items():
        if key.startswith("OP_SESSION_") and value:
            return value
    return None


def _load_service_account_token_from_env_file() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    try:
        content = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in content.splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        key = key.strip()
        if key != "OP_SERVICE_ACCOUNT_TOKEN":
            continue
        token = _parse_env_value(value)
        if token:
            os.environ["OP_SERVICE_ACCOUNT_TOKEN"] = token
        return


def _parse_env_value(value: str) -> str | None:
    trimmed = value.strip()
    if not trimmed:
        return None
    if trimmed.startswith(("'", '"')) and trimmed.endswith(("'", '"')):
        return trimmed[1:-1].strip()
    return trimmed


def load_secret_from_1password(
    *, vault_name: str, item_name: str, field_label: str
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
