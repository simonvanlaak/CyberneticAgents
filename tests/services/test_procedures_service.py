from __future__ import annotations

from datetime import datetime
from typing import Iterator

import pytest
from sqlalchemy.orm import Session

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.purpose import Purpose
from src.cyberagent.db.models.strategy import Strategy
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import procedures as procedures_service
from src.enums import Status


def _db_session() -> Session:
    return next(get_db())


def _create_team(session: Session, name: str = "team") -> Team:
    team = Team(name=name, last_active_at=datetime.utcnow())
    session.add(team)
    session.commit()
    session.refresh(team)
    return team


def _create_purpose(session: Session, team_id: int) -> Purpose:
    purpose = Purpose(team_id=team_id, name="Purpose", content="Desc")
    session.add(purpose)
    session.commit()
    session.refresh(purpose)
    return purpose


def _create_strategy(session: Session, team_id: int, purpose_id: int) -> Strategy:
    strategy = Strategy(
        team_id=team_id,
        purpose_id=purpose_id,
        name="Strategy",
        description="Desc",
        status=Status.IN_PROGRESS,
        result="",
    )
    session.add(strategy)
    session.commit()
    session.refresh(strategy)
    return strategy


def test_create_procedure_draft_creates_tasks() -> None:
    session = _db_session()
    try:
        team = _create_team(session, "proc-team")
        procedure = procedures_service.create_procedure_draft(
            team_id=team.id,
            name="Daily Review",
            description="Review daily ops",
            risk_level="low",
            impact="minor",
            rollback_plan="none",
            created_by_system_id=1,
            tasks=[
                {
                    "name": "Check logs",
                    "description": "Review logs",
                    "position": 1,
                },
                {
                    "name": "Summarize",
                    "description": "Summarize findings",
                    "position": 2,
                },
            ],
        )
        assert procedure.status == procedures_service.ProcedureStatus.DRAFT
        task_templates = procedures_service.list_procedure_tasks(procedure.id)
        assert len(task_templates) == 2
        assert task_templates[0].name == "Check logs"
    finally:
        session.close()


def test_approve_procedure_retires_prior_version() -> None:
    session = _db_session()
    try:
        team = _create_team(session, "proc-team-2")
        first = procedures_service.create_procedure_draft(
            team_id=team.id,
            name="Weekly Review",
            description="Review weekly ops",
            risk_level="low",
            impact="minor",
            rollback_plan="none",
            created_by_system_id=1,
            tasks=[{"name": "Task", "description": "Do", "position": 1}],
        )
        procedures_service.approve_procedure(
            procedure_id=first.id, approved_by_system_id=5
        )
        second = procedures_service.create_procedure_revision(
            procedure_id=first.id,
            name="Weekly Review",
            description="Review weekly ops v2",
            risk_level="medium",
            impact="moderate",
            rollback_plan="revert",
            created_by_system_id=1,
        )
        procedures_service.approve_procedure(
            procedure_id=second.id, approved_by_system_id=5
        )
        first_refreshed = procedures_service.get_procedure(first.id)
        second_refreshed = procedures_service.get_procedure(second.id)
        assert first_refreshed.status == procedures_service.ProcedureStatus.RETIRED
        assert second_refreshed.status == procedures_service.ProcedureStatus.APPROVED
    finally:
        session.close()


def test_execute_procedure_materializes_initiative_and_tasks() -> None:
    session = _db_session()
    try:
        team = _create_team(session, "proc-team-3")
        purpose = _create_purpose(session, team.id)
        strategy = _create_strategy(session, team.id, purpose.id)
        procedure = procedures_service.create_procedure_draft(
            team_id=team.id,
            name="Daily Sync",
            description="Sync tasks",
            risk_level="low",
            impact="minor",
            rollback_plan="none",
            created_by_system_id=1,
            tasks=[
                {"name": "Step 1", "description": "Do 1", "position": 1},
                {"name": "Step 2", "description": "Do 2", "position": 2},
            ],
        )
        procedures_service.approve_procedure(
            procedure_id=procedure.id, approved_by_system_id=5
        )

        run = procedures_service.execute_procedure(
            procedure_id=procedure.id,
            team_id=team.id,
            strategy_id=strategy.id,
            executed_by_system_id=3,
        )
        initiative = procedures_service.get_initiative(run.initiative_id)
        tasks = initiative.get_tasks()
        assert initiative.procedure_id == procedure.id
        assert initiative.procedure_version == procedure.version
        assert len(tasks) == 2
    finally:
        session.close()
