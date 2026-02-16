"""Operational Taiga worker loop for task claim/execute/transition flow."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import sleep as _sleep
from typing import Callable, Literal

from src.cyberagent.integrations.taiga.adapter import TaigaAdapter, TaigaTask

TaigaOutcome = Literal["success", "failed", "blocked"]


@dataclass(frozen=True)
class TaigaExecutionResult:
    """Execution result captured for task result comments + status mapping."""

    outcome: TaigaOutcome
    summary: str
    error: str | None = None


@dataclass(frozen=True)
class TaigaWorkerConfig:
    """Runtime configuration for the Taiga worker loop."""

    project_slug: str
    assignee: str
    source_status: str = "pending"
    in_progress_status: str = "in_progress"
    success_status: str = "completed"
    failure_status: str = "blocked"
    blocked_status: str = "blocked"
    once: bool = False
    poll_seconds: float = 30.0
    max_tasks: int = 1
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be greater than 0.")
        if self.max_tasks <= 0:
            raise ValueError("max_tasks must be greater than 0.")


class TaigaWorker:
    """Deterministic worker loop that claims and resolves Taiga tasks."""

    def __init__(
        self,
        *,
        adapter: TaigaAdapter,
        config: TaigaWorkerConfig,
        execute_task: Callable[[TaigaTask], TaigaExecutionResult] | None = None,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._adapter = adapter
        self._config = config
        self._execute_task = execute_task or self._default_execute_task
        self._now = now or _utc_now
        self._sleep = sleep or _sleep
        self._logger = logger or logging.getLogger(__name__)

    def run(self) -> int:
        """Run the worker in once or loop mode."""
        if self._config.once:
            processed = self.run_once()
            self._logger.info(
                "Taiga worker completed one-shot run (processed=%s).", processed
            )
            return 0

        try:
            while True:
                processed = self.run_once()
                self._logger.info(
                    "Taiga worker loop tick complete (processed=%s).", processed
                )
                self._sleep(self._config.poll_seconds)
        except KeyboardInterrupt:
            self._logger.info("Taiga worker interrupted; stopping cleanly.")
            return 0

    def run_once(self) -> int:
        """Process up to max_tasks tasks from the configured pending queue."""
        tasks = self._adapter.list_assigned_tasks(
            project_slug=self._config.project_slug,
            assignee=self._config.assignee,
            status_slug=self._config.source_status,
        )
        if not tasks:
            return 0

        validated_projects: set[int] = set()
        processed = 0
        required_statuses = self._required_status_names()
        for task in tasks:
            if processed >= self._config.max_tasks:
                break

            if task.project_id not in validated_projects:
                self._adapter.validate_required_statuses(
                    project_id=task.project_id,
                    required_status_names=required_statuses,
                )
                validated_projects.add(task.project_id)

            claimed = self._adapter.claim_task(
                task,
                target_status_name=self._config.in_progress_status,
            )
            if not claimed:
                self._logger.warning(
                    "Skipped task id=%s due to version conflict while claiming.",
                    task.task_id,
                )
                continue

            result = self._execute_with_failure_capture(task)
            self._transition_with_result(task, result)
            processed += 1

        return processed

    def _required_status_names(self) -> tuple[str, ...]:
        names = [
            self._config.source_status,
            self._config.in_progress_status,
            self._config.success_status,
            self._config.failure_status,
            self._config.blocked_status,
        ]
        seen: set[str] = set()
        ordered: list[str] = []
        for name in names:
            normalized = name.strip().lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(name)
        return tuple(ordered)

    def _execute_with_failure_capture(self, task: TaigaTask) -> TaigaExecutionResult:
        try:
            return self._execute_task(task)
        except Exception as exc:  # pragma: no cover - defensive safety net
            self._logger.exception("Task execution failed for task id=%s", task.task_id)
            return TaigaExecutionResult(
                outcome="failed",
                summary="Task execution failed before completion.",
                error=str(exc),
            )

    def _transition_with_result(
        self,
        task: TaigaTask,
        result: TaigaExecutionResult,
    ) -> None:
        target_status_name = self._target_status_for_outcome(result.outcome)
        result_comment = self._render_result_comment(result)

        self._adapter.append_result_and_transition(
            task_id=task.task_id,
            result_comment=result_comment,
            target_status_name=target_status_name,
        )

    def _target_status_for_outcome(self, outcome: TaigaOutcome) -> str:
        if outcome == "success":
            return self._config.success_status
        if outcome == "blocked":
            return self._config.blocked_status
        return self._config.failure_status

    def _render_result_comment(self, result: TaigaExecutionResult) -> str:
        timestamp = self._now().astimezone(UTC).isoformat().replace("+00:00", "Z")
        lines = [
            f"Outcome: {result.outcome.upper()}",
            f"Summary: {_single_line(result.summary, fallback='No summary provided.')}",
        ]
        if result.error:
            lines.append(f"Error: {_single_line(result.error, fallback='n/a')}")
        lines.extend(
            [
                f"Worker run id: {self._config.run_id}",
                f"Timestamp (UTC): {timestamp}",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _default_execute_task(task: TaigaTask) -> TaigaExecutionResult:
        return TaigaExecutionResult(
            outcome="success",
            summary=(
                "Automated Taiga worker completed task processing with default "
                f"executor for '{task.subject}'."
            ),
        )


def _single_line(value: str, *, fallback: str) -> str:
    collapsed = " ".join(value.strip().split())
    if not collapsed:
        return fallback
    return collapsed


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)
