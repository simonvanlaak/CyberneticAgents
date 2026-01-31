import json
import sqlite3
import uuid

from src.cli.status import collect_status, render_status, render_status_json
from src.db_utils import get_db
from src.init_db import init_db
from src.models.purpose import Purpose
from src.models.team import Team


def _create_team_id() -> int:
    team = Team(name=f"status_team_{uuid.uuid4().hex}")
    db = next(get_db())
    db.add(team)
    db.commit()
    return team.id


def _insert_strategy(
    team_id: int, purpose_id: int, name: str, description: str, status: str
) -> int:
    conn = sqlite3.connect("data/CyberneticAgents.db")
    try:
        cursor = conn.execute(
            "INSERT INTO strategies "
            "(team_id, purpose_id, status, name, description, result) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (team_id, purpose_id, status, name, description, ""),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def _insert_initiative(
    team_id: int, strategy_id: int, name: str, description: str, status: str
) -> int:
    conn = sqlite3.connect("data/CyberneticAgents.db")
    try:
        cursor = conn.execute(
            "INSERT INTO initiatives "
            "(team_id, strategy_id, status, name, description, result) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (team_id, strategy_id, status, name, description, None),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def _insert_task(
    team_id: int,
    initiative_id: int,
    name: str,
    content: str,
    status: str,
    assignee: str | None,
) -> int:
    conn = sqlite3.connect("data/CyberneticAgents.db")
    try:
        cursor = conn.execute(
            "INSERT INTO tasks "
            "(team_id, initiative_id, status, assignee, name, content, result) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (team_id, initiative_id, status, assignee, name, content, None),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def test_status_render_includes_hierarchy():
    init_db()
    team_id = _create_team_id()
    purpose = Purpose(
        team_id=team_id,
        name="Purpose Alpha",
        content="Purpose content.",
    )
    purpose_id = purpose.add()
    strategy_id = _insert_strategy(
        team_id=team_id,
        purpose_id=purpose_id,
        name="Strategy Alpha",
        description="Strategy description.",
        status="in_progress",
    )
    initiative_id = _insert_initiative(
        team_id=team_id,
        strategy_id=strategy_id,
        name="Initiative Alpha",
        description="Initiative description.",
        status="pending",
    )
    task_one_id = _insert_task(
        team_id=team_id,
        initiative_id=initiative_id,
        name="Task One",
        content="Task one content.",
        status="pending",
        assignee="root_operations_alpha",
    )
    task_two_id = _insert_task(
        team_id=team_id,
        initiative_id=initiative_id,
        name="Task Two",
        content="Task two content.",
        status="completed",
        assignee=None,
    )

    output = render_status(collect_status(team_id=team_id, active_only=False))

    assert f"Team {team_id}:" in output
    assert f"Purpose {purpose_id}: Purpose Alpha" in output
    assert "Content: Purpose content." in output
    assert f"Strategy {strategy_id} [in_progress]: Strategy Alpha" in output
    assert "Description: Strategy description." in output
    assert f"Initiative {initiative_id} [pending]: Initiative Alpha" in output
    assert "Description: Initiative description." in output
    assert (
        f"Task {task_one_id} [pending] (assignee: root_operations_alpha) - Task One"
        in output
    )
    assert f"Task {task_two_id} [completed] (assignee: -) - Task Two" in output


def test_status_active_only_filters_completed_tasks():
    init_db()
    team_id = _create_team_id()
    purpose = Purpose(
        team_id=team_id,
        name="Purpose Beta",
        content="Purpose content.",
    )
    purpose_id = purpose.add()
    strategy_id = _insert_strategy(
        team_id=team_id,
        purpose_id=purpose_id,
        name="Strategy Beta",
        description="Strategy description.",
        status="in_progress",
    )
    initiative_id = _insert_initiative(
        team_id=team_id,
        strategy_id=strategy_id,
        name="Initiative Beta",
        description="Initiative description.",
        status="pending",
    )
    task_pending_id = _insert_task(
        team_id=team_id,
        initiative_id=initiative_id,
        name="Task Pending",
        content="Pending content.",
        status="pending",
        assignee=None,
    )
    task_completed_id = _insert_task(
        team_id=team_id,
        initiative_id=initiative_id,
        name="Task Completed",
        content="Completed content.",
        status="completed",
        assignee=None,
    )

    output = render_status(collect_status(team_id=team_id, active_only=True))

    assert f"Task {task_pending_id} [pending]" in output
    assert f"Task {task_completed_id} [completed]" not in output


def test_status_json_output_includes_fields():
    init_db()
    team_id = _create_team_id()
    purpose = Purpose(
        team_id=team_id,
        name="Purpose JSON",
        content="Purpose content.",
    )
    purpose_id = purpose.add()
    strategy_id = _insert_strategy(
        team_id=team_id,
        purpose_id=purpose_id,
        name="Strategy JSON",
        description="Strategy description.",
        status="in_progress",
    )
    initiative_id = _insert_initiative(
        team_id=team_id,
        strategy_id=strategy_id,
        name="Initiative JSON",
        description="Initiative description.",
        status="pending",
    )
    task_id = _insert_task(
        team_id=team_id,
        initiative_id=initiative_id,
        name="Task JSON",
        content="Task content.",
        status="pending",
        assignee="root_operations_json",
    )

    payload = json.loads(
        render_status_json(collect_status(team_id=team_id, active_only=False))
    )

    assert payload["teams"][0]["id"] == team_id
    assert payload["teams"][0]["purposes"][0]["id"] == purpose_id
    assert payload["teams"][0]["purposes"][0]["strategies"][0]["id"] == strategy_id
    assert (
        payload["teams"][0]["purposes"][0]["strategies"][0]["initiatives"][0]["id"]
        == initiative_id
    )
    assert (
        payload["teams"][0]["purposes"][0]["strategies"][0]["initiatives"][0]["tasks"][
            0
        ]["id"]
        == task_id
    )
