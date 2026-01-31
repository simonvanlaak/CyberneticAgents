from __future__ import annotations

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
