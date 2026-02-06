from __future__ import annotations

from pathlib import Path

from src.cyberagent.db import init_db


def test_get_database_path_uses_cyberagent_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CYBERAGENT_ROOT", str(tmp_path))
    monkeypatch.delenv("CYBERAGENT_DB_URL", raising=False)
    previous_url = init_db.DATABASE_URL
    previous_from_env = init_db._DATABASE_URL_FROM_ENV
    try:
        init_db.configure_database("sqlite:///:memory:", from_env=True)
        db_path = init_db.get_database_path()
        assert db_path == str((tmp_path / "data" / "CyberneticAgents.db").resolve())
    finally:
        init_db.configure_database(previous_url, from_env=previous_from_env)
