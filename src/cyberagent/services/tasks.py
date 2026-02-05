"""Task orchestration helpers."""

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.task import Task, get_task as _get_task
from src.enums import Status


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
    task.set_status(Status.IN_PROGRESS)
    task.update()
    return task


def complete_task(task: Task, result: str) -> None:
    """
    Persist task completion result.

    Args:
        task: Task record to update.
        result: Result text.
    """
    task.result = result
    task.set_status(Status.COMPLETED)
    task.update()


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
    task.update()


def approve_task(task: Task) -> None:
    """
    Mark a task as approved.

    Args:
        task: Task to update.
    """
    task.set_status(Status.APPROVED)
    task.update()
