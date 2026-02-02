"""Procedure orchestration helpers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import and_

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.initiative import Initiative
from src.cyberagent.db.models.procedure import (
    Procedure,
    get_procedure as _get_procedure,
)
from src.cyberagent.db.models.procedure_run import (
    ProcedureRun,
    get_procedure_run as _get_procedure_run,
)
from src.cyberagent.db.models.procedure_task import ProcedureTask
from src.cyberagent.db.models.task import Task
from src.enums import ProcedureStatus

ProcedureTaskInput = dict[str, Any]


def get_procedure(procedure_id: int) -> Procedure:
    procedure = _get_procedure(procedure_id)
    if procedure is None:
        raise ValueError(f"Procedure with id {procedure_id} not found")
    return procedure


def list_procedure_tasks(procedure_id: int) -> list[ProcedureTask]:
    session = next(get_db())
    try:
        return (
            session.query(ProcedureTask)
            .filter(ProcedureTask.procedure_id == procedure_id)
            .order_by(ProcedureTask.position.asc())
            .all()
        )
    finally:
        session.close()


def create_procedure_draft(
    team_id: int,
    name: str,
    description: str,
    risk_level: str,
    impact: str,
    rollback_plan: str,
    created_by_system_id: int,
    tasks: Iterable[ProcedureTaskInput],
) -> Procedure:
    session = next(get_db())
    try:
        procedure = Procedure(
            team_id=team_id,
            name=name,
            description=description,
            status=ProcedureStatus.DRAFT,
            version=1,
            risk_level=risk_level,
            impact=impact,
            rollback_plan=rollback_plan,
            created_by_system_id=created_by_system_id,
            updated_at=datetime.utcnow(),
        )
        session.add(procedure)
        session.flush()
        procedure.series_id = procedure.id
        session.flush()
        _create_task_templates(session, procedure.id, tasks)
        session.commit()
        session.refresh(procedure)
        return procedure
    finally:
        session.close()


def create_procedure_revision(
    procedure_id: int,
    name: str,
    description: str,
    risk_level: str,
    impact: str,
    rollback_plan: str,
    created_by_system_id: int,
    tasks: Iterable[ProcedureTaskInput] | None = None,
) -> Procedure:
    base = get_procedure(procedure_id)
    session = next(get_db())
    try:
        revision = Procedure(
            team_id=base.team_id,
            name=name,
            description=description,
            status=ProcedureStatus.DRAFT,
            version=base.version + 1,
            series_id=base.series_id or base.id,
            risk_level=risk_level,
            impact=impact,
            rollback_plan=rollback_plan,
            created_by_system_id=created_by_system_id,
            updated_at=datetime.utcnow(),
        )
        session.add(revision)
        session.flush()
        template_tasks = tasks
        if template_tasks is None:
            template_tasks = _clone_task_templates(base.id)
        _create_task_templates(session, revision.id, template_tasks)
        session.commit()
        session.refresh(revision)
        return revision
    finally:
        session.close()


def approve_procedure(procedure_id: int, approved_by_system_id: int) -> Procedure:
    session = next(get_db())
    try:
        procedure = (
            session.query(Procedure).filter(Procedure.id == procedure_id).first()
        )
        if procedure is None:
            raise ValueError(f"Procedure with id {procedure_id} not found")
        if procedure.status == ProcedureStatus.RETIRED:
            raise ValueError("Cannot approve a retired procedure")
        procedure.status = ProcedureStatus.APPROVED
        procedure.approved_by_system_id = approved_by_system_id
        procedure.updated_at = datetime.utcnow()
        series_id = procedure.series_id or procedure.id
        session.query(Procedure).filter(
            and_(
                Procedure.series_id == series_id,
                Procedure.id != procedure.id,
                Procedure.status == ProcedureStatus.APPROVED,
            )
        ).update({"status": ProcedureStatus.RETIRED}, synchronize_session=False)
        session.commit()
        session.refresh(procedure)
        return procedure
    finally:
        session.close()


def execute_procedure(
    procedure_id: int,
    team_id: int,
    strategy_id: int,
    executed_by_system_id: int,
) -> ProcedureRun:
    procedure = get_procedure(procedure_id)
    if procedure.status != ProcedureStatus.APPROVED:
        raise ValueError("Procedure must be approved before execution")

    session = next(get_db())
    try:
        initiative = Initiative(
            team_id=team_id,
            strategy_id=strategy_id,
            name=procedure.name,
            description=procedure.description,
            procedure_id=procedure.id,
            procedure_version=procedure.version,
        )
        session.add(initiative)
        session.flush()
        _materialize_tasks(session, team_id, initiative.id, procedure.id)
        run = ProcedureRun(
            procedure_id=procedure.id,
            procedure_version=procedure.version,
            initiative_id=initiative.id,
            executed_by_system_id=executed_by_system_id,
            status="started",
            started_at=datetime.utcnow(),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
    finally:
        session.close()


def get_procedure_run(run_id: int) -> ProcedureRun:
    run = _get_procedure_run(run_id)
    if run is None:
        raise ValueError(f"Procedure run with id {run_id} not found")
    return run


def get_initiative(initiative_id: int) -> Initiative:
    session = next(get_db())
    try:
        initiative = (
            session.query(Initiative).filter(Initiative.id == initiative_id).first()
        )
        if initiative is None:
            raise ValueError(f"Initiative with id {initiative_id} not found")
        return initiative
    finally:
        session.close()


def search_procedures(team_id: int, include_retired: bool) -> list[Procedure]:
    session = next(get_db())
    try:
        query = session.query(Procedure).filter(Procedure.team_id == team_id)
        if not include_retired:
            query = query.filter(Procedure.status != ProcedureStatus.RETIRED)
        return query.order_by(Procedure.updated_at.desc()).all()
    finally:
        session.close()


def _create_task_templates(
    session, procedure_id: int, tasks: Iterable[ProcedureTaskInput]
) -> None:
    for task in tasks:
        required_skills = task.get("required_skills")
        if isinstance(required_skills, (list, tuple)):
            required_skills_value = json.dumps(list(required_skills))
        else:
            required_skills_value = required_skills
        session.add(
            ProcedureTask(
                procedure_id=procedure_id,
                name=str(task.get("name", "")),
                description=str(task.get("description", "")),
                position=int(task.get("position", 0)),
                depends_on_task_id=task.get("depends_on_task_id"),
                default_assignee_system_type=task.get("default_assignee_system_type"),
                required_skills=required_skills_value,
            )
        )


def _clone_task_templates(procedure_id: int) -> list[ProcedureTaskInput]:
    tasks = list_procedure_tasks(procedure_id)
    return [
        {
            "name": task.name,
            "description": task.description,
            "position": task.position,
            "depends_on_task_id": task.depends_on_task_id,
            "default_assignee_system_type": task.default_assignee_system_type,
            "required_skills": task.required_skills,
        }
        for task in tasks
    ]


def _materialize_tasks(
    session, team_id: int, initiative_id: int, procedure_id: int
) -> None:
    templates = (
        session.query(ProcedureTask)
        .filter(ProcedureTask.procedure_id == procedure_id)
        .order_by(ProcedureTask.position.asc())
        .all()
    )
    for template in templates:
        session.add(
            Task(
                team_id=team_id,
                initiative_id=initiative_id,
                name=template.name,
                content=template.description,
            )
        )


__all__ = [
    "ProcedureStatus",
    "create_procedure_draft",
    "create_procedure_revision",
    "approve_procedure",
    "execute_procedure",
    "get_procedure",
    "get_procedure_run",
    "list_procedure_tasks",
    "search_procedures",
    "get_initiative",
]
