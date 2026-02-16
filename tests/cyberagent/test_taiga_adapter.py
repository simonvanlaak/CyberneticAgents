"""Tests for the thin Taiga adapter PoC used by issue #114."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.cyberagent.integrations.taiga.adapter import (
    TaigaAdapter,
    TaigaTask,
)


@dataclass
class _FakeResponse:
    status_code: int
    payload: object

    def json(self) -> object:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSession:
    def __init__(self, *, get_responses: list[_FakeResponse] | None = None) -> None:
        self._get_responses = get_responses or []
        self.get_calls: list[tuple[str, dict[str, object]]] = []
        self.patch_calls: list[tuple[str, dict[str, object]]] = []
        self.headers: dict[str, str] = {}

    def get(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        timeout: int,
    ) -> _FakeResponse:
        self.get_calls.append((url, {"params": params or {}, "timeout": timeout}))
        if not self._get_responses:
            raise AssertionError("Unexpected GET call")
        return self._get_responses.pop(0)

    def patch(
        self,
        url: str,
        *,
        json: dict[str, object],
        timeout: int,
    ) -> _FakeResponse:
        self.patch_calls.append((url, {"json": json, "timeout": timeout}))
        return _FakeResponse(status_code=200, payload={})


def test_list_assigned_tasks_uses_expected_filters() -> None:
    """List call should pass project/assignee/status filters to Taiga."""
    session = _FakeSession(
        get_responses=[
            _FakeResponse(
                status_code=200,
                payload=[
                    {
                        "id": 77,
                        "ref": 12,
                        "subject": "Verify adapter PoC",
                        "status": 3,
                        "project": 44,
                        "version": 8,
                    }
                ],
            )
        ]
    )
    adapter = TaigaAdapter(
        base_url="http://taiga.local",
        token="test-token",
        session=session,
    )

    tasks = adapter.list_assigned_tasks(
        project_slug="cyberneticagents",
        assignee="taiga-bot",
        status_slug="pending",
    )

    assert tasks == [
        TaigaTask(
            task_id=77,
            ref=12,
            subject="Verify adapter PoC",
            status_id=3,
            project_id=44,
            version=8,
        )
    ]

    assert session.get_calls == [
        (
            "http://taiga.local/api/v1/tasks",
            {
                "params": {
                    "project__slug": "cyberneticagents",
                    "assigned_to": "taiga-bot",
                    "status__slug": "pending",
                },
                "timeout": 20,
            },
        )
    ]


def test_append_result_and_transition_updates_comment_and_status() -> None:
    """Adapter should write result comment and status transition in one patch."""
    session = _FakeSession(
        get_responses=[
            _FakeResponse(
                status_code=200,
                payload={
                    "id": 77,
                    "ref": 12,
                    "subject": "Verify adapter PoC",
                    "status": 3,
                    "project": 44,
                    "version": 8,
                },
            ),
            _FakeResponse(
                status_code=200,
                payload=[
                    {"id": 3, "name": "pending", "slug": "pending"},
                    {"id": 5, "name": "completed", "slug": "completed"},
                ],
            ),
        ]
    )
    adapter = TaigaAdapter(
        base_url="http://taiga.local",
        token="test-token",
        session=session,
    )

    adapter.append_result_and_transition(
        task_id=77,
        result_comment="Automation finished successfully.",
        target_status_name="completed",
    )

    assert session.patch_calls == [
        (
            "http://taiga.local/api/v1/tasks/77",
            {
                "json": {
                    "version": 8,
                    "status": 5,
                    "comment": "Automation finished successfully.",
                },
                "timeout": 20,
            },
        )
    ]


def test_append_result_and_transition_raises_when_status_missing() -> None:
    """A clear error is raised when requested status does not exist."""
    session = _FakeSession(
        get_responses=[
            _FakeResponse(
                status_code=200,
                payload={
                    "id": 77,
                    "ref": 12,
                    "subject": "Verify adapter PoC",
                    "status": 3,
                    "project": 44,
                    "version": 8,
                },
            ),
            _FakeResponse(
                status_code=200,
                payload=[
                    {"id": 3, "name": "pending", "slug": "pending"},
                ],
            ),
        ]
    )
    adapter = TaigaAdapter(
        base_url="http://taiga.local",
        token="test-token",
        session=session,
    )

    with pytest.raises(ValueError, match="target status 'completed'"):
        adapter.append_result_and_transition(
            task_id=77,
            result_comment="Automation finished successfully.",
            target_status_name="completed",
        )


def test_process_first_assigned_task_runs_one_item_cycle() -> None:
    """Bridge helper should pull one assigned task and update it."""
    session = _FakeSession(
        get_responses=[
            _FakeResponse(
                status_code=200,
                payload=[
                    {
                        "id": 77,
                        "ref": 12,
                        "subject": "Verify adapter PoC",
                        "status": 3,
                        "project": 44,
                        "version": 8,
                    }
                ],
            ),
            _FakeResponse(
                status_code=200,
                payload={
                    "id": 77,
                    "ref": 12,
                    "subject": "Verify adapter PoC",
                    "status": 3,
                    "project": 44,
                    "version": 8,
                },
            ),
            _FakeResponse(
                status_code=200,
                payload=[
                    {"id": 3, "name": "pending", "slug": "pending"},
                    {"id": 5, "name": "completed", "slug": "completed"},
                ],
            ),
        ]
    )
    adapter = TaigaAdapter(
        base_url="http://taiga.local",
        token="test-token",
        session=session,
    )

    task = adapter.process_first_assigned_task(
        project_slug="cyberneticagents",
        assignee="taiga-bot",
        source_status_slug="pending",
        result_comment="Automation finished successfully.",
        target_status_name="completed",
    )

    assert task is not None
    assert task.task_id == 77
    assert session.patch_calls == [
        (
            "http://taiga.local/api/v1/tasks/77",
            {
                "json": {
                    "version": 8,
                    "status": 5,
                    "comment": "Automation finished successfully.",
                },
                "timeout": 20,
            },
        )
    ]
