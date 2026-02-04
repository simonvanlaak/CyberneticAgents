from __future__ import annotations

import os
from pathlib import Path


def _find_env_file(start: Path) -> Path | None:
    for path in [start, *start.parents]:
        candidate = path / ".env"
        if candidate.exists():
            return candidate
    return None


def load_op_service_account_token() -> None:
    env_path = _find_env_file(Path.cwd())
    if os.environ.get("OP_SERVICE_ACCOUNT_TOKEN") or env_path is None:
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
        if key.strip() != "OP_SERVICE_ACCOUNT_TOKEN":
            continue
        token = _parse_env_value(value)
        if token:
            os.environ.setdefault("OP_SERVICE_ACCOUNT_TOKEN", token)
        return


def _parse_env_value(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()
    return cleaned or None
