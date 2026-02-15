"""Shared authorization DB URL resolution for Casbin enforcers."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from src.cyberagent.core.paths import get_data_dir


def resolve_authz_db_url(
    *,
    specific_env: str,
    default_filename: str,
) -> str:
    """
    Resolve DB URL for authorization enforcers.

    Precedence:
    1. CYBERAGENT_AUTHZ_DB_URL (shared source of truth)
    2. specific_env (enforcer-specific override)
    3. sqlite:///<data>/<default_filename>
    """
    shared = os.environ.get("CYBERAGENT_AUTHZ_DB_URL")
    if shared:
        _ensure_sqlite_parent(shared)
        return shared

    specific = os.environ.get(specific_env)
    if specific:
        _ensure_sqlite_parent(specific)
        return specific

    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / default_filename
    return f"sqlite:///{db_path}"


def _ensure_sqlite_parent(db_url: str) -> None:
    parsed = urlparse(db_url)
    if parsed.scheme != "sqlite":
        return
    raw_path = parsed.path or ""
    if not raw_path or raw_path == "/:memory:":
        return
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = Path(raw_path.lstrip("/"))
    if db_path.parent:
        db_path.parent.mkdir(parents=True, exist_ok=True)
