from __future__ import annotations

from uuid import uuid4

import pytest
from autogen_core import AgentId, CancellationToken, MessageContext

from src.agents.messages import ConfirmationMessage, RecursionCreateMessage
from src.agents.system5 import System5
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import recursions as recursions_service
from src.enums import SystemType


def _create_team_id() -> int:
    session = next(get_db())
    try:
        team = Team(name=f"recursion_team_{uuid4().hex}")
        session.add(team)
        session.commit()
        return team.id
    finally:
        session.close()


def _create_system_id(team_id: int) -> int:
    session = next(get_db())
    try:
        system = System(
            team_id=team_id,
            name=f"system_{uuid4().hex}",
            type=SystemType.OPERATION,
            agent_id_str=f"team{team_id}_ops_{uuid4().hex}",
        )
        session.add(system)
        session.commit()
        return system.id
    finally:
        session.close()


def _make_context(sender: str = "System3/control1") -> MessageContext:
    return MessageContext(
        sender=AgentId.from_str(sender),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="msg_system5_recursion",
    )


@pytest.mark.asyncio
async def test_system5_creates_recursion_link(monkeypatch: pytest.MonkeyPatch) -> None:
    parent_team_id = _create_team_id()
    sub_team_id = _create_team_id()
    origin_system_id = _create_system_id(parent_team_id)

    monkeypatch.setenv("CYBERAGENT_ACTIVE_TEAM_ID", str(parent_team_id))
    system5 = System5("System5/policy1")

    message = RecursionCreateMessage(
        sub_team_id=sub_team_id,
        origin_system_id=origin_system_id,
        parent_team_id=parent_team_id,
        content="Create recursion link.",
        source="System3/control1",
    )

    response = await system5.handle_recursion_create_message(message, _make_context())

    assert isinstance(response, ConfirmationMessage)
    assert response.is_error is False
    link = recursions_service.get_recursion(sub_team_id)
    assert link is not None
    assert link.origin_system_id == origin_system_id
    assert link.parent_team_id == parent_team_id


@pytest.mark.asyncio
async def test_system5_rejects_cross_team_recursion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent_team_id = _create_team_id()
    sub_team_id = _create_team_id()
    origin_system_id = _create_system_id(parent_team_id)
    other_team_id = _create_team_id()

    monkeypatch.setenv("CYBERAGENT_ACTIVE_TEAM_ID", str(other_team_id))
    system5 = System5("System5/policy1")

    message = RecursionCreateMessage(
        sub_team_id=sub_team_id,
        origin_system_id=origin_system_id,
        parent_team_id=parent_team_id,
        content="Create recursion link.",
        source="System3/control1",
    )

    response = await system5.handle_recursion_create_message(message, _make_context())

    assert response.is_error is True
    assert recursions_service.get_recursion(sub_team_id) is None
