# System1 Agent Tests
# Tests for System1 (Operations) agent functionality

import pytest
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, CancellationToken, MessageContext
from unittest.mock import AsyncMock

from src.agents.system1 import System1
from src.agents.messages import (
    TaskAssignMessage,
    TaskReviewMessage,
)


class TestSystem1Basic:
    """Test System1 basic functionality."""

    def test_system1_creation(self):
        """Test System1 creation with proper AutoGen format."""
        # Use AutoGen format: "type/key"
        system1 = System1("System1/worker1")
        assert system1 is not None
        assert system1.agent_id.type == "System1"
        assert system1.agent_id.key == "worker1"

    def test_system1_identity_and_responsibilities(self):
        """Test System1 identity and responsibility prompts."""
        system1 = System1("System1/worker1")

        # Check identity prompt
        assert "operational execution system" in system1.identity_prompt
        assert "execute operations directly" in system1.identity_prompt

        # Check responsibility prompts
        assert len(system1.responsibility_prompts) == 3
        assert "Execute tasks" in system1.responsibility_prompts[0]
        assert "Return results" in system1.responsibility_prompts[1]
        assert "lacking the ability" in system1.responsibility_prompts[2]

    def test_system1_handler_exists(self):
        """Test that System1 has the required message handler."""
        system1 = System1("System1/worker1")
        assert hasattr(system1, "handle_assign_task_message")
        assert callable(getattr(system1, "handle_assign_task_message"))


class TestSystem1Messages:
    """Test System1 message handling."""

    def test_task_assign_message_creation(self):
        """Test TaskAssignMessage creation."""
        message = TaskAssignMessage(
            task_id=1,
            assignee_agent_id_str="System1/worker1",
            source="System3/manager",
            content="Test task",
        )
        assert message.task_id == 1
        assert message.assignee_agent_id_str == "System1/worker1"
        assert message.source == "System3/manager"
        assert message.content == "Test task"

    def test_task_review_message_creation(self):
        """Test TaskReviewMessage creation."""
        message = TaskReviewMessage(
            task_id=1,
            assignee_agent_id_str="System1/worker1",
            content="Task completed",
            source="System1/worker1",
        )
        assert message.task_id == 1
        assert message.assignee_agent_id_str == "System1/worker1"
        assert message.content == "Task completed"
        assert message.source == "System1/worker1"


class TestSystem1Integration:
    """Test System1 integration scenarios."""

    def test_system1_with_trace_context(self):
        """Test System1 with trace context."""
        trace_context = {"trace_id": "abc123", "span_id": "def456"}
        system1 = System1("System1/worker1", trace_context=trace_context)
        assert system1.trace_context == trace_context


@pytest.mark.asyncio
async def test_system1_basic_smoke_test():
    """Basic smoke test for System1."""
    # Test creation
    system1 = System1("System1/worker1")
    assert system1 is not None
    print(f"System1 created: {system1.name}")
    print(f"System1 agent ID: {system1.agent_id}")

    # Test message creation
    task_message = TaskAssignMessage(
        task_id=1,
        assignee_agent_id_str="System1/worker1",
        source="System3/manager",
        content="Test task",
    )
    assert task_message.task_id == 1
    print(f"Task message created: {task_message.content}")

    # Test responsibility prompts
    for i, prompt in enumerate(system1.responsibility_prompts, 1):
        print(f"Responsibility {i}: {prompt}")

    print("System1 basic functionality test completed successfully!")


if __name__ == "__main__":
    # Run basic test
    import asyncio

    asyncio.run(test_system1_basic_smoke_test())


