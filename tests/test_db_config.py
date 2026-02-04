from __future__ import annotations

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
