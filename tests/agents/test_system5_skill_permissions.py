from __future__ import annotations

from uuid import uuid4

import pytest
from autogen_core import AgentId, CancellationToken, MessageContext

from src.agents.messages import (
    ConfirmationMessage,
    SystemSkillGrantUpdateMessage,
    TeamEnvelopeUpdateMessage,
)
from src.agents.system5 import System5
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import teams as teams_service
from src.enums import SystemType
from src.rbac import skill_permissions_enforcer


@pytest.fixture(autouse=True)
def _reset_skill_permissions_enforcer(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    skill_permissions_enforcer._global_enforcer = None
    enforcer = skill_permissions_enforcer.get_enforcer()
    enforcer.clear_policy()
    yield
    skill_permissions_enforcer._global_enforcer = None


def _create_team_id() -> int:
    session = next(get_db())
    try:
        team = Team(name=f"system5_team_{uuid4().hex}")
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
        message_id="msg_system5_permissions",
    )


@pytest.mark.asyncio
async def test_system5_updates_team_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    team_id = _create_team_id()
    monkeypatch.setenv("CYBERAGENT_ACTIVE_TEAM_ID", str(team_id))
    system5 = System5("System5/policy1")

    message = TeamEnvelopeUpdateMessage(
        team_id=team_id,
        skill_name="skill.alpha",
        action="add",
        content="Add skill.alpha to team envelope.",
        source="System3/control1",
    )

    response = await system5.handle_team_envelope_update_message(
        message, _make_context()
    )

    assert isinstance(response, ConfirmationMessage)
    assert response.is_error is False
    assert teams_service.list_allowed_skills(team_id) == ["skill.alpha"]


@pytest.mark.asyncio
async def test_system5_rejects_cross_team_envelope_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team_id = _create_team_id()
    other_team_id = _create_team_id()
    monkeypatch.setenv("CYBERAGENT_ACTIVE_TEAM_ID", str(team_id))
    system5 = System5("System5/policy1")

    message = TeamEnvelopeUpdateMessage(
        team_id=other_team_id,
        skill_name="skill.beta",
        action="add",
        content="Add skill.beta to team envelope.",
        source="System3/control1",
    )

    response = await system5.handle_team_envelope_update_message(
        message, _make_context()
    )

    assert response.is_error is True
    assert teams_service.list_allowed_skills(other_team_id) == []


@pytest.mark.asyncio
async def test_system5_grants_and_revokes_system_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team_id = _create_team_id()
    system_id = _create_system_id(team_id)
    monkeypatch.setenv("CYBERAGENT_ACTIVE_TEAM_ID", str(team_id))
    system5 = System5("System5/policy1")

    teams_service.add_allowed_skill(
        team_id=team_id,
        skill_name="skill.gamma",
        actor_id="system5/root",
    )

    grant_message = SystemSkillGrantUpdateMessage(
        system_id=system_id,
        skill_name="skill.gamma",
        action="add",
        content="Grant skill.gamma to system.",
        source="System3/control1",
    )

    response = await system5.handle_system_skill_grant_update_message(
        grant_message, _make_context()
    )

    assert response.is_error is False
    assert systems_service.list_granted_skills(system_id) == ["skill.gamma"]

    revoke_message = SystemSkillGrantUpdateMessage(
        system_id=system_id,
        skill_name="skill.gamma",
        action="remove",
        content="Revoke skill.gamma from system.",
        source="System3/control1",
    )

    response = await system5.handle_system_skill_grant_update_message(
        revoke_message, _make_context()
    )

    assert response.is_error is False
    assert systems_service.list_granted_skills(system_id) == []


@pytest.mark.asyncio
async def test_system5_rejects_cross_team_system_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team_id = _create_team_id()
    other_team_id = _create_team_id()
    other_system_id = _create_system_id(other_team_id)
    monkeypatch.setenv("CYBERAGENT_ACTIVE_TEAM_ID", str(team_id))
    system5 = System5("System5/policy1")

    message = SystemSkillGrantUpdateMessage(
        system_id=other_system_id,
        skill_name="skill.delta",
        action="add",
        content="Grant skill.delta to system.",
        source="System3/control1",
    )

    response = await system5.handle_system_skill_grant_update_message(
        message, _make_context()
    )

    assert response.is_error is True
    assert systems_service.list_granted_skills(other_system_id) == []
