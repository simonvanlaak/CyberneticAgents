from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import threading
from typing import Generator

import pytest

from src.cyberagent.db import init_db
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import ensure_default_systems_for_team
from src.cyberagent.db.models.team import Team
from src.cyberagent.testing.pytest_worker import get_pytest_worker_id
from src.cyberagent.testing.thread_exceptions import ThreadExceptionTracker
from src.cyberagent.authz import skill_permissions_enforcer

_WORKER_ID = get_pytest_worker_id(os.environ, os.getpid())
_TEST_DB_ROOT = (Path(".pytest_db") / _WORKER_ID).resolve()
TEST_DB_PATH = (_TEST_DB_ROOT / "test.db").resolve()
TEST_SKILL_DB_PATH = (_TEST_DB_ROOT / "skill_permissions.db").resolve()
TEST_MEMORY_DB_PATH = (_TEST_DB_ROOT / "memory.db").resolve()


@pytest.fixture(scope="session", autouse=True)
def _initialize_test_db() -> None:
    os.environ["CYBERAGENT_DISABLE_BACKGROUND_DISCOVERY"] = "1"
    os.environ["MEMORY_SQLITE_PATH"] = str(TEST_MEMORY_DB_PATH)
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
def _thread_exception_guard() -> Generator[None, None, None]:
    tracker = ThreadExceptionTracker()
    original_hook = threading.excepthook
    threading.excepthook = tracker.handle
    try:
        yield
    finally:
        threading.excepthook = original_hook
        tracker.raise_if_any()


@pytest.fixture(autouse=True)
def _clear_active_team_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CYBERAGENT_ACTIVE_TEAM_ID", raising=False)
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.setenv(
        "CYBERAGENT_SKILL_PERMISSIONS_DB_URL",
        f"sqlite:///{TEST_SKILL_DB_PATH}",
    )
    monkeypatch.setenv("MEMORY_SQLITE_PATH", str(TEST_MEMORY_DB_PATH))
    if TEST_SKILL_DB_PATH.exists():
        os.chmod(TEST_SKILL_DB_PATH, 0o666)
        TEST_SKILL_DB_PATH.unlink()
    skill_permissions_enforcer._global_enforcer = None
    if TEST_DB_PATH.exists():
        os.chmod(TEST_DB_PATH, 0o666)
    if TEST_MEMORY_DB_PATH.exists():
        os.chmod(TEST_MEMORY_DB_PATH, 0o666)
        TEST_MEMORY_DB_PATH.unlink()
    session = next(get_db())
    try:
        for table in reversed(init_db.Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        team = Team(name="default_team", last_active_at=datetime.utcnow())
        session.add(team)
        session.commit()
        ensure_default_systems_for_team(team.id)
    finally:
        session.close()
