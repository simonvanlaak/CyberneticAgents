"""Casbin enforcer helpers for skill permissions."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import casbin
import casbin_sqlalchemy_adapter

logger = logging.getLogger(__name__)

_global_enforcer: casbin.Enforcer | None = None


def get_enforcer() -> casbin.Enforcer:
    """
    Return the global skill-permissions enforcer.

    Creates the enforcer on first access and reuses it across calls.
    """
    global _global_enforcer
    if _global_enforcer is None:
        _global_enforcer = _create_enforcer()
    return _global_enforcer


def _create_enforcer() -> casbin.Enforcer:
    """
    Create a new Casbin enforcer for skill permissions.
    """
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "skill_permissions.db"
    adapter = casbin_sqlalchemy_adapter.Adapter(f"sqlite:///{db_path}")
    model_path = os.path.join(os.path.dirname(__file__), "skill_permissions_model.conf")
    enforcer = casbin.Enforcer(model_path, adapter)
    enforcer.enable_auto_save(True)
    return enforcer
