# System3 Agent Tests
# Tests for System3 (Control) agent functionality

import pytest
from unittest.mock import AsyncMock, patch
from autogen_core import MessageContext, AgentId, CancellationToken
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import TextMessage

from src.agents.system3 import (
    System3,
    TaskAssignmentResponse,
    TasksAssignResponse,
    TasksCreateResponse,
)
from src.agents.messages import (
    InitiativeAssignMessage,
    PolicySuggestionMessage,
    TaskReviewMessage,
)


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
async def test_system3_task_review_falls_back_on_json_validate_failure():
    """Structured review should retry without strict schema when provider rejects JSON generation."""
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

    class DummySystem5:
        def get_agent_id(self):
            return AgentId.from_str("System5/root")

    fallback_json = (
        '{"cases":[{"policy_id":1,"judgement":"Satisfied","reasoning":"ok"}]}'
    )
    mocked_run = AsyncMock(
        side_effect=[
            RuntimeError("json_validate_failed: Failed to generate JSON"),
            TaskResult(messages=[TextMessage(content=fallback_json, source="System3")]),
        ]
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
        patch("src.cyberagent.services.tasks.approve_task") as approve_task,
        patch("src.cyberagent.services.tasks.set_task_case_judgement"),
    ):
        await system3.handle_task_review_message(message, context)  # type: ignore[arg-type]

    assert mocked_run.await_count == 2
    first_call = mocked_run.await_args_list[0]
    second_call = mocked_run.await_args_list[1]
    assert first_call.args[3].__name__ == "CasesResponse"
    assert first_call.kwargs["include_memory_context"] is False
    assert second_call.args[3] is None
    assert second_call.kwargs["include_memory_context"] is False
    approve_task.assert_called_once()


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
        patch("src.cyberagent.services.tasks.approve_task") as approve_task,
        patch("src.cyberagent.services.tasks.set_task_case_judgement") as set_judgement,
    ):
        await system3.handle_task_review_message(message, context)  # type: ignore[arg-type]

    approve_task.assert_called_once()
    set_judgement.assert_called_once()
    stored_cases = set_judgement.call_args.args[1]
    assert stored_cases == [
        {"policy_id": 1, "judgement": "Satisfied", "reasoning": "ok"},
        {"policy_id": 2, "judgement": "Violated", "reasoning": "bad"},
    ]
