from __future__ import annotations

from pathlib import Path

from src import init_db


def pytest_configure() -> None:
    tmp_root = Path(".pytest_db").resolve()
    tmp_root.mkdir(parents=True, exist_ok=True)
    db_path = tmp_root / "test.db"
    init_db.configure_database(f"sqlite:///{db_path}")
    init_db.init_db()
