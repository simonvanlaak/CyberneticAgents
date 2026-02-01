"""Task orchestration helpers."""

from typing import Optional

from src.cyberagent.db.models.task import Task, get_task
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
    task = get_task(task_id)
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
