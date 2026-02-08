import uuid

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import init_db
from src.cyberagent.db.models.policy import Policy
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.enums import SystemType


def _create_team_and_system(agent_id: str) -> tuple[int, int]:
    db = next(get_db())
    try:
        team = Team(name=f"policy_team_{uuid.uuid4().hex}")
        db.add(team)
        db.flush()
        system = System(
            team_id=team.id,
            name=agent_id,
            type=SystemType.OPERATION,
            agent_id_str=agent_id,
        )
        db.add(system)
        db.commit()
        return team.id, system.id
    finally:
        db.close()


def test_get_system_policy_prompts_delegates(monkeypatch):
    from src.cyberagent.services import policies as policy_service

    monkeypatch.setattr(
        policy_service, "_get_system_policy_prompts", lambda agent_id: ["p1"]
    )

    assert policy_service.get_system_policy_prompts("agent") == ["p1"]


def test_get_policy_by_id_delegates(monkeypatch):
    from src.cyberagent.services import policies as policy_service

    monkeypatch.setattr(policy_service, "_get_policy", lambda policy_id: "policy")

    assert policy_service.get_policy_by_id(5) == "policy"


def test_get_team_policy_prompts_delegates(monkeypatch):
    from src.cyberagent.services import policies as policy_service

    monkeypatch.setattr(
        policy_service, "_get_team_policy_prompts", lambda agent_id: ["t1"]
    )

    assert policy_service.get_team_policy_prompts("agent") == ["t1"]


def test_ensure_baseline_policies_for_assignee_requires_registered_system(monkeypatch):
    from src.cyberagent.services import policies as policy_service

    monkeypatch.setattr(policy_service, "get_system_from_agent_id", lambda _id: None)

    try:
        policy_service.ensure_baseline_policies_for_assignee("System1/root")
        assert False, "Expected ValueError for unknown system"
    except ValueError as exc:
        assert "not registered" in str(exc)


def test_ensure_baseline_policies_for_assignee_creates_policies():
    from src.cyberagent.services import policies as policy_service

    init_db()
    team_id, system_id = _create_team_and_system("System1/policy-test")

    created = policy_service.ensure_baseline_policies_for_assignee(
        "System1/policy-test"
    )

    db = next(get_db())
    try:
        records = (
            db.query(Policy)
            .filter(Policy.team_id == team_id, Policy.system_id == system_id)
            .all()
        )
    finally:
        db.close()

    assert created == 3
    assert len(records) == 3


def test_get_system_policy_prompts_returns_flat_strings():
    from src.cyberagent.services import policies as policy_service

    init_db()
    team_id, system_id = _create_team_and_system("System1/policy-prompt-shape")

    db = next(get_db())
    try:
        db.add(
            Policy(
                team_id=team_id,
                system_id=system_id,
                name="shape_test",
                content="Policy content",
            )
        )
        db.commit()
    finally:
        db.close()

    prompts = policy_service.get_system_policy_prompts("System1/policy-prompt-shape")

    assert prompts
    assert all(isinstance(item, str) for item in prompts)
