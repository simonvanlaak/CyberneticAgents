from contextlib import contextmanager
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
        self.execution_log = None
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


def test_complete_task_persists_result_to_team_memory_for_sqlalchemy_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task

    task = Task(
        team_id=1,
        initiative_id=1,
        name="Collect profile links",
        content="Collect profile links",
        assignee="System1/root",
    )

    calls: dict[str, object] = {}
    monkeypatch.setattr(task_service, "_persist_task", lambda _task: None)
    monkeypatch.setattr(
        task_service,
        "_store_task_result_in_team_memory",
        lambda _task: calls.__setitem__("stored_task_id", _task.id),
    )

    task.id = 42
    task_service.complete_task(task, "done")

    assert task.result == "done"
    assert calls["stored_task_id"] == 42


def test_store_task_result_in_team_memory_creates_team_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status, SystemType

    class _FakeMemoryService:
        def __init__(self, **_kwargs) -> None:
            pass

        def create_entries(self, *, actor, requests):  # type: ignore[no-untyped-def]
            captured["actor"] = actor
            captured["requests"] = requests
            return []

    class _ControlSystem:
        id = 7
        team_id = 1
        type = SystemType.CONTROL
        agent_id_str = "System3/root"

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        task_service.systems_service,
        "get_system_by_type",
        lambda team_id, system_type: _ControlSystem(),
    )
    monkeypatch.setattr(task_service, "load_memory_backend_config", lambda: object())
    monkeypatch.setattr(task_service, "build_memory_registry", lambda _config: object())
    monkeypatch.setattr(task_service, "build_memory_metrics", lambda: object())
    monkeypatch.setattr(task_service, "LoggingMemoryAuditSink", lambda: object())
    monkeypatch.setattr(task_service, "MemoryCrudService", _FakeMemoryService)

    task = Task(
        team_id=1,
        initiative_id=3,
        name="Collect user identity",
        content="Collect user identity",
        assignee="System1/root",
    )
    task.id = 11
    task.status = Status.COMPLETED
    task.result = "User identity confirmed"

    task_service._store_task_result_in_team_memory(task)

    from src.cyberagent.memory.crud import MemoryActorContext, MemoryCreateRequest

    actor = cast(MemoryActorContext, captured["actor"])
    requests = cast(list[MemoryCreateRequest], captured["requests"])
    assert actor.agent_id == "System3/root"
    assert actor.team_id == 1
    assert len(requests) == 1
    request = requests[0]
    assert request.namespace == "team:1"
    assert request.content.startswith("Task #11")
    assert request.tags is not None
    assert "task_result" in request.tags
    assert "task:11" in request.tags


