from __future__ import annotations

import sqlite3

from src.cyberagent.cli.agent_message_queue import enqueue_agent_message
from src.cyberagent.db.init_db import get_database_path


def queue_in_progress_initiatives(team_id: int) -> int:
    """
    Queue initiative_assign messages for in-progress initiatives to System3.

    This allows runtime startup to resume control flow for initiatives that were
    already in progress before the runtime stopped.
    """
    db_path = get_database_path()
    queued = 0
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM initiatives WHERE team_id = ? "
                "AND UPPER(status) = ? ORDER BY id",
                (team_id, "IN_PROGRESS"),
            )
            initiative_ids = [int(row["id"]) for row in cursor.fetchall()]
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
                "source": "System4/root",
                "content": f"Resume initiative {initiative_id}.",
            },
        )
        queued += 1
    return queued
