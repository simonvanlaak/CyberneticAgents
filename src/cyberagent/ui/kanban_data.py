from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from src.cyberagent.db.init_db import get_database_path
from src.enums import Status

KANBAN_STATUSES = [status.value for status in Status]


@dataclass(frozen=True)
class TaskCard:
    id: int
    team_id: int
    team_name: str
    purpose_id: Optional[int]
    purpose_name: Optional[str]
    strategy_id: Optional[int]
    strategy_name: Optional[str]
    initiative_id: Optional[int]
    initiative_name: Optional[str]
    status: str
    assignee: Optional[str]
    name: str
    content: str
    result: Optional[str]
    reasoning: Optional[str]
    execution_log: Optional[str]
    case_judgement: Optional[str]
    follow_up_task_id: Optional[int] = None
    replaces_task_id: Optional[int] = None


@dataclass(frozen=True)
class InitiativeKanbanRow:
    team_id: int
    team_name: str
    purpose_id: Optional[int]
    purpose_name: Optional[str]
    strategy_id: Optional[int]
    strategy_name: Optional[str]
    initiative_id: Optional[int]
    initiative_name: Optional[str]
    tasks_by_status: dict[str, list[TaskCard]]


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
    if text in KANBAN_STATUSES:
        return text
    if "." in text:
        text = text.split(".")[-1]
    lowered = text.lower()
    if lowered in KANBAN_STATUSES:
        return lowered
    return "unknown"


def load_task_cards(
    *,
    team_id: int | None = None,
    strategy_id: int | None = None,
    initiative_id: int | None = None,
    assignee: str | None = None,
) -> list[TaskCard]:
    """
    Load task cards with hierarchy metadata for read-only Kanban rendering.

    Args:
        team_id: Optional team filter.
        strategy_id: Optional strategy filter.
        initiative_id: Optional initiative filter.
        assignee: Optional assignee filter.
    """
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
        WHERE 1 = 1
    """
    params: list[object] = []

    if team_id is not None:
        query += " AND t.team_id = ?"
        params.append(team_id)
    if strategy_id is not None:
        query += " AND s.id = ?"
        params.append(strategy_id)
    if initiative_id is not None:
        query += " AND i.id = ?"
        params.append(initiative_id)
    if assignee is not None:
        query += " AND t.assignee = ?"
        params.append(assignee)

    query += " ORDER BY t.id"

    try:
        cursor = conn.cursor()
        rows = cursor.execute(query, tuple(params)).fetchall()
        return [
            TaskCard(
                id=int(row["task_id"]),
                team_id=int(row["team_id"]),
                team_name=str(row["team_name"]),
                purpose_id=(
                    int(row["purpose_id"]) if row["purpose_id"] is not None else None
                ),
                purpose_name=(
                    str(row["purpose_name"])
                    if row["purpose_name"] is not None
                    else None
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
                    int(row["initiative_id"])
                    if row["initiative_id"] is not None
                    else None
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
                result=(
                    str(row["task_result"]) if row["task_result"] is not None else None
                ),
                reasoning=(
                    str(row["task_reasoning"])
                    if row["task_reasoning"] is not None
                    else None
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
            for row in rows
        ]
    finally:
        conn.close()


def load_task_detail(task_id: int) -> Optional[TaskCard]:
    """
    Load one task card by id with hierarchy and review fields.

    Args:
        task_id: Task identifier.
    """
    tasks = load_task_cards()
    for task in tasks:
        if task.id == task_id:
            return task
    return None


def group_tasks_by_status(tasks: list[TaskCard]) -> dict[str, list[TaskCard]]:
    """
    Group tasks into stable Kanban status columns.

    Unknown statuses are ignored to keep board columns consistent.
    """
    grouped: dict[str, list[TaskCard]] = {status: [] for status in KANBAN_STATUSES}
    for task in tasks:
        if task.status in grouped:
            grouped[task.status].append(task)
    return grouped


def group_tasks_by_hierarchy(tasks: list[TaskCard]) -> list[InitiativeKanbanRow]:
    """
    Build initiative-level Kanban rows sorted like `status` hierarchy traversal.

    Sort order: team_id, purpose_id, strategy_id, initiative_id.
    """
    buckets: dict[
        tuple[int, Optional[int], Optional[int], Optional[int]], list[TaskCard]
    ] = {}
    for task in tasks:
        key = (task.team_id, task.purpose_id, task.strategy_id, task.initiative_id)
        buckets.setdefault(key, []).append(task)

    def _sort_key(
        key: tuple[int, Optional[int], Optional[int], Optional[int]],
    ) -> tuple[int, int, int, int]:
        team_id, purpose_id, strategy_id, initiative_id = key
        return (
            team_id,
            purpose_id if purpose_id is not None else 0,
            strategy_id if strategy_id is not None else 0,
            initiative_id if initiative_id is not None else 0,
        )

    rows: list[InitiativeKanbanRow] = []
    for key in sorted(buckets.keys(), key=_sort_key):
        bucket_tasks = sorted(buckets[key], key=lambda task: task.id)
        if bucket_tasks and all(
            task.status == Status.COMPLETED.value for task in bucket_tasks
        ):
            continue
        first = bucket_tasks[0]
        rows.append(
            InitiativeKanbanRow(
                team_id=first.team_id,
                team_name=first.team_name,
                purpose_id=first.purpose_id,
                purpose_name=first.purpose_name,
                strategy_id=first.strategy_id,
                strategy_name=first.strategy_name,
                initiative_id=first.initiative_id,
                initiative_name=first.initiative_name,
                tasks_by_status=group_tasks_by_status(bucket_tasks),
            )
        )
    return rows
