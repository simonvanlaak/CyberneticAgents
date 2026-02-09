"""Task orchestration helpers."""

import json

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.task import Task, get_task as _get_task
from src.enums import Status

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

    A task is approved only when all review cases are judged as ``Satisfied``.
    Otherwise task status remains unchanged for policy follow-up handling.
    """
    set_task_case_judgement(task, cases)
    all_satisfied = len(cases) > 0 and all(
        str(case.get("judgement", "")) == "Satisfied" for case in cases
    )
    if not all_satisfied:
        return
    if _resolve_task_status(getattr(task, "status", None)) != Status.COMPLETED:
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
    try:
        return Status(str(raw_status))
    except ValueError:
        return None
