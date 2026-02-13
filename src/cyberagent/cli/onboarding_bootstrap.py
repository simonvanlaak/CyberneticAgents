from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from src.cyberagent.cli.onboarding_defaults import get_default_team_name
from src.cyberagent.cli.onboarding_output import print_db_write_error
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.procedure import Procedure
from src.cyberagent.db.models.strategy import Strategy
from src.cyberagent.db.models.system import (
    System,
    ensure_default_systems_for_team,
    get_system_by_type,
)
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import procedures as procedures_service
from src.cyberagent.services import purposes as purposes_service
from src.cyberagent.services import strategies as strategies_service
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import teams as teams_service
from src.enums import SystemType
from src.rbac.enforcer import give_user_tool_permission

NETWORK_SKILL_NAMES = {"web-fetch", "web-search", "git-readonly-sync"}


def seed_default_procedures(team_id: int, procedures: list[dict[str, object]]) -> None:
    ensure_default_systems_for_team(team_id)
    system4 = get_system_by_type(team_id, SystemType.INTELLIGENCE)
    system5 = get_system_by_type(team_id, SystemType.POLICY)

    session = next(get_db())
    try:
        existing_names = {
            procedure.name
            for procedure in session.query(Procedure)
            .filter(Procedure.team_id == team_id)
            .all()
        }
    finally:
        session.close()

    for template in procedures:
        name = template.get("name")
        if not isinstance(name, str):
            continue
        if name in existing_names:
            continue
        tasks = template.get("tasks")
        if not isinstance(tasks, list):
            tasks = []
        procedure = procedures_service.create_procedure_draft(
            team_id=team_id,
            name=name,
            description=str(template.get("description", "")),
            risk_level=str(template.get("risk_level", "")),
            impact=str(template.get("impact", "")),
            rollback_plan=str(template.get("rollback_plan", "")),
            created_by_system_id=system4.id,
            tasks=tasks,
        )
        procedures_service.approve_procedure(
            procedure_id=procedure.id, approved_by_system_id=system5.id
        )


def seed_default_team_envelope(team_id: int, team_defaults: dict[str, object]) -> None:
    allowed = team_defaults.get("allowed_skills")
    if not isinstance(allowed, list):
        return
    skill_names = [skill for skill in allowed if isinstance(skill, str)]
    teams_service.set_allowed_skills(team_id, skill_names, actor_id="onboarding")


def seed_root_team_envelope_from_defaults(team_defaults: dict[str, object]) -> None:
    team_name = get_default_team_name(team_defaults)
    allowed = team_defaults.get("allowed_skills")
    if not isinstance(allowed, list):
        return
    skill_names = [skill for skill in allowed if isinstance(skill, str)]
    if not skill_names:
        return
    session = next(get_db())
    try:
        root_team = session.query(Team).filter(Team.name == team_name).first()
    finally:
        session.close()
    if root_team is None:
        return
    teams_service.set_allowed_skills(root_team.id, skill_names, actor_id="onboarding")


def ensure_team_systems(team_id: int, team_defaults: dict[str, object]) -> None:
    systems_block = team_defaults.get("systems")
    if not isinstance(systems_block, list):
        ensure_default_systems_for_team(team_id)
        return
    session = next(get_db())
    try:
        existing = {
            system.type: system
            for system in session.query(System).filter(System.team_id == team_id).all()
        }
        for entry in systems_block:
            if not isinstance(entry, dict):
                continue
            type_value = entry.get("type")
            name = entry.get("name")
            agent_id = entry.get("agent_id")
            if not isinstance(type_value, str):
                continue
            try:
                system_type = SystemType[type_value]
            except KeyError:
                continue
            if system_type in existing:
                continue
            if not isinstance(name, str) or not isinstance(agent_id, str):
                continue
            system = System(
                team_id=team_id,
                name=name,
                type=system_type,
                agent_id_str=agent_id,
            )
            session.add(system)
            existing[system_type] = system
        session.commit()
    finally:
        session.close()

    for entry in systems_block:
        if not isinstance(entry, dict):
            continue
        type_value = entry.get("type")
        if not isinstance(type_value, str):
            continue
        try:
            system_type = SystemType[type_value]
        except KeyError:
            continue
        systems = (
            systems_service.get_systems_by_type(team_id, system_type)
            if system_type == SystemType.OPERATION
            else [get_system_by_type(team_id, system_type)]
        )
        skill_grants = entry.get("skill_grants")
        if not isinstance(skill_grants, list):
            continue
        for system in systems:
            for skill_name in skill_grants:
                if isinstance(skill_name, str):
                    systems_service.add_skill_grant(
                        system.id, skill_name, actor_id="onboarding"
                    )
                    if skill_name in NETWORK_SKILL_NAMES:
                        give_user_tool_permission(system.agent_id_str, skill_name, "*")


def trigger_onboarding_initiative(
    team_id: int,
    onboarding_procedure_name: str,
    onboarding_strategy_name: str,
    onboarding_purpose_name: str,
) -> bool:
    """Deprecated for Phase 1 onboarding."""

    ensure_default_systems_for_team(team_id)
    session = next(get_db())
    try:
        procedure = (
            session.query(Procedure)
            .filter(
                Procedure.team_id == team_id,
                Procedure.name == onboarding_procedure_name,
            )
            .first()
        )
    finally:
        session.close()
    if procedure is None:
        return True

    purpose = purposes_service.get_or_create_default_purpose(team_id)
    purpose.name = onboarding_purpose_name
    purpose.content = procedure.description
    try:
        purpose.update()
    except SQLAlchemyError as exc:
        print_db_write_error("purpose", exc)
        return False

    session = next(get_db())
    try:
        strategy = (
            session.query(Strategy)
            .filter(
                Strategy.team_id == team_id,
                Strategy.name == onboarding_strategy_name,
            )
            .first()
        )
    finally:
        session.close()
    if strategy is None:
        try:
            strategies_service.create_strategy(
                team_id=team_id,
                purpose_id=purpose.id,
                name=onboarding_strategy_name,
                description=procedure.description,
            )
        except SQLAlchemyError as exc:
            print_db_write_error("strategy", exc)
            return False

    return True
