from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from src.cyberagent.db import init_db


def test_ensure_task_lineage_columns_and_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "tasks-lineage.db"
    previous = init_db.DATABASE_URL
    previous_from_env = init_db._DATABASE_URL_FROM_ENV
    try:
        init_db.configure_database(f"sqlite:///{db_path.resolve()}")
        with init_db.engine.begin() as connection:
            connection.execute(text("""
                    CREATE TABLE tasks (
                        id INTEGER PRIMARY KEY,
                        team_id INTEGER NOT NULL,
                        initiative_id INTEGER,
                        status TEXT,
                        assignee TEXT,
                        name TEXT,
                        content TEXT,
                        result TEXT,
                        reasoning TEXT,
                        execution_log TEXT,
                        policy_judgement TEXT,
                        policy_judgement_reasoning TEXT,
                        case_judgement TEXT
                    )
                    """))

        init_db._ensure_task_follow_up_task_id_column()
        init_db._ensure_task_replaces_task_id_column()
        init_db._ensure_task_invalid_review_retry_count_column()

        with init_db.engine.connect() as connection:
            columns = connection.execute(text("PRAGMA table_info(tasks);")).fetchall()
            indexes = connection.execute(text("PRAGMA index_list(tasks);")).fetchall()

        names = {str(column[1]) for column in columns}
        index_names = {str(index[1]) for index in indexes}

        assert "follow_up_task_id" in names
        assert "replaces_task_id" in names
        assert "invalid_review_retry_count" in names
        assert "idx_tasks_follow_up_task_id" in index_names
        assert "idx_tasks_replaces_task_id" in index_names
    finally:
        init_db.configure_database(previous, from_env=previous_from_env)
