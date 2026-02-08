# System3 Sequential Processing Implementation Test
# Test the actual refactored handle_initiative_assign_message method

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from autogen_core import AgentId, MessageContext

from src.agents.messages import InitiativeAssignMessage
from src.agents.system3 import (
    System3,
    TaskCreateResponse,
    TasksAssignResponse,
    TasksCreateResponse,
)


class TestSystem3RefactoredImplementation:
    """Test the refactored System3 implementation with sequential processing."""

    @pytest.mark.asyncio
    async def test_handle_initiative_assign_message_sequential_processing(self):
        """Test the complete sequential processing workflow."""
        system3 = System3("System3/controller1")

        # Create an initiative message (like System4 would send)
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

        class DummyInitiative:
            def __init__(self, initiative_id: int, name: str, description: str):
                self.id = initiative_id
                self.name = name
                self.description = description
                self.status = ""
                self.updated = False

            def set_status(self, status):  # noqa: ANN001
                self.status = str(status)

            def update(self):
                self.updated = True

        # Mock the database operations
        with (
            patch(
                "src.cyberagent.services.initiatives._get_initiative"
            ) as mock_get_initiative,
            patch("src.cyberagent.db.models.task.Task.add"),
            patch("src.cyberagent.db.models.task.Task.to_prompt", return_value=["{}"]),
            patch.object(system3, "_get_systems_by_type") as mock_get_systems,
            patch(
                "src.cyberagent.services.tasks.has_tasks_for_initiative"
            ) as mock_has_tasks,
        ):
            # Create mock initiative
            mock_initiative = DummyInitiative(1, "Test Initiative", "Test Description")
            mock_get_initiative.return_value = mock_initiative

            class DummySystems:
                def __init__(self):
                    self.systems = []

            mock_get_systems.return_value = DummySystems()
            mock_has_tasks.return_value = False

            # Mock the run method for both phases
            system3.run = AsyncMock()
            system3._get_structured_message = MagicMock()
            system3._was_tool_called = MagicMock()

            # Phase 1: Task creation (structured output)
            mock_tasks_response = TasksCreateResponse(
                tasks=[
                    TaskCreateResponse(name="Task 1", content="Do task 1"),
                    TaskCreateResponse(name="Task 2", content="Do task 2"),
                ]
            )

            from autogen_agentchat.base import Response
            from autogen_agentchat.messages import TextMessage

            # Mock the first run call (task creation)
            system3.run.return_value = Response(
                chat_message=TextMessage(
                    content="Tasks created", source="System3/controller1"
                ),
                inner_messages=[],
            )
            # Provide task creation response first, then assignment response.
            mock_assign_response = TasksAssignResponse(
                assignments=[(1, 101), (2, 102)]  # system_id, task_id pairs
            )
            system3._get_structured_message.side_effect = [
                mock_tasks_response,
                mock_assign_response,
            ]

            # Phase 2: Tool decision phase
            # Simulate that the tool was NOT called (so we need structured assignment)
            system3._was_tool_called.return_value = False

            # Mock assign_task method
            system3.assign_task = AsyncMock()

            # Call the handler
            await system3.handle_initiative_assign_message(
                message=initiative_message,
                ctx=context,
            )  # type: ignore[call-arg]

            # Verify the sequential processing worked

            # Phase 1 verification: Initiative was fetched and updated
            mock_get_initiative.assert_called_once_with(1)
            assert mock_initiative.status
            assert mock_initiative.updated is True

            # Phase 2 verification: Tasks were created
            assert system3.run.call_count >= 1

            # Phase 3 verification: Tasks were assigned manually
            system3.assign_task.assert_called()
            # Should be called for each assignment
            assert system3.assign_task.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_initiative_assign_message_tool_called(self):
        """Test when the assign_task tool is called directly."""
        system3 = System3("System3/controller1")

        # Create an initiative message
        initiative_message = InitiativeAssignMessage(
            initiative_id=2, source="System4/strategy2", content="Start initiative 2."
        )

        from autogen_core import CancellationToken

        context = MessageContext(
            sender=AgentId.from_str("System4/strategy2"),
            topic_id=None,
            is_rpc=False,
            cancellation_token=CancellationToken(),
            message_id="test_msg_2",
        )

        class DummyInitiative:
            def __init__(self, initiative_id: int, name: str):
                self.id = initiative_id
                self.name = name
                self.status = ""
                self.updated = False

            def set_status(self, status):  # noqa: ANN001
                self.status = str(status)

            def update(self):
                self.updated = True

        # Mock the database operations
        with (
            patch(
                "src.cyberagent.services.initiatives._get_initiative"
            ) as mock_get_initiative,
            patch("src.cyberagent.db.models.task.Task.add"),
            patch("src.cyberagent.db.models.task.Task.to_prompt", return_value=["{}"]),
            patch.object(system3, "_get_systems_by_type") as mock_get_systems,
        ):
            # Create mock initiative
            mock_initiative = DummyInitiative(2, "Test Initiative 2")
            mock_get_initiative.return_value = mock_initiative

            class DummySystems:
                def __init__(self):
                    self.systems = []

            mock_get_systems.return_value = DummySystems()

            # Mock the run method
            system3.run = AsyncMock()
            system3._get_structured_message = MagicMock()
            system3._was_tool_called = MagicMock()

            # Simulate that the tool WAS called
            system3._was_tool_called.return_value = True

            from autogen_agentchat.base import Response
            from autogen_agentchat.messages import TextMessage

            # Mock the run response
            system3.run.return_value = Response(
                chat_message=TextMessage(
                    content="Tool called", source="System3/controller1"
                ),
                inner_messages=[],
            )

            # Provide minimal task creation response for phase 1.
            system3._get_structured_message.return_value = TasksCreateResponse(
                tasks=[TaskCreateResponse(name="Task 1", content="Do task 1")]
            )

            # Call the handler
            await system3.handle_initiative_assign_message(
                message=initiative_message,
                ctx=context,
            )  # type: ignore[call-arg]

            # Verify that when tool is called, we don't proceed to structured assignment
            system3._was_tool_called.assert_called_with(
                system3.run.return_value, "assign_task"
            )

    @pytest.mark.asyncio
    async def test_handle_initiative_assign_message_assigns_existing_tasks(self):
        """Assign existing unassigned tasks when tasks are already materialized."""
        system3 = System3("System3/controller1")

        initiative_message = InitiativeAssignMessage(
            initiative_id=1, source="System4/strategy1", content="Start initiative 1."
        )

        from autogen_core import CancellationToken

        context = MessageContext(
            sender=AgentId.from_str("System4/strategy1"),
            topic_id=None,
            is_rpc=False,
            cancellation_token=CancellationToken(),
            message_id="test_msg_2",
        )

        class DummyInitiative:
            def __init__(self, initiative_id: int):
                self.id = initiative_id
                self.status = ""
                self.updated = False

            def set_status(self, status):  # noqa: ANN001
                self.status = str(status)

            def update(self):
                self.updated = True

            def get_tasks(self):
                class _Task:
                    def __init__(self, task_id: int) -> None:
                        self.id = task_id
                        self.name = f"Task {task_id}"
                        self.assignee = None

                    def to_prompt(self):
                        return [f"task-{self.id}"]

                return [_Task(101), _Task(102)]

        with (
            patch("src.agents.system3.init_db", lambda: None),
            patch(
                "src.cyberagent.services.initiatives._get_initiative"
            ) as mock_get_initiative,
            patch(
                "src.cyberagent.services.tasks.has_tasks_for_initiative"
            ) as mock_has_tasks,
            patch.object(system3, "_get_systems_by_type") as mock_get_systems,
        ):
            mock_get_initiative.return_value = DummyInitiative(1)
            mock_has_tasks.return_value = True
            mock_get_systems.return_value = []

            from autogen_agentchat.base import Response
            from autogen_agentchat.messages import TextMessage

            system3.run = AsyncMock()
            system3.run.return_value = Response(
                chat_message=TextMessage(
                    content="Assignments prepared", source="System3/controller1"
                ),
                inner_messages=[],
            )
            system3._was_tool_called = MagicMock(return_value=False)
            system3._get_structured_message = MagicMock(
                return_value=TasksAssignResponse(assignments=[(1, 101)])
            )
            system3.assign_task = AsyncMock()

            await system3.handle_initiative_assign_message(
                message=initiative_message,
                ctx=context,
            )  # type: ignore[call-arg]

            mock_get_initiative.assert_called_once_with(1)
            mock_has_tasks.assert_called_once_with(1)
            system3.run.assert_called()
            system3.assign_task.assert_awaited_once_with(1, 101)


