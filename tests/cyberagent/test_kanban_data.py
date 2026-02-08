from __future__ import annotations

from datetime import datetime

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.initiative import Initiative
from src.cyberagent.db.models.purpose import Purpose
from src.cyberagent.db.models.strategy import Strategy
from src.cyberagent.db.models.task import Task
from src.cyberagent.db.models.team import Team
from src.cyberagent.ui.kanban_data import (
    KANBAN_STATUSES,
    group_tasks_by_status,
    load_task_cards,
)
from src.enums import Status


def _seed_team_hierarchy(name_suffix: str) -> tuple[int, int, int]:
    session = next(get_db())
    try:
        team = Team(name=f"kanban-team-{name_suffix}", last_active_at=datetime.utcnow())
        session.add(team)
        session.flush()

        purpose = Purpose(
            team_id=team.id,
            name=f"purpose-{name_suffix}",
            content="purpose content",
        )
        session.add(purpose)
        session.flush()

        strategy = Strategy(
            team_id=team.id,
            purpose_id=purpose.id,
            name=f"strategy-{name_suffix}",
            description="strategy description",
        )
        session.add(strategy)
        session.flush()

        initiative = Initiative(
            team_id=team.id,
            strategy_id=strategy.id,
            name=f"initiative-{name_suffix}",
            description="initiative description",
        )
        session.add(initiative)
        session.flush()

        session.commit()
        return team.id, strategy.id, initiative.id
    finally:
        session.close()


def _seed_task(
    *,
    team_id: int,
    initiative_id: int,
    name: str,
    status: Status,
    assignee: str | None,
) -> None:
    session = next(get_db())
    try:
        task = Task(
            team_id=team_id,
            initiative_id=initiative_id,
            name=name,
            content=f"{name} content",
            assignee=assignee,
            status=status,
        )
        session.add(task)
        session.commit()
    finally:
        session.close()


def test_load_task_cards_filters_by_team_and_assignee() -> None:
    team_a, _, initiative_a = _seed_team_hierarchy("a")
    team_b, _, initiative_b = _seed_team_hierarchy("b")

    _seed_task(
        team_id=team_a,
        initiative_id=initiative_a,
        name="A pending",
        status=Status.PENDING,
        assignee="System1/root",
    )
    _seed_task(
        team_id=team_a,
        initiative_id=initiative_a,
        name="A in progress",
        status=Status.IN_PROGRESS,
        assignee="System1/ops",
    )
    _seed_task(
        team_id=team_b,
        initiative_id=initiative_b,
        name="B pending",
        status=Status.PENDING,
        assignee="System1/root",
    )

    team_tasks = load_task_cards(team_id=team_a)
    assert len(team_tasks) == 2
    assert all(task.team_id == team_a for task in team_tasks)

    assignee_tasks = load_task_cards(team_id=team_a, assignee="System1/root")
    assert len(assignee_tasks) == 1
    assert assignee_tasks[0].name == "A pending"


def test_group_tasks_by_status_returns_all_kanban_columns() -> None:
    team_id, _, initiative_id = _seed_team_hierarchy("group")
    _seed_task(
        team_id=team_id,
        initiative_id=initiative_id,
        name="Grouped pending",
        status=Status.PENDING,
        assignee=None,
    )
    _seed_task(
        team_id=team_id,
        initiative_id=initiative_id,
        name="Grouped completed",
        status=Status.COMPLETED,
        assignee="System1/root",
    )

    tasks = load_task_cards(team_id=team_id)
    grouped = group_tasks_by_status(tasks)

    assert list(grouped.keys()) == KANBAN_STATUSES
    assert [task.name for task in grouped[Status.PENDING.value]] == ["Grouped pending"]
    assert [task.name for task in grouped[Status.COMPLETED.value]] == [
        "Grouped completed"
    ]
