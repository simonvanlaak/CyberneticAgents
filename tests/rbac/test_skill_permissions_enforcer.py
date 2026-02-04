from __future__ import annotations

from pathlib import Path

import pytest

from src.rbac import skill_permissions_enforcer


def test_skill_permissions_enforcer_honors_db_url_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "skill_permissions.db"
    if db_path.exists():
        db_path.unlink()
    monkeypatch.setenv("CYBERAGENT_SKILL_PERMISSIONS_DB_URL", f"sqlite:///{db_path}")
    skill_permissions_enforcer._global_enforcer = None

    enforcer = skill_permissions_enforcer.get_enforcer()
    enforcer.add_policy("system:1", "team:1", "skill:test", "allow")
    enforcer.save_policy()

    assert db_path.exists()
