from __future__ import annotations

from datetime import datetime

from src.cyberagent.cli import cyberagent
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import init_db
from src.cyberagent.db.models.initiative import Initiative
from src.cyberagent.db.models.purpose import Purpose
from src.cyberagent.db.models.strategy import Strategy
from src.cyberagent.db.models.task import Task
from src.cyberagent.db.models.team import Team
from src.enums import Status


def _seed_task_with_hierarchy() -> int:
    session = next(get_db())
    try:
        team = Team(name="task-cli-team", last_active_at=datetime.utcnow())
        session.add(team)
        session.flush()

        purpose = Purpose(
            team_id=team.id,
            name="task-cli-purpose",
            content="purpose content",
        )
        session.add(purpose)
        session.flush()

        strategy = Strategy(
            team_id=team.id,
            purpose_id=purpose.id,
            name="task-cli-strategy",
            description="strategy description",
        )
        session.add(strategy)
        session.flush()

        initiative = Initiative(
            team_id=team.id,
            strategy_id=strategy.id,
            name="task-cli-initiative",
            description="initiative description",
        )
        session.add(initiative)
        session.flush()

        task = Task(
            team_id=team.id,
            initiative_id=initiative.id,
            name="Task CLI detail",
            content="Task content body.",
            assignee="System1/root",
            status=Status.BLOCKED,
            result="Task result body.",
            reasoning="Task reasoning body.",
            execution_log='[{"type":"ToolCallExecutionEvent","name":"task_search"}]',
            case_judgement=(
                '[{"policy_id":2,"judgement":"Violated","reasoning":"Missing proof."}]'
            ),
            follow_up_task_id=77,
            replaces_task_id=44,
        )
        session.add(task)
        session.flush()
        session.commit()
        return int(task.id)
    finally:
        session.close()


def test_build_parser_accepts_task_command() -> None:
    parser = cyberagent.build_parser()

    args = parser.parse_args(["task", "42"])

    assert args.command == "task"
    assert args.task_id == 42


def test_task_command_prints_task_details(
    capsys,
) -> None:
    init_db()
    task_id = _seed_task_with_hierarchy()

    exit_code = cyberagent.main(["task", str(task_id)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"Task #{task_id}: Task CLI detail" in output
    assert "Task Content" in output
    assert "Task content body." in output
    assert "Status Reasoning" in output
    assert "Task reasoning body." in output
    assert "Task Result" in output
    assert "Task result body." in output
    assert "Execution Log" in output
    assert "task_search" in output
    assert "Lineage" in output
    assert "Follow-up Task ID: `77`" in output
    assert "Replaces Task ID: `44`" in output
    assert "Case Judgement" in output
    assert "Violated" in output


def test_task_command_returns_not_found_for_unknown_id(
    capsys,
) -> None:
    init_db()

    exit_code = cyberagent.main(["task", "999999"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Task #999999 not found." in output
