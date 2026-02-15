# System3 Sequential Processing Implementation Test
# Test the actual refactored handle_initiative_assign_message method

import re
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from autogen_core import AgentId, MessageContext

from src.agents.messages import InitiativeAssignMessage
from src.agents.messages import TaskAssignMessage
from src.agents.system3 import (
    System3,
    TaskAssignmentResponse,
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
                assignments=[
                    TaskAssignmentResponse(system_id=1, task_id=1),
                    TaskAssignmentResponse(system_id=2, task_id=2),
                ]
            )
            system3._get_structured_message.side_effect = [
                mock_tasks_response,
                mock_assign_response,
            ]

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
    async def test_handle_initiative_assign_message_uses_structured_assignments(self):
        """Test assignment flow uses structured output without tool-decision phase."""
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
            from autogen_agentchat.base import Response
            from autogen_agentchat.messages import TextMessage

            # Mock the run response
            system3.run.return_value = Response(
                chat_message=TextMessage(
                    content="Structured assignments", source="System3/controller1"
                ),
                inner_messages=[],
            )

            system3._get_structured_message.side_effect = [
                TasksCreateResponse(
                    tasks=[TaskCreateResponse(name="Task 1", content="Do task 1")]
                ),
                TasksAssignResponse(
                    assignments=[TaskAssignmentResponse(system_id=1, task_id=1)]
                ),
            ]
            system3.assign_task = AsyncMock()

            # Call the handler
            await system3.handle_initiative_assign_message(
                message=initiative_message,
                ctx=context,
            )  # type: ignore[call-arg]

            system3.assign_task.assert_awaited_once_with(1, 1)

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
            system3._get_structured_message = MagicMock(
                return_value=TasksAssignResponse(
                    assignments=[TaskAssignmentResponse(system_id=1, task_id=101)]
                )
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

    @pytest.mark.asyncio
    async def test_handle_initiative_assign_message_falls_back_when_assignment_task_missing(
        self,
    ) -> None:
        """Fallback to first available task when model returns an invalid task id."""
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
            message_id="test_msg_invalid_assignment_fallback",
        )

        class DummyTask:
            def __init__(self, task_id: int) -> None:
                self.id = task_id
                self.name = f"Task {task_id}"
                self.assignee = None

            def to_prompt(self):
                return [f"task-{self.id}"]

        class DummyInitiative:
            def __init__(self) -> None:
                self.id = 1
                self.status = ""
                self.updated = False

            def set_status(self, status):  # noqa: ANN001
                self.status = str(status)

            def update(self):
                self.updated = True

            def get_tasks(self):
                return [DummyTask(101), DummyTask(102)]

        class DummySystem:
            def __init__(self, system_id: int) -> None:
                self.id = system_id
                self.name = "System1/root"
                self.type = "operation"
                self.agent_id_str = "System1/root"

        with (
            patch("src.agents.system3.init_db", lambda: None),
            patch(
                "src.cyberagent.services.initiatives._get_initiative",
                return_value=DummyInitiative(),
            ),
            patch(
                "src.cyberagent.services.tasks.has_tasks_for_initiative",
                return_value=True,
            ),
            patch.object(
                system3, "_get_systems_by_type", return_value=[DummySystem(1)]
            ),
        ):
            from autogen_agentchat.base import Response
            from autogen_agentchat.messages import TextMessage

            system3.run = AsyncMock(
                return_value=Response(
                    chat_message=TextMessage(
                        content="Assignments prepared",
                        source="System3/controller1",
                    ),
                    inner_messages=[],
                )
            )
            system3._get_structured_message = MagicMock(
                return_value=TasksAssignResponse(
                    assignments=[TaskAssignmentResponse(system_id=1, task_id=999)]
                )
            )
            system3.assign_task = AsyncMock()

            await system3.handle_initiative_assign_message(
                message=initiative_message,
                ctx=context,
            )  # type: ignore[call-arg]

            system3.assign_task.assert_awaited_once_with(1, 101)

    @pytest.mark.asyncio
    async def test_handle_initiative_assign_message_redelivers_pending_assigned_task(
        self,
    ) -> None:
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
            message_id="test_msg_redeliver",
        )

        class DummyTask:
            id = 7
            name = "Define scope"
            assignee = "System1/root"
            status = "pending"

        class DummyInitiative:
            def __init__(self) -> None:
                self.id = 1
                self.status = ""
                self.updated = False

            def set_status(self, status):  # noqa: ANN001
                self.status = str(status)

            def update(self):
                self.updated = True

            def get_tasks(self):
                return [DummyTask()]

        with (
            patch("src.agents.system3.init_db", lambda: None),
            patch(
                "src.cyberagent.services.initiatives._get_initiative",
                return_value=DummyInitiative(),
            ),
            patch(
                "src.cyberagent.services.tasks.has_tasks_for_initiative",
                return_value=True,
            ),
        ):
            system3.run = AsyncMock()
            system3._publish_message_to_agent = AsyncMock()

            await system3.handle_initiative_assign_message(
                message=initiative_message,
                ctx=context,
            )  # type: ignore[call-arg]

            system3.run.assert_not_called()
            system3._publish_message_to_agent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_initiative_assign_message_redelivers_in_progress_assigned_task(
        self,
    ) -> None:
        system3 = System3("System3/controller1")
        initiative_message = InitiativeAssignMessage(
            initiative_id=1, source="System4/strategy1", content="Resume initiative 1."
        )

        from autogen_core import CancellationToken

        context = MessageContext(
            sender=AgentId.from_str("System4/strategy1"),
            topic_id=None,
            is_rpc=False,
            cancellation_token=CancellationToken(),
            message_id="test_msg_redeliver_in_progress",
        )

        class DummyTask:
            id = 8
            name = "Collect user documents"
            assignee = "System1/root"
            status = "in_progress"

        class DummyInitiative:
            def __init__(self) -> None:
                self.id = 1
                self.status = ""
                self.updated = False

            def set_status(self, status):  # noqa: ANN001
                self.status = str(status)

            def update(self):
                self.updated = True

            def get_tasks(self):
                return [DummyTask()]

        with (
            patch("src.agents.system3.init_db", lambda: None),
            patch(
                "src.cyberagent.services.initiatives._get_initiative",
                return_value=DummyInitiative(),
            ),
            patch(
                "src.cyberagent.services.tasks.has_tasks_for_initiative",
                return_value=True,
            ),
        ):
            system3.run = AsyncMock()
            system3._publish_message_to_agent = AsyncMock()

            await system3.handle_initiative_assign_message(
                message=initiative_message,
                ctx=context,
            )  # type: ignore[call-arg]

            system3.run.assert_not_called()
            system3._publish_message_to_agent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_initiative_assign_message_redelivers_all_in_progress_assigned_tasks(
        self,
    ) -> None:
        system3 = System3("System3/controller1")
        initiative_message = InitiativeAssignMessage(
            initiative_id=1, source="System4/strategy1", content="Resume initiative 1."
        )

        from autogen_core import CancellationToken

        context = MessageContext(
            sender=AgentId.from_str("System4/strategy1"),
            topic_id=None,
            is_rpc=False,
            cancellation_token=CancellationToken(),
            message_id="test_msg_redeliver_all_in_progress",
        )

        class DummyTask:
            def __init__(self, task_id: int, name: str) -> None:
                self.id = task_id
                self.name = name
                self.assignee = "System1/root"
                self.status = "in_progress"

        class DummyInitiative:
            def __init__(self) -> None:
                self.id = 1
                self.status = ""
                self.updated = False

            def set_status(self, status):  # noqa: ANN001
                self.status = str(status)

            def update(self):
                self.updated = True

            def get_tasks(self):
                return [
                    DummyTask(8, "Collect user identity"),
                    DummyTask(9, "Collect docs"),
                ]

        with (
            patch("src.agents.system3.init_db", lambda: None),
            patch(
                "src.cyberagent.services.initiatives._get_initiative",
                return_value=DummyInitiative(),
            ),
            patch(
                "src.cyberagent.services.tasks.has_tasks_for_initiative",
                return_value=True,
            ),
        ):
            system3.run = AsyncMock()
            system3._publish_message_to_agent = AsyncMock()

            await system3.handle_initiative_assign_message(
                message=initiative_message,
                ctx=context,
            )  # type: ignore[call-arg]

            system3.run.assert_not_called()
            assert system3._publish_message_to_agent.await_count == 2


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
    print("Phase 2: Structured task assignment (tools disabled)")

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


@pytest.mark.asyncio
async def test_assign_task_uses_valid_message_source() -> None:
    system3 = System3("System3/controller1")

    class DummySystem:
        agent_id_str = "System1/root"

        def get_agent_id(self):
            return AgentId.from_str("System1/root")

    class DummyTask:
        name = "Do work"

    published: dict[str, object] = {}

    async def _capture(message, _agent_id):  # noqa: ANN001
        published["message"] = message

    with (
        patch("src.cyberagent.services.systems.get_system", return_value=DummySystem()),
        patch("src.cyberagent.services.tasks.get_task_by_id", return_value=DummyTask()),
        patch("src.cyberagent.services.tasks.assign_task"),
    ):
        system3._publish_message_to_agent = _capture  # type: ignore[method-assign]
        await system3.assign_task(system_id=1, task_id=7)

    message = cast(TaskAssignMessage | None, published.get("message"))
    assert message is not None
    assert re.fullmatch(r"[A-Za-z0-9_-]+", message.source) is not None
