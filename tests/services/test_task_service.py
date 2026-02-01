import pytest


class _FakeTask:
    def __init__(self) -> None:
        self.status = None
        self.result = None
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

    task = _FakeTask()

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

    task = _FakeTask()

    task_service.assign_task(task, "agent-1")

    assert task.assignee == "agent-1"
    assert task.updated is True


def test_approve_task_updates_status() -> None:
    from src.cyberagent.services import tasks as task_service

    task = _FakeTask()

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