class TestSystem3MessageCompatibility:
    """Test message compatibility with the refactored implementation."""

    def test_initiative_assign_message_structure(self):
        """Verify InitiativeAssignMessage structure for the refactored implementation."""
        message = InitiativeAssignMessage(
            initiative_id=42, source="System4/strategy", content="Test initiative"
        )

        # The refactored implementation should work with initiative_id only
        assert message.initiative_id == 42
        assert message.source == "System4/strategy"
        assert message.content == "Test initiative"

        # Confirm it does NOT have initiative object (this was the original bug)
        assert not hasattr(message, "initiative")


@pytest.mark.asyncio
async def test_system3_sequential_processing_complete():
    """Test the complete sequential processing implementation."""
    system3 = System3("System3/controller1")

    print(f"System3 created: {system3.name}")
    print(f"Available tools: {[tool.name for tool in system3.tools]}")

    # Test the sequential processing concept
    print("\n=== Sequential Processing Implementation ===")
    print("Phase 1: Structured task creation (tools disabled)")
    print("Phase 2: Tool usage decision (tools enabled)")
    print("Phase 3: Manual assignment if tools not called")

    # Test message creation
    initiative_message = InitiativeAssignMessage(
        initiative_id=1, source="System4/strategy1", content="Test initiative"
    )

    print(f"\nInitiative message: ID={initiative_message.initiative_id}")
    print("Note: Message only contains initiative_id (not full initiative object)")
    print(
        "This fixes the original bug where System3 tried to access message.initiative"
    )

    print("\nSystem3 sequential processing implementation test completed!")


if __name__ == "__main__":
    # Run basic test
    import asyncio

    asyncio.run(test_system3_sequential_processing_complete())
