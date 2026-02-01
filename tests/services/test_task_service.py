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


def test_start_task_updates_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import tasks as task_service

    task = _FakeTask()
    monkeypatch.setattr(task_service, "get_task", lambda task_id: task)

    result = task_service.start_task(123)

    assert result is task
    assert task.updated is True
    assert task.status is not None


def test_start_task_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import tasks as task_service

    monkeypatch.setattr(task_service, "get_task", lambda task_id: None)

    with pytest.raises(ValueError):
        task_service.start_task(999)


def test_complete_task_sets_result() -> None:
    from src.cyberagent.services import tasks as task_service

    task = _FakeTask()

    task_service.complete_task(task, "done")

    assert task.result == "done"
    assert task.updated is True
