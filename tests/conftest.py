from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

import pytest

from src.cyberagent.db import init_db
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import ensure_default_systems_for_team
from src.cyberagent.db.models.recursion import Recursion
from src.cyberagent.db.models.team import Team
from src.rbac import skill_permissions_enforcer

TEST_DB_PATH = (Path(".pytest_db") / "test.db").resolve()
TEST_SKILL_DB_PATH = (Path(".pytest_db") / "skill_permissions.db").resolve()


def pytest_configure() -> None:
    tmp_root = TEST_DB_PATH.parent
    tmp_root.mkdir(parents=True, exist_ok=True)
    db_path = TEST_DB_PATH
    if db_path.exists():
        os.chmod(db_path, 0o666)
        db_path.unlink()
    init_db.configure_database(f"sqlite:///{db_path}")
    init_db.init_db()
    if db_path.exists():
        os.chmod(db_path, 0o666)
    os.environ["CYBERAGENT_SKILL_PERMISSIONS_DB_URL"] = (
        f"sqlite:///{TEST_SKILL_DB_PATH}"
    )
    if TEST_SKILL_DB_PATH.exists():
        os.chmod(TEST_SKILL_DB_PATH, 0o666)
        TEST_SKILL_DB_PATH.unlink()
    session = next(get_db())
    try:
        team = Team(name="default_team", last_active_at=datetime.utcnow())
        session.add(team)
        session.commit()
        ensure_default_systems_for_team(team.id)
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clear_active_team_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CYBERAGENT_ACTIVE_TEAM_ID", raising=False)
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.setenv(
        "CYBERAGENT_SKILL_PERMISSIONS_DB_URL",
        f"sqlite:///{TEST_SKILL_DB_PATH}",
    )
    if TEST_SKILL_DB_PATH.exists():
        os.chmod(TEST_SKILL_DB_PATH, 0o666)
        TEST_SKILL_DB_PATH.unlink()
    skill_permissions_enforcer._global_enforcer = None
    if TEST_DB_PATH.exists():
        os.chmod(TEST_DB_PATH, 0o666)
    session = next(get_db())
    try:
        session.query(Recursion).delete()
        session.commit()
    finally:
        session.close()
