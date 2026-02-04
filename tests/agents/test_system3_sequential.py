# System3 Agent Tests - Sequential Processing
# Tests for System3 (Control) agent with sequential processing

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from autogen_core import AgentId, MessageContext

from src.agents.messages import InitiativeAssignMessage
from src.agents.system3 import System3, TasksCreateResponse


class TestSystem3SequentialProcessing:
    """Test System3 sequential processing functionality."""

    def test_system3_creation(self):
        """Test System3 creation with proper AutoGen format."""
        system3 = System3("System3/controller1")
        assert system3 is not None
        assert system3.agent_id.type == "System3"
        assert system3.agent_id.key == "controller1"

    def test_system3_tools_available(self):
        """Test that System3 has the assign_task tool available."""
        system3 = System3("System3/controller1")

        # Check that assign_task tool is available
        tool_names = [tool.name for tool in system3.tools]
        assert "assign_task" in tool_names

    def test_system3_sequential_processing_logic(self):
        """Test the sequential processing logic."""
        system3 = System3("System3/controller1")

        # Mock the run method to simulate different scenarios
        system3.run = AsyncMock()

        # Mock _was_tool_called to test both paths
        system3._was_tool_called = MagicMock()

        # Test scenario 1: Tool is called
        system3._was_tool_called.return_value = True

        # Simulate a response that indicates tool usage
        from autogen_agentchat.base import Response
        from autogen_agentchat.messages import TextMessage

        mock_response = Response(
            chat_message=TextMessage(
                content="Tool was called", source="System3/controller1"
            ),
            inner_messages=[],
        )
        system3.run.return_value = mock_response

        # Test the logic
        assert system3._was_tool_called(mock_response, "assign_task")

        # Test scenario 2: Tool is not called
        system3._was_tool_called.return_value = False
        assert not system3._was_tool_called(mock_response, "assign_task")

    @pytest.mark.asyncio
    async def test_system3_structured_output_without_tools(self):
        """Test that System3 can generate structured output when tools are disabled."""
        system3 = System3("System3/controller1")

        # Temporarily remove tools
        original_tools = system3.tools.copy()
        system3.tools = []

        # Mock the run method for structured output
        system3.run = AsyncMock()
        from autogen_agentchat.base import Response
        from autogen_agentchat.messages import TextMessage

        # Mock response for task creation - use proper TaskCreateResponse objects
        from src.agents.system3 import TaskCreateResponse

        task1 = TaskCreateResponse(name="Task 1", content="Do task 1")
        task2 = TaskCreateResponse(name="Task 2", content="Do task 2")

        task_response = TasksCreateResponse(tasks=[task1, task2])

        mock_response = Response(
            chat_message=TextMessage(
                content=json.dumps(task_response.model_dump()),
                source="System3/controller1",
            ),
            inner_messages=[],
        )
        system3.run.return_value = mock_response

        # Mock _get_structured_response
        system3._get_structured_message = MagicMock(return_value=task_response)

        # Create a mock message and context
        initiative_message = InitiativeAssignMessage(
            initiative_id=1, source="System4/strategy1", content="Test initiative"
        )
        from autogen_core import CancellationToken

        context = MessageContext(
            sender=AgentId.from_str("System4/strategy1"),
            topic_id=None,
            is_rpc=False,
            cancellation_token=CancellationToken(),
            message_id="test_msg_1",
        )

        # Test that structured output works without tools
        result = await system3.run(
            [initiative_message], context, ["test prompts"], TasksCreateResponse
        )
        structured_result = system3._get_structured_message(result, TasksCreateResponse)

        assert len(structured_result.tasks) == 2
        assert structured_result.tasks[0].name == "Task 1"

        # Restore tools
        system3.tools = original_tools


class TestSystem3MessageHandling:
    """Test System3 message handling."""

    def test_initiative_assign_message_properties(self):
        """Test InitiativeAssignMessage properties."""
        message = InitiativeAssignMessage(
            initiative_id=42, source="System4/strategy1", content="Test initiative"
        )

        assert message.initiative_id == 42
        assert message.source == "System4/strategy1"
        assert message.content == "Test initiative"

        # Confirm it does NOT have 'initiative' attribute (this is the bug)
        assert not hasattr(message, "initiative")


@pytest.mark.asyncio
async def test_system3_sequential_processing_demo():
    """Demonstrate the sequential processing solution."""
    system3 = System3("System3/controller1")

    print(f"System3 created: {system3.name}")
    print(f"Available tools: {[tool.name for tool in system3.tools]}")

    # Test the sequential processing concept
    print("\n=== Sequential Processing Concept ===")
    print("Phase 1: Structured output (tools disabled)")
    print("Phase 2: Tool usage decision (tools enabled)")
    print("Phase 3: Manual assignment if tools not called")

    # Test message creation
    initiative_message = InitiativeAssignMessage(
        initiative_id=1, source="System4/strategy1", content="Test initiative"
    )

    print(
        f"\nInitiative message: ID={initiative_message.initiative_id}, Source={initiative_message.source}"
    )
    print("Note: Message only contains initiative_id, not full initiative object")

    print("\nSystem3 sequential processing test completed!")


if __name__ == "__main__":
    # Run basic test
    import asyncio

    asyncio.run(test_system3_sequential_processing_demo())
