# System3 Agent Tests
# Tests for System3 (Control) agent functionality

import pytest
from unittest.mock import AsyncMock, patch
from autogen_core import MessageContext, AgentId, CancellationToken
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import TextMessage

from src.agents.system3 import (
    CasesResponse,
    PolicyJudgeResponse,
    System3,
    TaskAssignmentResponse,
    TasksAssignResponse,
    TasksCreateResponse,
)
from src.agents.messages import (
    CapabilityGapMessage,
    InitiativeAssignMessage,
    PolicySuggestionMessage,
    TaskReviewMessage,
)
from src.enums import PolicyJudgement, Status, SystemType


class TestSystem3Basic:
    """Test System3 basic functionality."""

    def test_system3_creation(self):
        """Test System3 creation with proper AutoGen format."""
        system3 = System3("System3/controller1")
        assert system3 is not None
        assert system3.agent_id.type == "System3"
        assert system3.agent_id.key == "controller1"

    def test_system3_creation_from_key(self):
        """Test System3 creation from key-only id."""
        system3 = System3("root")
        assert system3 is not None
        assert system3.agent_id.type == "System3"
        assert system3.agent_id.key == "root"

    def test_system3_identity_and_responsibilities(self):
        """Test System3 identity and responsibility prompts."""
        system3 = System3("System3/controller1")

        # Check identity prompt
        assert "operational control agent" in system3.identity_prompt
        assert "big picture" in system3.identity_prompt

        # Check responsibility prompts
        assert len(system3.responsibility_prompts) == 3
        assert "Operational Delegation" in system3.responsibility_prompts[0]
        assert "Project Planning" in system3.responsibility_prompts[1]
        assert "Task Review" in system3.responsibility_prompts[2]

    def test_system3_handler_exists(self):
        """Test that System3 has the required message handlers."""
        system3 = System3("System3/controller1")
        assert hasattr(system3, "handle_initiative_assign_message")
        assert callable(getattr(system3, "handle_initiative_assign_message"))

    def test_system3_registers_capability_gap_tool(self):
        """System3 must expose capability_gap_tool referenced in its prompts."""
        system3 = System3("System3/controller1")
        tool_names = [tool.name for tool in system3.tools]
        assert "capability_gap_tool" in tool_names


class TestSystem3Messages:
    """Test System3 message handling."""

    def test_initiative_assign_message_creation(self):
        """Test InitiativeAssignMessage creation."""
        message = InitiativeAssignMessage(
            initiative_id=1, source="System4/strategy1", content="Start initiative 1."
        )
        assert message.initiative_id == 1
        assert message.source == "System4/strategy1"
        assert message.content == "Start initiative 1."


class TestSystem3StructuredResponses:
    """Test System3 structured response types."""

    def test_tasks_create_response(self):
        """Test TasksCreateResponse structure."""
        from src.agents.system3 import TaskCreateResponse

        task1 = TaskCreateResponse(name="Task 1", content="Content 1")
        task2 = TaskCreateResponse(name="Task 2", content="Content 2")

        response = TasksCreateResponse(tasks=[task1, task2])
        assert len(response.tasks) == 2
        assert response.tasks[0].name == "Task 1"
        assert response.tasks[1].name == "Task 2"

    def test_tasks_assign_response(self):
        """Test TasksAssignResponse structure."""
        response = TasksAssignResponse(
            assignments=[
                TaskAssignmentResponse(system_id=1, task_id=101),
                TaskAssignmentResponse(system_id=2, task_id=102),
            ]
        )
        assert len(response.assignments) == 2
        assert response.assignments[0].system_id == 1
        assert response.assignments[0].task_id == 101
        assert response.assignments[1].system_id == 2
        assert response.assignments[1].task_id == 102


class TestSystem3Integration:
    """Test System3 integration scenarios."""

    def test_system3_with_trace_context(self):
        """Test System3 with trace context."""
        trace_context = {"trace_id": "abc123", "span_id": "def456"}
        system3 = System3("System3/controller1", trace_context=trace_context)
        assert system3.trace_context == trace_context


