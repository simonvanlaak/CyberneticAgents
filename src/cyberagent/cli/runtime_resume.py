from __future__ import annotations

import sqlite3

from src.cyberagent.cli.agent_message_queue import enqueue_agent_message
from src.cyberagent.core.agent_naming import normalize_message_source
from src.cyberagent.db.init_db import get_database_path


def queue_in_progress_initiatives(team_id: int) -> int:
    """
    Queue startup-resume messages to System3.

    This allows runtime startup to resume control flow for initiatives that were
    already in progress before the runtime stopped, and to backfill task review
    for completed-but-unapproved tasks.
    """
    db_path = get_database_path()
    queued = 0
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT i.id FROM initiatives i "
                "WHERE i.team_id = ? AND ("
                "UPPER(i.status) = ? OR ("
                "UPPER(i.status) = ? AND EXISTS ("
                "SELECT 1 FROM tasks t WHERE t.team_id = i.team_id "
                "AND t.initiative_id = i.id"
                ")"
                ")) ORDER BY i.id",
                (team_id, "IN_PROGRESS", "PENDING"),
            )
            initiative_ids = [int(row["id"]) for row in cursor.fetchall()]
            cursor.execute(
                "SELECT id, assignee, COALESCE(reasoning, result, content, name, '') AS review_content "
                "FROM tasks WHERE team_id = ? AND UPPER(status) IN (?, ?) "
                "AND assignee IS NOT NULL AND assignee != '' ORDER BY id",
                (team_id, "COMPLETED", "BLOCKED"),
            )
            review_tasks = [
                (
                    int(row["id"]),
                    str(row["assignee"]),
                    str(row["review_content"]),
                )
                for row in cursor.fetchall()
            ]
            cursor.execute(
                "SELECT agent_id_str FROM systems WHERE team_id = ? "
                "AND UPPER(type) = ? ORDER BY id LIMIT 1",
                (team_id, "CONTROL"),
            )
            control_row = cursor.fetchone()
            recipient = (
                str(control_row["agent_id_str"])
                if control_row is not None and control_row["agent_id_str"]
                else "System3/root"
            )
        finally:
            conn.close()
    except sqlite3.Error:
        return 0

    for initiative_id in initiative_ids:
        enqueue_agent_message(
            recipient=recipient,
            sender="System4/root",
            message_type="initiative_assign",
            payload={
                "initiative_id": initiative_id,
                "source": normalize_message_source("System4/root"),
                "content": f"Resume initiative {initiative_id}.",
            },
        )
        queued += 1

    for task_id, assignee, review_content in review_tasks:
        enqueue_agent_message(
            recipient=recipient,
            sender=assignee,
            message_type="task_review",
            payload={
                "task_id": task_id,
                "assignee_agent_id_str": assignee,
                "source": normalize_message_source(assignee),
                "content": review_content or f"Review completed task {task_id}.",
            },
        )
        queued += 1
    return queued
