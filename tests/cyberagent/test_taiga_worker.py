"""Tests for the Taiga worker loop promoted from the PoC bridge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.cyberagent.integrations.taiga.adapter import TaigaTask
from src.cyberagent.integrations.taiga.worker import (
    TaigaExecutionResult,
    TaigaWorker,
    TaigaWorkerConfig,
)


@dataclass
class _TransitionCall:
    task_id: int
    target_status_name: str
    result_comment: str


class _FakeAdapter:
    def __init__(
        self,
        *,
        tasks: list[TaigaTask],
        claim_results: list[bool] | None = None,
    ) -> None:
        self._tasks = tasks
        self._claim_results = claim_results or [True for _ in tasks]
        self.list_calls: list[tuple[str, str, str]] = []
        self.validation_calls: list[tuple[int, tuple[str, ...]]] = []
        self.claim_calls: list[tuple[int, str]] = []
        self.transition_calls: list[_TransitionCall] = []

    def list_assigned_tasks(
        self,
        *,
        project_slug: str,
        assignee: str,
        status_slug: str,
    ) -> list[TaigaTask]:
        self.list_calls.append((project_slug, assignee, status_slug))
        return list(self._tasks)

    def validate_required_statuses(
        self,
        *,
        project_id: int,
        required_status_names: tuple[str, ...],
    ) -> None:
        self.validation_calls.append((project_id, required_status_names))

    def claim_task(self, task: TaigaTask, *, target_status_name: str) -> bool:
        self.claim_calls.append((task.task_id, target_status_name))
        if self._claim_results:
            return self._claim_results.pop(0)
        return True

    def append_result_and_transition(
        self,
        *,
        task_id: int,
        result_comment: str,
        target_status_name: str,
    ) -> None:
        self.transition_calls.append(
            _TransitionCall(
                task_id=task_id,
                target_status_name=target_status_name,
                result_comment=result_comment,
            )
        )


def _build_task(task_id: int) -> TaigaTask:
    return TaigaTask(
        task_id=task_id,
        ref=task_id,
        subject=f"Task {task_id}",
        status_id=1,
        project_id=900,
        version=3,
    )


def test_run_once_claims_tasks_and_writes_structured_success_comment() -> None:
    adapter = _FakeAdapter(tasks=[_build_task(1), _build_task(2)])
    worker = TaigaWorker(
        adapter=adapter,
        config=TaigaWorkerConfig(
            project_slug="cyberneticagents",
            assignee="taiga-bot",
            run_id="run-123",
            max_tasks=2,
            once=True,
        ),
        execute_task=lambda _: TaigaExecutionResult(
            outcome="success", summary="Execution completed"
        ),
        now=lambda: datetime(2026, 2, 16, 10, 45, tzinfo=UTC),
    )

    processed = worker.run_once()

    assert processed == 2
    assert adapter.list_calls == [("cyberneticagents", "taiga-bot", "pending")]
    assert adapter.validation_calls == [
        (900, ("pending", "in_progress", "completed", "blocked"))
    ]
    assert adapter.claim_calls == [(1, "in_progress"), (2, "in_progress")]
    assert [call.target_status_name for call in adapter.transition_calls] == [
        "completed",
        "completed",
    ]
    assert "Outcome: SUCCESS" in adapter.transition_calls[0].result_comment
    assert "Worker run id: run-123" in adapter.transition_calls[0].result_comment


def test_run_once_skips_task_when_claim_has_version_conflict() -> None:
    adapter = _FakeAdapter(
        tasks=[_build_task(1), _build_task(2)],
        claim_results=[False, True],
    )
    worker = TaigaWorker(
        adapter=adapter,
        config=TaigaWorkerConfig(project_slug="cyberneticagents", assignee="taiga-bot"),
        execute_task=lambda _: TaigaExecutionResult(outcome="success", summary="Done"),
    )

    processed = worker.run_once()

    assert processed == 1
    assert [call.task_id for call in adapter.transition_calls] == [2]


def test_run_once_maps_execution_exceptions_to_failed_and_blocked_status() -> None:
    adapter = _FakeAdapter(tasks=[_build_task(7)])

    def _raise(_: TaigaTask) -> TaigaExecutionResult:
        raise RuntimeError("executor boom")

    worker = TaigaWorker(
        adapter=adapter,
        config=TaigaWorkerConfig(project_slug="cyberneticagents", assignee="taiga-bot"),
        execute_task=_raise,
    )

    processed = worker.run_once()

    assert processed == 1
    assert adapter.transition_calls[0].target_status_name == "blocked"
    assert "Outcome: FAILED" in adapter.transition_calls[0].result_comment
    assert "Error: executor boom" in adapter.transition_calls[0].result_comment


def test_run_loop_returns_zero_when_interrupted() -> None:
    adapter = _FakeAdapter(tasks=[])

    sleeps: list[float] = []

    def _sleep(seconds: float) -> None:
        sleeps.append(seconds)
        raise KeyboardInterrupt

    worker = TaigaWorker(
        adapter=adapter,
        config=TaigaWorkerConfig(
            project_slug="cyberneticagents",
            assignee="taiga-bot",
            once=False,
            poll_seconds=12.5,
        ),
        sleep=_sleep,
    )

    assert worker.run() == 0
    assert sleeps == [12.5]
