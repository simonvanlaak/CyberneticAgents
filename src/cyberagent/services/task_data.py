from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from src.cyberagent.db.init_db import get_database_path
from src.enums import Status


@dataclass(frozen=True)
class TaskDetailView:
    id: int
    team_id: int
    team_name: str
    purpose_id: int | None
    purpose_name: str | None
    strategy_id: int | None
    strategy_name: str | None
    initiative_id: int | None
    initiative_name: str | None
    status: str
    assignee: str | None
    name: str
    content: str
    result: str | None
    reasoning: str | None
    execution_log: str | None
    case_judgement: str | None
    follow_up_task_id: int | None
    replaces_task_id: int | None


def _connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    return conn


def _task_column_expr(conn: sqlite3.Connection, column_name: str) -> str:
    columns = conn.execute("PRAGMA table_info(tasks)").fetchall()
    names = {str(row["name"]) for row in columns}
    if column_name in names:
        return f"t.{column_name}"
    return "NULL"


def _normalize_status(raw_status: object) -> str:
    text = str(raw_status or "").strip()
    valid_statuses = {status.value for status in Status}
    if text in valid_statuses:
        return text
    if "." in text:
        text = text.split(".")[-1]
    lowered = text.lower()
    if lowered in valid_statuses:
        return lowered
    return "unknown"


def load_task_detail(task_id: int) -> TaskDetailView | None:
    conn = _connect_db()
    result_expr = _task_column_expr(conn, "result")
    reasoning_expr = _task_column_expr(conn, "reasoning")
    execution_log_expr = _task_column_expr(conn, "execution_log")
    case_judgement_expr = _task_column_expr(conn, "case_judgement")
    follow_up_task_id_expr = _task_column_expr(conn, "follow_up_task_id")
    replaces_task_id_expr = _task_column_expr(conn, "replaces_task_id")
    query = f"""
        SELECT
            t.id AS task_id,
            t.team_id AS team_id,
            tm.name AS team_name,
            p.id AS purpose_id,
            p.name AS purpose_name,
            i.id AS initiative_id,
            i.name AS initiative_name,
            s.id AS strategy_id,
            s.name AS strategy_name,
            t.status AS status,
            t.assignee AS assignee,
            t.name AS task_name,
            t.content AS task_content,
            {result_expr} AS task_result,
            {reasoning_expr} AS task_reasoning,
            {execution_log_expr} AS task_execution_log,
            {case_judgement_expr} AS case_judgement,
            {follow_up_task_id_expr} AS follow_up_task_id,
            {replaces_task_id_expr} AS replaces_task_id
        FROM tasks t
        JOIN teams tm ON tm.id = t.team_id
        LEFT JOIN initiatives i ON i.id = t.initiative_id
        LEFT JOIN strategies s ON s.id = i.strategy_id
        LEFT JOIN purposes p ON p.id = s.purpose_id
        WHERE t.id = ?
    """
    try:
        row = conn.execute(query, (task_id,)).fetchone()
        if row is None:
            return None
        return TaskDetailView(
            id=int(row["task_id"]),
            team_id=int(row["team_id"]),
            team_name=str(row["team_name"]),
            purpose_id=int(row["purpose_id"]) if row["purpose_id"] is not None else None,
            purpose_name=(
                str(row["purpose_name"]) if row["purpose_name"] is not None else None
            ),
            strategy_id=(
                int(row["strategy_id"]) if row["strategy_id"] is not None else None
            ),
            strategy_name=(
                str(row["strategy_name"])
                if row["strategy_name"] is not None
                else None
            ),
            initiative_id=(
                int(row["initiative_id"]) if row["initiative_id"] is not None else None
            ),
            initiative_name=(
                str(row["initiative_name"])
                if row["initiative_name"] is not None
                else None
            ),
            status=_normalize_status(row["status"]),
            assignee=str(row["assignee"]) if row["assignee"] is not None else None,
            name=str(row["task_name"]),
            content=str(row["task_content"]),
            result=str(row["task_result"]) if row["task_result"] is not None else None,
            reasoning=(
                str(row["task_reasoning"]) if row["task_reasoning"] is not None else None
            ),
            execution_log=(
                str(row["task_execution_log"])
                if row["task_execution_log"] is not None
                else None
            ),
            case_judgement=(
                str(row["case_judgement"])
                if row["case_judgement"] is not None
                else None
            ),
            follow_up_task_id=(
                int(row["follow_up_task_id"])
                if row["follow_up_task_id"] is not None
                else None
            ),
            replaces_task_id=(
                int(row["replaces_task_id"])
                if row["replaces_task_id"] is not None
                else None
            ),
        )
    finally:
        conn.close()
