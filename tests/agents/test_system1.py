# System1 Agent Tests
# Tests for System1 (Operations) agent functionality

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from autogen_core import MessageContext, AgentId

from src.agents.system1 import System1
from src.agents.messages import TaskAssignMessage, TaskReviewMessage
from src.enums import Status


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
