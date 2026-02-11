"""Task orchestration helpers."""

import json
import logging

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.task import Task, get_task as _get_task
from src.cyberagent.memory.config import (
    build_memory_registry,
    load_memory_backend_config,
)
from src.cyberagent.memory.crud import (
    MemoryActorContext,
    MemoryCreateRequest,
    MemoryCrudService,
)
from src.cyberagent.memory.models import (
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.memory.observability import (
    LoggingMemoryAuditSink,
    build_memory_metrics,
)
from src.cyberagent.services import systems as systems_service
from src.enums import Status
from src.enums import SystemType

logger = logging.getLogger(__name__)

ALLOWED_TASK_TRANSITIONS: dict[Status, set[Status]] = {
    Status.PENDING: {Status.IN_PROGRESS, Status.REJECTED},
    Status.IN_PROGRESS: {Status.COMPLETED, Status.BLOCKED, Status.REJECTED},
    Status.BLOCKED: {Status.IN_PROGRESS, Status.REJECTED},
    Status.COMPLETED: {Status.APPROVED, Status.REJECTED},
    Status.APPROVED: set(),
    Status.REJECTED: set(),
}

REVIEW_ELIGIBLE_TASK_STATUSES: set[Status] = {Status.COMPLETED, Status.BLOCKED}


def start_task(task_id: int) -> Task:
    """
    Mark a task as in-progress.

    Args:
        task_id: Task identifier.

    Returns:
        The task record.

    Raises:
        ValueError: If the task does not exist.
    """
    task = _get_task(task_id)
    if task is None:
        raise ValueError(f"Task with id {task_id} not found")
    _transition_task(task, Status.IN_PROGRESS)
    _persist_task(task)
    return task


def complete_task(task: Task, result: str) -> None:
    """
    Persist task completion result.

    Args:
        task: Task record to update.
        result: Result text.
    """
    task.result = result
    _transition_task(task, Status.COMPLETED)
    _persist_task(task)
    if isinstance(task, Task):
        _store_task_result_in_team_memory(task)


def mark_task_blocked(task: Task, reasoning: str) -> None:
    """
    Mark a task as blocked with an explanation.

    Args:
        task: Task record to update.
        reasoning: Human-readable reason for the blocked status.
    """
    task.reasoning = reasoning
    _transition_task(task, Status.BLOCKED)
    _persist_task(task)


def get_task_by_id(task_id: int) -> Task:
    """
    Fetch a task or raise if missing.

    Args:
        task_id: Task identifier.

    Returns:
        The task record.

    Raises:
        ValueError: If the task does not exist.
    """
    task = _get_task(task_id)
    if task is None:
        raise ValueError(f"Task with id {task_id} not found")
    return task


def create_task(
    team_id: int,
    initiative_id: int,
    name: str,
    content: str,
) -> Task:
    """
    Create a task record and persist it.

    Args:
        team_id: Team identifier.
        initiative_id: Initiative identifier.
        name: Task name.
        content: Task content.
    """
    task = Task(
        team_id=team_id,
        initiative_id=initiative_id,
        name=name,
        content=content,
    )
    task.add()
    return task


def has_tasks_for_initiative(initiative_id: int) -> bool:
    """
    Return True when at least one task exists for an initiative.

    Args:
        initiative_id: Initiative identifier.
    """
    session = next(get_db())
    try:
        return (
            session.query(Task).filter(Task.initiative_id == initiative_id).first()
            is not None
        )
    finally:
        session.close()


def assign_task(task: Task, assignee_agent_id_str: str) -> None:
    """
    Assign a task to an agent.

    Args:
        task: Task to update.
        assignee_agent_id_str: Agent id string.
    """
    task.assignee = assignee_agent_id_str
    _persist_task(task)


def approve_task(task: Task) -> None:
    """
    Mark a task as approved.

    Args:
        task: Task to update.
    """
    _transition_task(task, Status.APPROVED)
    _persist_task(task)


def is_review_eligible_for_task(task: Task) -> bool:
    """
    Return whether a task is eligible for policy review.

    Completed tasks and blocked tasks may enter policy review.
    """
    current = _resolve_task_status(getattr(task, "status", None))
    return current in REVIEW_ELIGIBLE_TASK_STATUSES


def finalize_task_review(task: Task, cases: list[dict[str, object]]) -> None:
    """
    Persist review cases and finalize task status from review outcomes.

    A completed task is approved only when all review cases are ``Satisfied``.
    If at least one case is ``Vague``, status remains unchanged so System5 can
    clarify policy wording and retrigger review. If there are no vague cases
    and at least one ``Violated`` case, a completed task is rejected.
    """
    set_task_case_judgement(task, cases)
    judgements = [str(case.get("judgement", "")) for case in cases]
    has_vague = any(judgement == "Vague" for judgement in judgements)
    has_violated = any(judgement == "Violated" for judgement in judgements)
    all_satisfied = len(cases) > 0 and all(
        judgement == "Satisfied" for judgement in judgements
    )
    current_status = _resolve_task_status(getattr(task, "status", None))
    if not all_satisfied:
        if has_vague:
            return
        if has_violated and current_status == Status.COMPLETED:
            _transition_task(task, Status.REJECTED)
            _persist_task(task)
        return
    if current_status != Status.COMPLETED:
        return
    _transition_task(task, Status.APPROVED)
    _persist_task(task)


def set_task_case_judgement(task: Task, cases: list[dict[str, object]]) -> None:
    """
    Persist policy review case judgements on a task.

    Args:
        task: Task to update.
        cases: Structured policy case judgements.
    """
    judgement_priority = {"Violated": 3, "Vague": 2, "Satisfied": 1}
    selected_case: dict[str, object] | None = None
    selected_score = 0
    for case in cases:
        judgement = str(case.get("judgement", ""))
        score = judgement_priority.get(judgement, 0)
        if score > selected_score:
            selected_case = case
            selected_score = score

    task.case_judgement = json.dumps(cases, ensure_ascii=True)
    if selected_case is not None:
        task.policy_judgement = str(selected_case.get("judgement", ""))
        task.policy_judgement_reasoning = str(selected_case.get("reasoning", ""))
    else:
        task.policy_judgement = None
        task.policy_judgement_reasoning = None
    _persist_task(task)


def set_task_execution_log(task: Task, execution_log: str) -> None:
    """
    Persist serialized task execution messages (tool events + intermediate output).

    Args:
        task: Task to update.
        execution_log: JSON serialized execution trace.
    """
    task.execution_log = execution_log
    _persist_task(task)


def _persist_task(task: Task) -> None:
    """
    Persist a task mutation using service-level transaction control.

    Transitional compatibility:
    - SQLAlchemy Task instances are persisted via session merge/commit here.
    - Test doubles or legacy stand-ins fall back to ``update()`` when available.
    """
    if isinstance(task, Task):
        session = next(get_db())
        try:
            session.merge(task)
            session.commit()
        finally:
            session.close()
        return
    if hasattr(task, "update"):
        task.update()


def _transition_task(task: Task, next_status: Status) -> None:
    """Validate and apply a task status transition."""
    current = _resolve_task_status(getattr(task, "status", None))
    if current is None:
        task.set_status(next_status)
        return
    if current == next_status:
        return
    allowed = ALLOWED_TASK_TRANSITIONS.get(current, set())
    if next_status not in allowed:
        raise ValueError(
            f"Invalid task status transition: {current.value} -> {next_status.value}"
        )
    task.set_status(next_status)


def _resolve_task_status(raw_status: object) -> Status | None:
    if raw_status is None:
        return None
    if isinstance(raw_status, Status):
        return raw_status
    raw_text = str(raw_status).strip()
    if "." in raw_text:
        raw_text = raw_text.split(".")[-1]
    normalized = raw_text.lower()
    for status in Status:
        if status.value.lower() == normalized:
            return status
    try:
        return Status(str(raw_status))
    except ValueError:
        return None


def _store_task_result_in_team_memory(task: Task) -> None:
    """Persist completed task output into team-scope memory for reuse."""
    result_text = (task.result or "").strip()
    if not result_text:
        return
    try:
        control_system = systems_service.get_system_by_type(
            task.team_id, SystemType.CONTROL
        )
        actor = MemoryActorContext(
            agent_id=control_system.agent_id_str,
            system_id=control_system.id,
            team_id=control_system.team_id,
            system_type=control_system.type,
        )
        service = MemoryCrudService(
            registry=build_memory_registry(load_memory_backend_config()),
            metrics=build_memory_metrics(),
            audit_sink=LoggingMemoryAuditSink(),
        )
        status_text = (
            task.status.value if isinstance(task.status, Status) else str(task.status)
        )
        content_lines = [
            f"Task #{task.id}: {task.name}",
            f"Status: {status_text}",
            f"Assignee: {task.assignee or '-'}",
            f"Task content: {task.content}",
            f"Task result: {result_text}",
        ]
        if task.reasoning:
            content_lines.append(f"Task reasoning: {task.reasoning}")
        service.create_entries(
            actor=actor,
            requests=[
                MemoryCreateRequest(
                    content="\n".join(content_lines),
                    namespace=f"team:{task.team_id}",
                    scope=MemoryScope.TEAM,
                    tags=[
                        "task_result",
                        f"task:{task.id}",
                        (
                            f"initiative:{task.initiative_id}"
                            if task.initiative_id
                            else "initiative:none"
                        ),
                    ],
                    priority=MemoryPriority.HIGH,
                    source=MemorySource.TOOL,
                    confidence=0.95,
                    expires_at=None,
                    layer=MemoryLayer.LONG_TERM,
                )
            ],
        )
    except Exception as exc:
        logger.warning(
            "Unable to persist task result %s to team memory: %s",
            getattr(task, "id", "?"),
            exc,
        )
