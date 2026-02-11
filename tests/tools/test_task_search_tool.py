from __future__ import annotations

import pytest
from autogen_core import AgentId, CancellationToken

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.task import Task
from src.cyberagent.db.models.team import Team
from src.cyberagent.db.models.system import get_system_from_agent_id
from src.cyberagent.tools.task_search import TaskSearchArgs, TaskSearchTool
from src.enums import Status


def _create_team(name: str) -> Team:
    session = next(get_db())
    try:
        team = Team(name=name)
        session.add(team)
        session.commit()
        session.refresh(team)
        return team
    finally:
        session.close()


def _create_task(
    *,
    team_id: int,
    name: str,
    content: str,
    result: str | None,
    status: Status,
    assignee: str | None = "System1/root",
) -> int:
    session = next(get_db())
    try:
        task = Task(
            team_id=team_id,
            initiative_id=1,
            name=name,
            content=content,
            assignee=assignee,
            result=result,
            status=status,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return task.id
    finally:
        session.close()


@pytest.mark.asyncio
async def test_task_search_tool_returns_team_results_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = get_system_from_agent_id("System1/root")
    assert system is not None
    other_team = _create_team("other")

    own_task_id = _create_task(
        team_id=system.team_id,
        name="Collect identity",
        content="Collect user identity links",
        result="GitHub: https://github.com/example/repo",
        status=Status.APPROVED,
    )
    _create_task(
        team_id=other_team.id,
        name="Collect identity",
        content="Other team task",
        result="Should not be visible",
        status=Status.APPROVED,
    )

    tool = TaskSearchTool(AgentId.from_str("System1/root"))
    monkeypatch.setattr(
        "src.cyberagent.tools.task_search.systems_service.can_execute_skill",
        lambda _system_id, _skill_name: (True, None),
    )

    response = await tool.run(
        TaskSearchArgs(query="github", limit=10), CancellationToken()
    )

    assert response.errors == []
    assert len(response.items) == 1
    assert response.items[0].task_id == own_task_id
    assert "github.com/example/repo" in (response.items[0].result or "")


@pytest.mark.asyncio
async def test_task_search_tool_requires_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = TaskSearchTool(AgentId.from_str("System1/root"))
    monkeypatch.setattr(
        "src.cyberagent.tools.task_search.systems_service.can_execute_skill",
        lambda _system_id, _skill_name: (False, "system_grant"),
    )

    response = await tool.run(TaskSearchArgs(query="identity"), CancellationToken())

    assert response.items == []
    assert len(response.errors) == 1
    assert response.errors[0].code == "FORBIDDEN"
