# System3 Agent Tests
# Tests for System3 (Control) agent functionality

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from autogen_core import MessageContext, AgentId

from src.agents.system3 import System3, TasksCreateResponse, TasksAssignResponse
from src.agents.messages import InitiativeAssignMessage
from src.enums import Status


class TestSystem3Basic:
    """Test System3 basic functionality."""

    def test_system3_creation(self):
        """Test System3 creation with proper AutoGen format."""
        system3 = System3("System3/controller1")
        assert system3 is not None
        assert system3.agent_id.type == "System3"
        assert system3.agent_id.key == "controller1"

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
        response = TasksAssignResponse(assignments=[(1, 101), (2, 102)])
        assert len(response.assignments) == 2
        assert response.assignments[0] == (1, 101)
        assert response.assignments[1] == (2, 102)


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
    with patch("src.models.initiative.get_initiative", return_value=None):
        with pytest.raises(ValueError, match="Initiative with id 1 not found"):
            await system3.handle_initiative_assign_message(initiative_message, context)


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
