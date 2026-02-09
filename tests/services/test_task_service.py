from typing import cast

import pytest


class _FakeTask:
    def __init__(self) -> None:
        self.assignee = None
        self.status = None
        self.result = None
        self.reasoning = None
        self.policy_judgement = None
        self.policy_judgement_reasoning = None
        self.case_judgement = None
        self.updated = False

    def set_status(self, status) -> None:
        self.status = status

    def update(self) -> None:
        self.updated = True

    def add(self) -> int:
        self.updated = True
        return 123


def test_start_task_updates_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import tasks as task_service

    task = _FakeTask()
    monkeypatch.setattr(task_service, "_get_task", lambda task_id: task)

    result = task_service.start_task(123)

    assert result is task
    assert task.updated is True
    assert task.status is not None


def test_start_task_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import tasks as task_service

    monkeypatch.setattr(task_service, "_get_task", lambda task_id: None)

    with pytest.raises(ValueError):
        task_service.start_task(999)


def test_complete_task_sets_result() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task

    task = cast(Task, _FakeTask())

    task_service.complete_task(task, "done")

    assert task.result == "done"
    assert task.updated is True


def test_create_task_builds_task(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import tasks as task_service

    created: dict[str, object] = {}

    class _FactoryTask(_FakeTask):
        def __init__(self, **kwargs) -> None:
            super().__init__()
            created.update(kwargs)

    monkeypatch.setattr(task_service, "Task", _FactoryTask)

    task = task_service.create_task(
        team_id=1,
        initiative_id=2,
        name="Task",
        content="Do it",
    )

    assert isinstance(task, _FactoryTask)
    assert created["team_id"] == 1
    assert created["initiative_id"] == 2
    assert created["name"] == "Task"
    assert created["content"] == "Do it"


def test_assign_task_sets_assignee() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task

    task = cast(Task, _FakeTask())

    task_service.assign_task(task, "agent-1")

    assert task.assignee == "agent-1"
    assert task.updated is True


def test_approve_task_updates_status() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task

    task = cast(Task, _FakeTask())

    task_service.approve_task(task)

    assert task.status is not None
    assert task.updated is True


def test_get_task_by_id_returns_task(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import tasks as task_service

    task = _FakeTask()
    monkeypatch.setattr(task_service, "_get_task", lambda task_id: task)

    assert task_service.get_task_by_id(12) is task


def test_get_task_by_id_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import tasks as task_service

    monkeypatch.setattr(task_service, "_get_task", lambda task_id: None)

    with pytest.raises(ValueError):
        task_service.get_task_by_id(44)


def test_mark_task_blocked_updates_status_and_reasoning() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task

    task = cast(Task, _FakeTask())

    task_service.mark_task_blocked(task, "Missing external API credentials")

    assert task.status is not None
    assert task.reasoning == "Missing external API credentials"
    assert task.updated is True


def test_set_task_case_judgement_updates_policy_judgement_fields() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task

    task = cast(Task, _FakeTask())

    task_service.set_task_case_judgement(
        task,
        [
            {"policy_id": 1, "judgement": "Satisfied", "reasoning": "ok"},
            {"policy_id": 2, "judgement": "Violated", "reasoning": "missing evidence"},
        ],
    )

    assert task.case_judgement is not None
    assert task.policy_judgement == "Violated"
    assert task.policy_judgement_reasoning == "missing evidence"
    assert task.updated is True


def test_persist_task_uses_session_merge_for_sqlalchemy_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task

    class _Session:
        def __init__(self) -> None:
            self.merged = None
            self.committed = False
            self.closed = False

        def merge(self, task) -> None:  # type: ignore[no-untyped-def]
            self.merged = task

        def commit(self) -> None:
            self.committed = True

        def close(self) -> None:
            self.closed = True

    session = _Session()

    def _fake_get_db():  # type: ignore[no-untyped-def]
        yield session

    monkeypatch.setattr(task_service, "get_db", _fake_get_db)
    task = Task(team_id=1, initiative_id=1, name="Task", content="Do it")

    task_service.complete_task(task, "done")

    assert session.merged is task
    assert session.committed is True
    assert session.closed is True
