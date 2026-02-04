from __future__ import annotations

from pathlib import Path

import pytest

from src import init_db


def test_configure_database_updates_path(tmp_path) -> None:
    db_path = tmp_path / "alt.db"
    previous = init_db.DATABASE_URL
    try:
        init_db.configure_database(f"sqlite:///{db_path.resolve()}")
        assert init_db.get_database_path() == str(db_path)
    finally:
        init_db.configure_database(previous)


def test_configure_database_relative_path() -> None:
    previous = init_db.DATABASE_URL
    try:
        init_db.configure_database("sqlite:///data/relative.db")
        assert init_db.get_database_path() == "data/relative.db"
    finally:
        init_db.configure_database(previous)


def test_init_db_raises_when_db_path_is_directory(tmp_path) -> None:
    db_path = tmp_path / "db_dir"
    db_path.mkdir()
    previous = init_db.DATABASE_URL
    try:
        init_db.configure_database(f"sqlite:///{db_path.resolve()}")
        with pytest.raises(ValueError, match="Expected file path"):
            init_db.init_db()
    finally:
        init_db.configure_database(previous)


def test_init_db_raises_when_db_dir_not_writable(tmp_path) -> None:
    db_dir = tmp_path / "locked"
    db_dir.mkdir()
    db_path = db_dir / "db.sqlite"
    previous = init_db.DATABASE_URL
    try:
        db_dir.chmod(0o500)
        init_db.configure_database(f"sqlite:///{db_path.resolve()}")
        with pytest.raises(PermissionError, match="not writable"):
            init_db.init_db()
    finally:
        db_dir.chmod(0o700)
        init_db.configure_database(previous)


def test_init_db_recovers_from_sqlite_disk_io_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "bad.db"
    db_path.write_text("corrupt", encoding="utf-8")
    previous = init_db.DATABASE_URL
    original_configure = init_db.configure_database
    try:
        init_db.configure_database(f"sqlite:///{db_path.resolve()}")
        call_state = {"count": 0}
        configured: list[str] = []

        def _fake_create_all(*_args: object, **_kwargs: object) -> None:
            call_state["count"] += 1
            if call_state["count"] == 1:
                raise init_db.OperationalError(
                    "disk I/O error", None, Exception("disk I/O error")
                )

        monkeypatch.setattr(init_db.Base.metadata, "create_all", _fake_create_all)
        monkeypatch.setattr(
            init_db,
            "configure_database",
            lambda url: configured.append(url),
        )
        monkeypatch.setattr(init_db, "_ensure_team_last_active_column", lambda: None)

        init_db.init_db()

        backups = list(tmp_path.glob("bad.corrupt.*.db"))
        assert backups
        assert call_state["count"] == 2
        assert configured
    finally:
        original_configure(previous)