@pytest.mark.asyncio
async def test_system1_uses_context_sender_for_task_requestor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system1 = System1("System1/worker1")
    message = TaskAssignMessage(
        task_id=7,
        assignee_agent_id_str="System1/worker1",
        source="System3_root",
        content="Define scope",
    )
    ctx = MessageContext(
        sender=AgentId.from_str("System3/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )

    class _DummyTask:
        pass

    monkeypatch.setattr(
        "src.cyberagent.services.tasks.start_task", lambda _task_id: _DummyTask()
    )
    monkeypatch.setattr("src.cyberagent.services.tasks.complete_task", lambda *_: None)
    monkeypatch.setattr(
        system1,
        "run",
        AsyncMock(
            return_value=TaskResult(
                messages=[
                    TextMessage(
                        content='{"status":"done","result":"Task executed","reasoning":null}',
                        source="System1/worker1",
                    )
                ]
            )
        ),
    )
    system1._publish_message_to_agent = AsyncMock()  # type: ignore[attr-defined]

    await system1.handle_assign_task_message(message=message, ctx=ctx)  # type: ignore[call-arg]

    assert system1._publish_message_to_agent.await_count == 1  # type: ignore[attr-defined]
    published_args = system1._publish_message_to_agent.await_args.args  # type: ignore[attr-defined]
    recipient = published_args[1]
    assert str(recipient) == "System3/root"


@pytest.mark.asyncio
async def test_system1_blocked_marks_task_and_escalates_to_system3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system1 = System1("System1/worker1")
    message = TaskAssignMessage(
        task_id=9,
        assignee_agent_id_str="System1/worker1",
        source="System3/root",
        content="Fetch private data",
    )
    ctx = MessageContext(
        sender=AgentId.from_str("System3/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="blocked-task",
    )

    class _DummyTask:
        pass

    task = _DummyTask()
    captured: dict[str, object] = {"complete_called": False}

    monkeypatch.setattr(
        "src.cyberagent.services.tasks.start_task", lambda _task_id: task
    )
    monkeypatch.setattr(
        "src.cyberagent.services.tasks.complete_task",
        lambda *_: captured.__setitem__("complete_called", True),
    )
    monkeypatch.setattr(
        "src.cyberagent.services.tasks.mark_task_blocked",
        lambda _task, reason: captured.__setitem__("reason", reason),
    )
    monkeypatch.setattr(
        system1,
        "run",
        AsyncMock(
            return_value=TaskResult(
                messages=[
                    TextMessage(
                        content='{"status":"blocked","result":"Cannot proceed.","reasoning":"Missing API key"}',
                        source="System1/worker1",
                    )
                ]
            )
        ),
    )
    system1._publish_message_to_agent = AsyncMock()  # type: ignore[attr-defined]

    await system1.handle_assign_task_message(message=message, ctx=ctx)  # type: ignore[call-arg]

    assert captured["complete_called"] is False
    assert captured["reason"] == "Missing API key"
    assert system1._publish_message_to_agent.await_count == 1  # type: ignore[attr-defined]
    first_args = system1._publish_message_to_agent.await_args_list[0].args  # type: ignore[attr-defined]
    assert isinstance(first_args[0], TaskReviewMessage)
    assert first_args[0].task_id == 9
    assert first_args[0].content == "Missing API key"
    assert str(first_args[1]) == "System3/root"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_output",
    [
        "I need more details before I can complete this task.",
        '{"status":"blocked","result":"Missing context"',
        '{"result":"Need clarification on user identity links."}',
    ],
)
async def test_system1_ambiguous_output_marks_task_blocked(
    monkeypatch: pytest.MonkeyPatch, raw_output: str
) -> None:
    system1 = System1("System1/worker1")
    message = TaskAssignMessage(
        task_id=10,
        assignee_agent_id_str="System1/worker1",
        source="System3/root",
        content="Collect user identity and links",
    )
    ctx = MessageContext(
        sender=AgentId.from_str("System3/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="ambiguous-output",
    )

    class _DummyTask:
        pass

    task = _DummyTask()
    captured: dict[str, object] = {"complete_called": False}

    monkeypatch.setattr(
        "src.cyberagent.services.tasks.start_task", lambda _task_id: task
    )
    monkeypatch.setattr(
        "src.cyberagent.services.tasks.complete_task",
        lambda *_: captured.__setitem__("complete_called", True),
    )
    monkeypatch.setattr(
        "src.cyberagent.services.tasks.mark_task_blocked",
        lambda _task, reason: captured.__setitem__("reason", reason),
    )
    monkeypatch.setattr(
        system1,
        "run",
        AsyncMock(
            return_value=TaskResult(
                messages=[TextMessage(content=raw_output, source="System1/worker1")]
            )
        ),
    )
    system1._publish_message_to_agent = AsyncMock()  # type: ignore[attr-defined]

    await system1.handle_assign_task_message(message=message, ctx=ctx)  # type: ignore[call-arg]

    assert captured["complete_called"] is False
    assert isinstance(captured.get("reason"), str)
    assert system1._publish_message_to_agent.await_count == 1  # type: ignore[attr-defined]
    published_types = [
        type(call.args[0]).__name__
        for call in system1._publish_message_to_agent.await_args_list  # type: ignore[attr-defined]
    ]
    assert published_types == [TaskReviewMessage.__name__]


@pytest.mark.asyncio
async def test_system1_blocked_also_requests_task_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system1 = System1("System1/worker1")
    message = TaskAssignMessage(
        task_id=17,
        assignee_agent_id_str="System1/worker1",
        source="System3/root",
        content="Collect user identity and links",
    )
    ctx = MessageContext(
        sender=AgentId.from_str("System3/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="blocked-review-request",
    )

    class _DummyTask:
        pass

    monkeypatch.setattr(
        "src.cyberagent.services.tasks.start_task", lambda _task_id: _DummyTask()
    )
    monkeypatch.setattr(
        "src.cyberagent.services.tasks.mark_task_blocked",
        lambda *_: None,
    )
    monkeypatch.setattr(
        system1,
        "run",
        AsyncMock(
            return_value=TaskResult(
                messages=[
                    TextMessage(
                        content='{"status":"blocked","result":"Need clarification.","reasoning":"Ambiguous output"}',
                        source="System1/worker1",
                    )
                ]
            )
        ),
    )
    system1._publish_message_to_agent = AsyncMock()  # type: ignore[attr-defined]

    await system1.handle_assign_task_message(message=message, ctx=ctx)  # type: ignore[call-arg]

    published_types = [
        type(call.args[0]).__name__
        for call in system1._publish_message_to_agent.await_args_list  # type: ignore[attr-defined]
    ]
    assert TaskReviewMessage.__name__ in published_types


@pytest.mark.asyncio
async def test_system1_requests_structured_task_execution_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system1 = System1("System1/worker1")
    message = TaskAssignMessage(
        task_id=23,
        assignee_agent_id_str="System1/worker1",
        source="System3/root",
        content="Define scope",
    )
    ctx = MessageContext(
        sender=AgentId.from_str("System3/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="structured-execution-output",
    )

    class _DummyTask:
        pass

    monkeypatch.setattr(
        "src.cyberagent.services.tasks.start_task", lambda _task_id: _DummyTask()
    )
    monkeypatch.setattr("src.cyberagent.services.tasks.complete_task", lambda *_: None)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "src.cyberagent.services.tasks.set_task_execution_log",
        lambda _task, execution_log: captured.__setitem__(
            "execution_log", execution_log
        ),
    )
    mocked_run = AsyncMock(
        return_value=TaskResult(
            messages=[
                TextMessage(
                    content='{"status":"done","result":"Task executed","reasoning":null}',
                    source="System1/worker1",
                )
            ]
        )
    )
    monkeypatch.setattr(system1, "run", mocked_run)
    system1._publish_message_to_agent = AsyncMock()  # type: ignore[attr-defined]

    await system1.handle_assign_task_message(message=message, ctx=ctx)  # type: ignore[call-arg]

    assert mocked_run.await_count == 1
    await_args = mocked_run.await_args
    assert await_args is not None
    assert "output_content_type" not in await_args.kwargs
    assert isinstance(captured.get("execution_log"), str)
    assert "Task executed" in str(captured["execution_log"])


@pytest.mark.asyncio
async def test_system1_task_execution_enables_tools_and_guides_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system1 = System1("System1/worker1")
    message = TaskAssignMessage(
        task_id=24,
        assignee_agent_id_str="System1/worker1",
        source="System3/root",
        content="Collect source details",
    )
    ctx = MessageContext(
        sender=AgentId.from_str("System3/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="tool-enabled-task-execution",
    )

    class _DummyTask:
        pass

    monkeypatch.setattr(
        "src.cyberagent.services.tasks.start_task", lambda _task_id: _DummyTask()
    )
    monkeypatch.setattr("src.cyberagent.services.tasks.complete_task", lambda *_: None)
    mocked_run = AsyncMock(
        return_value=TaskResult(
            messages=[
                TextMessage(
                    content='{"status":"done","result":"Task executed","reasoning":null}',
                    source="System1/worker1",
                )
            ]
        )
    )
    monkeypatch.setattr(system1, "run", mocked_run)
    system1._publish_message_to_agent = AsyncMock()  # type: ignore[attr-defined]

    await system1.handle_assign_task_message(message=message, ctx=ctx)  # type: ignore[call-arg]

    await_args = mocked_run.await_args
    assert await_args is not None
    assert await_args.kwargs["enable_tools"] is True
    prompts = await_args.kwargs["message_specific_prompts"]
    assert any(
        "Return a JSON object for the task outcome" in prompt for prompt in prompts
    )
    assert any(
        "Do not call a tool named TaskExecutionResult" in prompt for prompt in prompts
    )
    assert any("task_search" in prompt for prompt in prompts)
    assert any("memory_crud" in prompt for prompt in prompts)


@pytest.mark.asyncio
async def test_system1_marks_task_blocked_when_execution_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system1 = System1("System1/worker1")
    message = TaskAssignMessage(
        task_id=25,
        assignee_agent_id_str="System1/worker1",
        source="System3/root",
        content="Collect user documents",
    )
    ctx = MessageContext(
        sender=AgentId.from_str("System3/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="execution-error",
    )

    class _DummyTask:
        pass

    task = _DummyTask()
    captured: dict[str, object] = {"complete_called": False}
    monkeypatch.setattr(
        "src.cyberagent.services.tasks.start_task", lambda _task_id: task
    )
    monkeypatch.setattr(
        "src.cyberagent.services.tasks.complete_task",
        lambda *_: captured.__setitem__("complete_called", True),
    )
    monkeypatch.setattr(
        "src.cyberagent.services.tasks.mark_task_blocked",
        lambda _task, reason: captured.__setitem__("reason", reason),
    )
    monkeypatch.setattr(
        system1,
        "run",
        AsyncMock(side_effect=RuntimeError("simulated execution failure")),
    )
    system1._publish_message_to_agent = AsyncMock()  # type: ignore[attr-defined]

    await system1.handle_assign_task_message(message=message, ctx=ctx)  # type: ignore[call-arg]

    assert captured["complete_called"] is False
    reason = str(captured.get("reason", ""))
    assert "simulated execution failure" in reason
    assert system1._publish_message_to_agent.await_count == 1  # type: ignore[attr-defined]
    published_args = system1._publish_message_to_agent.await_args.args  # type: ignore[attr-defined]
    review_message = published_args[0]
    recipient = published_args[1]
    assert isinstance(review_message, TaskReviewMessage)
    assert review_message.task_id == 25
    assert "simulated execution failure" in review_message.content
    assert str(recipient) == "System3/root"
