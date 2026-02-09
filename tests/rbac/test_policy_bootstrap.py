from __future__ import annotations

from pathlib import Path

import pytest

from src.rbac import enforcer as tools_enforcer
from src.rbac import skill_permissions_enforcer
from src.rbac.policy_bootstrap import (
    BOOTSTRAP_RESOURCE,
    BOOTSTRAP_SUBJECT,
    BOOTSTRAP_VERSION,
)


def test_tool_enforcer_bootstrap_marker_is_seeded_and_versioned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "rbac.db"
    monkeypatch.setenv("CYBERAGENT_RBAC_DB_URL", f"sqlite:///{db_path}")
    monkeypatch.delenv("CYBERAGENT_AUTHZ_DB_URL", raising=False)
    tools_enforcer._global_enforcer = None

    enforcer = tools_enforcer.get_enforcer()
    marker = [BOOTSTRAP_SUBJECT, "tools", BOOTSTRAP_RESOURCE, BOOTSTRAP_VERSION]
    assert enforcer.has_policy(*marker) is True

    enforcer.remove_policy(*marker)
    enforcer.add_policy(BOOTSTRAP_SUBJECT, "tools", BOOTSTRAP_RESOURCE, "old-version")
    enforcer.save_policy()

    tools_enforcer._global_enforcer = None
    refreshed = tools_enforcer.get_enforcer()
    assert refreshed.has_policy(*marker) is True
    assert (
        refreshed.has_policy(
            BOOTSTRAP_SUBJECT, "tools", BOOTSTRAP_RESOURCE, "old-version"
        )
        is False
    )


def test_skill_enforcer_bootstrap_marker_is_seeded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "skills.db"
    monkeypatch.setenv("CYBERAGENT_SKILL_PERMISSIONS_DB_URL", f"sqlite:///{db_path}")
    monkeypatch.delenv("CYBERAGENT_AUTHZ_DB_URL", raising=False)
    skill_permissions_enforcer._global_enforcer = None

    enforcer = skill_permissions_enforcer.get_enforcer()
    marker = [BOOTSTRAP_SUBJECT, "skills", BOOTSTRAP_RESOURCE, BOOTSTRAP_VERSION]
    assert enforcer.has_policy(*marker) is True