@pytest.mark.asyncio
async def test_system3_current_issue():
    """Test System3 handles missing initiatives without touching the DB."""
    system3 = System3("System3/controller1")

    # Create initiative message (this is what System4 would send)
    initiative_message = InitiativeAssignMessage(
        initiative_id=1, source="System4/strategy1", content="Start initiative 1."
    )

    from autogen_core import CancellationToken

    context = MessageContext(
        sender=AgentId.from_str("System4/strategy1"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test_msg_1",
    )

    # Mock DB access so the test does not require real tables.
    with patch(
        "src.cyberagent.services.initiatives._get_initiative", return_value=None
    ):
        with pytest.raises(ValueError, match="Initiative with id 1 not found"):
            await system3.handle_initiative_assign_message(
                message=initiative_message,
                ctx=context,
            )  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_system3_basic_smoke_test():
    """Basic smoke test for System3."""
    # Test creation
    system3 = System3("System3/controller1")
    assert system3 is not None
    print(f"System3 created: {system3.name}")
    print(f"System3 agent ID: {system3.agent_id}")

    # Test message creation
    initiative_message = InitiativeAssignMessage(
        initiative_id=1, source="System4/strategy1", content="Start initiative 1."
    )
    assert initiative_message.initiative_id == 1
    print(
        f"Initiative message created for initiative {initiative_message.initiative_id}"
    )

    # Test responsibility prompts
    for i, prompt in enumerate(system3.responsibility_prompts, 1):
        print(f"Responsibility {i}: {prompt}")

    print("System3 basic functionality test completed successfully!")


if __name__ == "__main__":
    # Run basic test
    import asyncio

    asyncio.run(test_system3_basic_smoke_test())


@pytest.mark.asyncio
async def test_system3_task_review_escalates_when_no_policies():
    """No-policy task reviews should escalate to System5 instead of crashing."""
    system3 = System3("System3/controller1")
    system3._publish_message_to_agent = AsyncMock()

    message = TaskReviewMessage(
        task_id=42,
        assignee_agent_id_str="System1/root",
        source="System1/root",
        content="Task result",
    )
    context = MessageContext(
        sender=AgentId.from_str("System1/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="task_review_no_policy",
    )

    class DummyTask:
        id = 42
        assignee = "System1/root"
        status = Status.COMPLETED

    class DummySystem5:
        def get_agent_id(self):
            return AgentId.from_str("System5/root")

    with (
        patch("src.cyberagent.services.tasks._get_task", return_value=DummyTask()),
        patch(
            "src.cyberagent.services.policies._get_system_policy_prompts",
            return_value=[],
        ),
        patch.object(system3, "_get_systems_by_type", return_value=[DummySystem5()]),
    ):
        await system3.handle_task_review_message(message, context)  # type: ignore[arg-type]

    system3._publish_message_to_agent.assert_awaited_once()
    await_args = system3._publish_message_to_agent.await_args
    assert await_args is not None
    published_message = await_args.args[0]
    assert isinstance(published_message, PolicySuggestionMessage)
    assert published_message.policy_id is None
    assert published_message.task_id == 42


@pytest.mark.asyncio
async def test_system3_task_review_processes_blocked_tasks() -> None:
    system3 = System3("System3/controller1")
    system3._publish_message_to_agent = AsyncMock()
    mocked_run = AsyncMock()

    message = TaskReviewMessage(
        task_id=42,
        assignee_agent_id_str="System1/root",
        source="System1/root",
        content="Task result",
    )
    context = MessageContext(
        sender=AgentId.from_str("System1/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="task_review_blocked",
    )

    class DummyTask:
        id = 42
        assignee = "System1/root"
        status = Status.BLOCKED

    class DummySystem5:
        def get_agent_id(self):
            return AgentId.from_str("System5/root")

    mocked_run.return_value = object()

    with (
        patch("src.cyberagent.services.tasks._get_task", return_value=DummyTask()),
        patch(
            "src.cyberagent.services.policies._get_system_policy_prompts",
            return_value=["Policy #1"],
        ),
        patch.object(system3, "_get_systems_by_type", return_value=[DummySystem5()]),
        patch.object(
            system3,
            "_get_structured_message",
            return_value=CasesResponse(
                cases=[
                    PolicyJudgeResponse(
                        policy_id=1,
                        judgement=PolicyJudgement.VIOLATED,
                        reasoning="blocked for valid reason",
                    )
                ]
            ),
        ),
        patch.object(system3, "run", mocked_run),
    ):
        await system3.handle_task_review_message(message, context)  # type: ignore[arg-type]

    assert mocked_run.await_count == 1
    assert system3._publish_message_to_agent.await_count == 1


@pytest.mark.asyncio
async def test_system3_task_review_processes_blocked_tasks_with_prefixed_status() -> (
    None
):
    system3 = System3("System3/controller1")
    system3._publish_message_to_agent = AsyncMock()
    mocked_run = AsyncMock()

    message = TaskReviewMessage(
        task_id=42,
        assignee_agent_id_str="System1/root",
        source="System1/root",
        content="Task result",
    )
    context = MessageContext(
        sender=AgentId.from_str("System1/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="task_review_blocked_prefixed",
    )

    class DummyTask:
        id = 42
        assignee = "System1/root"
        status = "Status.BLOCKED"

    class DummySystem5:
        def get_agent_id(self):
            return AgentId.from_str("System5/root")

    mocked_run.return_value = object()

    with (
        patch("src.cyberagent.services.tasks._get_task", return_value=DummyTask()),
        patch(
            "src.cyberagent.services.policies._get_system_policy_prompts",
            return_value=["Policy #1"],
        ),
        patch.object(system3, "_get_systems_by_type", return_value=[DummySystem5()]),
        patch.object(
            system3,
            "_get_structured_message",
            return_value=CasesResponse(
                cases=[
                    PolicyJudgeResponse(
                        policy_id=1,
                        judgement=PolicyJudgement.VIOLATED,
                        reasoning="blocked for valid reason",
                    )
                ]
            ),
        ),
        patch.object(system3, "run", mocked_run),
    ):
        await system3.handle_task_review_message(message, context)  # type: ignore[arg-type]

    assert mocked_run.await_count == 1


@pytest.mark.asyncio
async def test_system3_task_review_skips_non_review_eligible_tasks() -> None:
    system3 = System3("System3/controller1")
    system3._publish_message_to_agent = AsyncMock()
    mocked_run = AsyncMock()

    message = TaskReviewMessage(
        task_id=42,
        assignee_agent_id_str="System1/root",
        source="System1/root",
        content="Task result",
    )
    context = MessageContext(
        sender=AgentId.from_str("System1/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="task_review_pending",
    )

    class DummyTask:
        id = 42
        assignee = "System1/root"
        status = Status.PENDING

    with (
        patch("src.cyberagent.services.tasks._get_task", return_value=DummyTask()),
        patch.object(system3, "run", mocked_run),
    ):
        await system3.handle_task_review_message(message, context)  # type: ignore[arg-type]

    assert mocked_run.await_count == 0
    assert system3._publish_message_to_agent.await_count == 0


@pytest.mark.asyncio
async def test_system3_task_review_falls_back_on_json_validate_failure():
    """System3 should request structured review; fallback is handled in SystemBase."""
    system3 = System3("System3/controller1")
    system3._publish_message_to_agent = AsyncMock()

    message = TaskReviewMessage(
        task_id=42,
        assignee_agent_id_str="System1/root",
        source="System1/root",
        content="Task result",
    )
    context = MessageContext(
        sender=AgentId.from_str("System1/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="task_review_fallback",
    )

    class DummyTask:
        id = 42
        assignee = "System1/root"
        status = Status.COMPLETED

    class DummySystem5:
        def get_agent_id(self):
            return AgentId.from_str("System5/root")

    fallback_json = (
        '{"cases":[{"policy_id":1,"judgement":"Satisfied","reasoning":"ok"}]}'
    )
    mocked_run = AsyncMock(
        return_value=TaskResult(
            messages=[TextMessage(content=fallback_json, source="System3")]
        )
    )

    with (
        patch("src.cyberagent.services.tasks._get_task", return_value=DummyTask()),
        patch(
            "src.cyberagent.services.policies._get_system_policy_prompts",
            return_value=[
                '{"id":1,"content":"Approve when actionable","system_id":1,"team_id":1,"name":"task_completion_criteria"}'
            ],
        ),
        patch.object(system3, "_get_systems_by_type", return_value=[DummySystem5()]),
        patch.object(system3, "run", mocked_run),
        patch("src.cyberagent.services.tasks.finalize_task_review") as finalize_review,
    ):
        await system3.handle_task_review_message(message, context)  # type: ignore[arg-type]

    assert mocked_run.await_count == 1
    first_call = mocked_run.await_args_list[0]
    assert first_call.args[3].__name__ == "CasesResponse"
    assert first_call.kwargs["include_memory_context"] is False
    finalize_review.assert_called_once()


@pytest.mark.asyncio
async def test_system3_task_review_persists_case_judgements() -> None:
    system3 = System3("System3/controller1")
    system3._publish_message_to_agent = AsyncMock()

    message = TaskReviewMessage(
        task_id=42,
        assignee_agent_id_str="System1/root",
        source="System1/root",
        content="Task result",
    )
    context = MessageContext(
        sender=AgentId.from_str("System1/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="task_review_store_cases",
    )

    class DummyTask:
        id = 42
        assignee = "System1/root"
        status = Status.COMPLETED

    class DummySystem5:
        def get_agent_id(self):
            return AgentId.from_str("System5/root")

    cases_json = (
        '{"cases":[{"policy_id":1,"judgement":"Satisfied","reasoning":"ok"},'
        '{"policy_id":2,"judgement":"Violated","reasoning":"bad"}]}'
    )

    with (
        patch("src.cyberagent.services.tasks._get_task", return_value=DummyTask()),
        patch(
            "src.cyberagent.services.policies._get_system_policy_prompts",
            return_value=[
                '{"id":1,"content":"p1","system_id":1,"team_id":1,"name":"n1"}',
                '{"id":2,"content":"p2","system_id":1,"team_id":1,"name":"n2"}',
            ],
        ),
        patch.object(system3, "_get_systems_by_type", return_value=[DummySystem5()]),
        patch.object(
            system3,
            "run",
            AsyncMock(
                return_value=TaskResult(
                    messages=[TextMessage(content=cases_json, source="System3")]
                )
            ),
        ),
        patch("src.cyberagent.services.tasks.finalize_task_review") as finalize_review,
    ):
        await system3.handle_task_review_message(message, context)  # type: ignore[arg-type]

    finalize_review.assert_called_once()
    stored_cases = finalize_review.call_args.args[1]
    assert stored_cases == [
        {"policy_id": 1, "judgement": "Satisfied", "reasoning": "ok"},
        {"policy_id": 2, "judgement": "Violated", "reasoning": "bad"},
    ]


@pytest.mark.asyncio
async def test_system3_task_review_persists_failure_marker_and_escalates_on_parse_failure():
    system3 = System3("System3/controller1")
    system3._publish_message_to_agent = AsyncMock()

    message = TaskReviewMessage(
        task_id=42,
        assignee_agent_id_str="System1/root",
        source="System1/root",
        content="Task result",
    )
    context = MessageContext(
        sender=AgentId.from_str("System1/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="task_review_error_route",
    )

    class DummyTask:
        id = 42
        assignee = "System1/root"
        status = Status.COMPLETED

    class DummySystem5:
        def get_agent_id(self):
            return AgentId.from_str("System5/root")

    mocked_run = AsyncMock(
        side_effect=[
            RuntimeError("json_validate_failed: Failed to generate JSON"),
            TaskResult(messages=[TextMessage(content="not-json", source="System3")]),
        ]
    )

    with (
        patch("src.cyberagent.services.tasks._get_task", return_value=DummyTask()),
        patch(
            "src.cyberagent.services.policies._get_system_policy_prompts",
            return_value=['{"id":1,"content":"p1","system_id":1,"team_id":1}'],
        ),
        patch.object(system3, "_get_systems_by_type", return_value=[DummySystem5()]),
        patch.object(system3, "run", mocked_run),
        patch("src.cyberagent.services.tasks.set_task_case_judgement") as set_cases,
        patch("src.cyberagent.services.tasks.finalize_task_review") as finalize_review,
    ):
        await system3.handle_task_review_message(message, context)  # type: ignore[arg-type]

    finalize_review.assert_not_called()
    set_cases.assert_called_once()
    stored_cases = set_cases.call_args.args[1]
    assert len(stored_cases) == 1
    assert stored_cases[0]["kind"] == "review_parse_failure"
    assert stored_cases[0]["phase"] == "fallback"
    assert stored_cases[0]["retry_count"] == 1
    system3._publish_message_to_agent.assert_awaited_once()
    await_args = system3._publish_message_to_agent.await_args
    assert await_args is not None
    published_message = await_args.args[0]
    assert isinstance(published_message, PolicySuggestionMessage)
    assert published_message.task_id == 42
    assert "retry 1/" in published_message.content.lower()


@pytest.mark.asyncio
async def test_system3_task_review_parse_failure_marks_retry_exhausted_after_max() -> (
    None
):
    system3 = System3("System3/controller1")
    system3._publish_message_to_agent = AsyncMock()

    message = TaskReviewMessage(
        task_id=42,
        assignee_agent_id_str="System1/root",
        source="System1/root",
        content="Task result",
    )
    context = MessageContext(
        sender=AgentId.from_str("System1/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="task_review_error_route_max_retry",
    )

    class DummyTask:
        id = 42
        assignee = "System1/root"
        status = Status.COMPLETED
        case_judgement = (
            '[{"kind":"review_parse_failure","phase":"fallback","retry_count":1}]'
        )

    class DummySystem5:
        def get_agent_id(self):
            return AgentId.from_str("System5/root")

    mocked_run = AsyncMock(
        side_effect=[
            RuntimeError("json_validate_failed: Failed to generate JSON"),
            TaskResult(messages=[TextMessage(content="not-json", source="System3")]),
        ]
    )

    with (
        patch("src.cyberagent.services.tasks._get_task", return_value=DummyTask()),
        patch(
            "src.cyberagent.services.policies._get_system_policy_prompts",
            return_value=['{"id":1,"content":"p1","system_id":1,"team_id":1}'],
        ),
        patch.object(system3, "_get_systems_by_type", return_value=[DummySystem5()]),
        patch.object(system3, "run", mocked_run),
        patch("src.cyberagent.services.tasks.set_task_case_judgement") as set_cases,
        patch("src.cyberagent.services.tasks.finalize_task_review") as finalize_review,
    ):
        await system3.handle_task_review_message(message, context)  # type: ignore[arg-type]

    finalize_review.assert_not_called()
    set_cases.assert_called_once()
    stored_cases = set_cases.call_args.args[1]
    assert stored_cases[0]["retry_count"] == 2
    assert stored_cases[0]["retry_exhausted"] is True
    await_args = system3._publish_message_to_agent.await_args
    assert await_args is not None
    published_message = await_args.args[0]
    assert isinstance(published_message, PolicySuggestionMessage)
    assert "manual intervention" in published_message.content.lower()


@pytest.mark.asyncio
async def test_system3_capability_gap_retries_tool_args_json_error_without_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system3 = System3("System3/controller1")
    system3._publish_message_to_agent = AsyncMock()

    async def fake_set_system_prompt(
        _prompts: list[str], _memory_context: list[str] | None = None
    ) -> None:
        return None

    monkeypatch.setattr(system3, "_set_system_prompt", fake_set_system_prompt)
    monkeypatch.setattr(system3, "_build_memory_context", lambda *_args: [])
    monkeypatch.setattr(
        "src.agents.system_base.mark_team_active", lambda *_args, **_kwargs: None
    )

    class DummyTask:
        assignee = "System1/root"

    monkeypatch.setattr(
        "src.cyberagent.services.tasks._get_task", lambda _task_id: DummyTask()
    )
    monkeypatch.setattr(system3, "_was_tool_called", lambda *_args, **_kwargs: True)

    system3._agent.run = AsyncMock(
        side_effect=[
            RuntimeError(
                "Error code: 400 - {'error': {'message': "
                "'Failed to parse tool call arguments as JSON', "
                "'type': 'invalid_request_error', 'code': 'tool_use_failed'}}"
            ),
            TaskResult(messages=[TextMessage(content="ok", source="System3/root")]),
        ]
    )

    message = CapabilityGapMessage(
        task_id=7,
        content="Need different capability",
        assignee_agent_id_str="System1/root",
        source="System1/root",
    )
    context = MessageContext(
        sender=AgentId.from_str("System1/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="capability_gap_tool_args_retry_test",
    )

    await system3.handle_capability_gap_message(message, context)  # type: ignore[arg-type]

    assert system3._agent.run.await_count == 2
    system3._publish_message_to_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_system3_capability_gap_prompt_includes_exact_task_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system3 = System3("System3/controller1")

    class DummyTask:
        assignee = "System1/root"
        id = 7
        name = "Define workshop objectives and key questions"
        content = "Outline workshop goals and key questions."

    monkeypatch.setattr(
        "src.cyberagent.services.tasks._get_task", lambda _task_id: DummyTask()
    )

    captured_prompts: list[str] = []

    async def _fake_run(
        _messages,
        _ctx,
        message_specific_prompts=None,
        output_content_type=None,
        **_kwargs,
    ):
        _ = output_content_type
        if message_specific_prompts:
            captured_prompts.extend(message_specific_prompts)
        return TaskResult(messages=[TextMessage(content="ok", source="System3/root")])

    monkeypatch.setattr(system3, "run", _fake_run)
    monkeypatch.setattr(system3, "_was_tool_called", lambda *_args, **_kwargs: True)

    message = CapabilityGapMessage(
        task_id=7,
        content="Ambiguous or non-JSON task execution output.",
        assignee_agent_id_str="System1/root",
        source="System1/root",
    )
    context = MessageContext(
        sender=AgentId.from_str("System1/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="capability-gap-prompt-context",
    )

    await system3.handle_capability_gap_message(message, context)  # type: ignore[arg-type]

    joined = "\n".join(captured_prompts)
    assert "The affected task_id is 7." in joined
    assert "never use 0 or placeholders" in joined
    assert "Define workshop objectives and key questions" in joined


@pytest.mark.asyncio
async def test_system3_blocked_task_with_insufficient_info_requests_system4_research():
    """When a task is blocked due to insufficient information, System3 should request System4 research."""
    system3 = System3("System3/controller1")
    system3._publish_message_to_agent = AsyncMock()

    message = TaskReviewMessage(
        task_id=33,
        assignee_agent_id_str="System1/root",
        source="System1/root",
        content="Review blocked task.",
    )
    context = MessageContext(
        sender=AgentId.from_str("System1/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="task_review_blocked_insufficient_info",
    )

    class DummyTask:
        id = 33
        assignee = "System1/root"
        status = Status.BLOCKED
        name = "Collect user identity and disambiguation links"
        content = "Gather user name and confirm public profile links"
        reasoning = "Insufficient information: No user identity or disambiguation links are available to retrieve."

    class DummySystem4:
        def get_agent_id(self):
            return AgentId.from_str("System4/root")

    class DummySystem5:
        def get_agent_id(self):
            return AgentId.from_str("System5/root")

    with (
        patch("src.cyberagent.services.tasks._get_task", return_value=DummyTask()),
        patch.object(
            system3,
            "_get_systems_by_type",
            side_effect=lambda system_type: [DummySystem4()]
            if system_type == SystemType.INTELLIGENCE
            else [DummySystem5()],
        ),
        patch(
            "src.cyberagent.services.policies._get_system_policy_prompts",
            return_value=["Policy #1"],
        ),
        patch.object(system3, "run", new=AsyncMock()),
    ):
        await system3.handle_task_review_message(message, context)  # type: ignore[arg-type]

    # First message should be a research request to System4.
    assert system3._publish_message_to_agent.await_count >= 1
    published = [call.args[0] for call in system3._publish_message_to_agent.await_args_list]
    from src.agents.messages import ResearchRequestMessage

    assert any(isinstance(msg, ResearchRequestMessage) for msg in published)