def test_create_task_builds_task(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import tasks as task_service

    created: dict[str, object] = {}

    class _FactoryTask(_FakeTask):
        def __init__(self, **kwargs) -> None:
            super().__init__()
            created.update(kwargs)

    class _Session:
        def add(self, _value) -> None:  # type: ignore[no-untyped-def]
            return None

        def flush(self) -> None:
            return None

        def commit(self) -> None:
            return None

        def refresh(self, _value) -> None:  # type: ignore[no-untyped-def]
            return None

        def expunge(self, _value) -> None:  # type: ignore[no-untyped-def]
            return None

    @contextmanager
    def _fake_managed_session(*, commit: bool = False):  # type: ignore[no-untyped-def]
        del commit
        yield _Session()

    monkeypatch.setattr(task_service, "Task", _FactoryTask)
    monkeypatch.setattr(task_service, "managed_session", _fake_managed_session)

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


def test_approve_task_rejects_invalid_transition() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.status = Status.PENDING

    with pytest.raises(ValueError, match="Invalid task status transition"):
        task_service.approve_task(task)


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


def test_complete_task_rejects_invalid_transition() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.status = Status.PENDING

    with pytest.raises(ValueError, match="Invalid task status transition"):
        task_service.complete_task(task, "done")


def test_allowed_task_transitions_match_canonical_lifecycle() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.enums import Status

    assert task_service.ALLOWED_TASK_TRANSITIONS == {
        Status.PENDING: {Status.IN_PROGRESS, Status.CANCELED},
        Status.IN_PROGRESS: {Status.COMPLETED, Status.BLOCKED},
        Status.BLOCKED: {Status.IN_PROGRESS, Status.CANCELED},
        Status.COMPLETED: {Status.APPROVED, Status.REJECTED},
        Status.REJECTED: {Status.CANCELED},
        Status.APPROVED: set(),
        Status.CANCELED: set(),
    }


@pytest.mark.parametrize(
    ("current", "next_status"),
    [
        ("pending", "in_progress"),
        ("pending", "canceled"),
        ("in_progress", "completed"),
        ("in_progress", "blocked"),
        ("blocked", "in_progress"),
        ("blocked", "canceled"),
        ("completed", "approved"),
        ("completed", "rejected"),
        ("rejected", "canceled"),
    ],
)
def test_transition_task_allows_canonical_transitions(
    current: str,
    next_status: str,
) -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.status = Status(current)

    task_service._transition_task(task, Status(next_status))

    assert task.status == Status(next_status)


@pytest.mark.parametrize(
    ("current", "invalid_next"),
    [
        ("pending", "approved"),
        ("in_progress", "approved"),
        ("blocked", "completed"),
        ("completed", "in_progress"),
        ("rejected", "approved"),
        ("approved", "canceled"),
        ("canceled", "pending"),
    ],
)
def test_transition_task_rejects_invalid_transition_for_each_state(
    current: str,
    invalid_next: str,
) -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.status = Status(current)

    with pytest.raises(ValueError, match="Invalid task status transition"):
        task_service._transition_task(task, Status(invalid_next))


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


def test_set_task_execution_log_updates_field() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task

    task = cast(Task, _FakeTask())
    task_service.set_task_execution_log(task, '[{"type":"TextMessage"}]')

    assert task.execution_log == '[{"type":"TextMessage"}]'
    assert task.updated is True


def test_record_invalid_review_event_resets_task_within_retry_limit() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.status = Status.IN_PROGRESS
    task.assignee = "System1/root"
    task.invalid_review_retry_count = 0

    retry_count, should_auto_retry = task_service.record_invalid_review_event(
        task,
        "TaskReviewMessage received for non-review-eligible status 'in_progress'.",
    )

    assert retry_count == 1
    assert should_auto_retry is True
    assert task.invalid_review_retry_count == 1
    assert task.status == Status.PENDING
    assert task.assignee is None
    assert task.reasoning is not None
    assert "non-review-eligible" in task.reasoning
    assert task.updated is True


def test_record_invalid_review_event_stops_auto_retry_after_cap() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.status = Status.IN_PROGRESS
    task.assignee = "System1/root"
    task.invalid_review_retry_count = 3

    retry_count, should_auto_retry = task_service.record_invalid_review_event(
        task,
        "TaskReviewMessage received for non-review-eligible status 'in_progress'.",
    )

    assert retry_count == 4
    assert should_auto_retry is False
    assert task.invalid_review_retry_count == 4
    assert task.status == Status.IN_PROGRESS
    assert task.assignee == "System1/root"
    assert task.reasoning is not None
    assert "non-review-eligible" in task.reasoning
    assert task.updated is True


def test_archive_rejected_task_creates_pending_replacement_with_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    original = cast(Task, _FakeTask())
    original.id = 14
    original.team_id = 5
    original.initiative_id = 22
    original.name = "Collect links"
    original.content = "Collect all source links"
    original.status = Status.REJECTED
    original.assignee = "System1/original"
    original.follow_up_task_id = None

    replacement = cast(Task, _FakeTask())
    replacement.id = 15
    replacement.status = Status.PENDING
    replacement.assignee = None
    replacement.replaces_task_id = None

    monkeypatch.setattr(task_service, "create_task", lambda **_kwargs: replacement)
    monkeypatch.setattr(task_service, "_persist_task", lambda task: task.update())

    created = task_service.archive_rejected_task_with_replacement(
        original,
        replacement_name="Collect links (replacement)",
        replacement_content="Collect all source links\n\nChange: include LinkedIn profile URL.",
        replacement_reasoning="Policy remediation approved",
    )

    assert created is replacement
    assert original.status == Status.CANCELED
    assert original.assignee == "System1/original"
    assert original.follow_up_task_id == 15
    assert replacement.replaces_task_id == 14
    assert replacement.status == Status.PENDING
    assert replacement.assignee is None
    assert replacement.reasoning == "Policy remediation approved"


def test_archive_rejected_task_raises_for_non_rejected_status() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.id = 14
    task.team_id = 5
    task.initiative_id = 22
    task.name = "Collect links"
    task.content = "Collect all source links"
    task.status = Status.COMPLETED

    with pytest.raises(ValueError, match="must be in rejected status"):
        task_service.archive_rejected_task_with_replacement(
            task,
            replacement_name="Collect links (replacement)",
            replacement_content="Collect all source links",
        )


def test_is_review_eligible_for_task_when_completed_or_blocked() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.status = Status.COMPLETED
    assert task_service.is_review_eligible_for_task(task) is True

    task.status = Status.BLOCKED
    assert task_service.is_review_eligible_for_task(task) is True

    task.status = Status.PENDING
    assert task_service.is_review_eligible_for_task(task) is False


def test_is_review_eligible_for_task_supports_prefixed_status_strings() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task

    task = _FakeTask()
    task.status = "Status.BLOCKED"
    assert task_service.is_review_eligible_for_task(cast(Task, task)) is True

    task.status = "Status.PENDING"
    assert task_service.is_review_eligible_for_task(cast(Task, task)) is False


def test_finalize_task_review_approves_only_when_all_cases_satisfied() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.status = Status.COMPLETED

    task_service.finalize_task_review(
        task,
        [
            {"policy_id": 1, "judgement": "Satisfied", "reasoning": "ok"},
            {"policy_id": 2, "judgement": "Satisfied", "reasoning": "still ok"},
        ],
    )

    assert task.status == Status.APPROVED
    assert task.policy_judgement == "Satisfied"
    assert task.updated is True


def test_finalize_task_review_rejects_when_violated_and_no_vague() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.status = Status.COMPLETED

    task_service.finalize_task_review(
        task,
        [
            {"policy_id": 1, "judgement": "Satisfied", "reasoning": "ok"},
            {"policy_id": 2, "judgement": "Violated", "reasoning": "bad"},
        ],
    )

    assert task.status == Status.REJECTED
    assert task.policy_judgement == "Violated"
    assert task.updated is True


def test_finalize_task_review_does_not_approve_blocked_tasks() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.status = Status.BLOCKED

    task_service.finalize_task_review(
        task,
        [
            {"policy_id": 1, "judgement": "Satisfied", "reasoning": "ok"},
            {"policy_id": 2, "judgement": "Satisfied", "reasoning": "still ok"},
        ],
    )

    assert task.status == Status.BLOCKED
    assert task.policy_judgement == "Satisfied"
    assert task.updated is True


def test_finalize_task_review_keeps_completed_when_any_case_is_vague() -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task
    from src.enums import Status

    task = cast(Task, _FakeTask())
    task.status = Status.COMPLETED

    task_service.finalize_task_review(
        task,
        [
            {"policy_id": 1, "judgement": "Satisfied", "reasoning": "ok"},
            {
                "policy_id": 2,
                "judgement": "Vague",
                "reasoning": "policy wording unclear",
            },
            {"policy_id": 3, "judgement": "Violated", "reasoning": "bad"},
        ],
    )

    assert task.status == Status.COMPLETED
    assert task.policy_judgement == "Violated"
    assert task.updated is True


def test_persist_task_uses_session_merge_for_sqlalchemy_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cyberagent.services import tasks as task_service
    from src.cyberagent.db.models.task import Task

    class _Session:
        def __init__(self) -> None:
            self.merged = None
            self.closed = False

        def merge(self, task) -> None:  # type: ignore[no-untyped-def]
            self.merged = task

        def close(self) -> None:
            self.closed = True

    session = _Session()

    @contextmanager
    def _fake_managed_session(*, commit: bool = False):  # type: ignore[no-untyped-def]
        assert commit is True
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(task_service, "managed_session", _fake_managed_session)
    task = Task(team_id=1, initiative_id=1, name="Task", content="Do it")

    task_service.complete_task(task, "done")

    assert session.merged is task
    assert session.closed is True
