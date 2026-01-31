# User-Agent to System4 Communication Tests
# Tests for communication between UserAgent and System4

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, MessageContext, TopicId
from autogen_core._cancellation_token import CancellationToken

from src.agents.user_agent import UserAgent
from src.agents.system4 import System4
from src.agents.messages import UserMessage
from src.cli_session import (
    clear_pending_questions,
    enqueue_pending_question,
    get_pending_question,
)
from src.ui_state import clear_messages, get_latest_user_notice, get_messages


class TestUserAgent:
    """Test UserAgent functionality."""

    def test_user_agent_creation(self):
        """Test that UserAgent can be created."""
        user_agent = UserAgent("test_user")
        assert user_agent is not None
        assert user_agent.id.key == "test_user"

    def test_user_agent_message_handlers_exist(self):
        """Test that UserAgent has the required message handlers."""
        user_agent = UserAgent("test_user")

        # Check that the handler methods exist
        assert hasattr(user_agent, "handle_user_message")
        assert hasattr(user_agent, "handle_task_result")
        assert callable(getattr(user_agent, "handle_user_message"))
        assert callable(getattr(user_agent, "handle_task_result"))


class TestSystem4:
    """Test System4 functionality."""

    def test_system4_creation(self):
        """Test that System4 can be created."""
        system4 = System4("test_system4")
        assert system4 is not None
        assert system4.name == "System4_test_system4"

    def test_system4_message_handlers_exist(self):
        """Test that System4 has the required message handlers."""
        system4 = System4("test_system4")

        # Check that the handler methods exist
        assert hasattr(system4, "handle_user_message")
        assert hasattr(system4, "handle_strategy_request_message")
        assert hasattr(system4, "handle_initiative_review_message")
        assert hasattr(system4, "handle_research_request_message")
        assert callable(getattr(system4, "handle_user_message"))
        assert callable(getattr(system4, "handle_strategy_request_message"))


class TestMessageTypes:
    """Test message type compatibility."""

    def test_user_message_creation(self):
        """Test UserMessage creation and properties."""
        message = UserMessage(content="Test content", source="User")
        assert message.content == "Test content"
        assert message.source == "User"

    def test_user_message_with_different_content_types(self):
        """Test UserMessage with different content types."""
        # String content
        message1 = UserMessage(content="String content", source="User")
        assert isinstance(message1.content, str)

        # Numeric content (should be converted to string)
        message2 = UserMessage(content="123", source="User")  # String numeric
        assert isinstance(message2.content, str)

        # None content - skip this test as it violates type hints


class TestAgentIntegration:
    """Test basic integration between agents."""

    def test_agent_creation_and_initialization(self):
        """Test that all agents can be created and initialized."""
        # Test UserAgent
        user_agent = UserAgent("test_user")
        assert user_agent.id.type == "UserAgent"
        assert user_agent.id.key == "test_user"

        # Test System4
        system4 = System4("test_system4")
        assert system4.agent_id.type == "System4"
        assert system4.agent_id.key == "test_system4"

    def test_agent_name_formatting(self):
        """Test that agent names are properly formatted."""
        # Test with simple name
        user_agent1 = UserAgent("simple_name")
        assert user_agent1.id.key == "simple_name"

        # Test with complex name
        with pytest.raises(ValueError):
            System4("complex-name_with.special")


class TestErrorScenarios:
    """Test error handling scenarios."""

    def test_invalid_agent_names(self):
        """Test agents with unusual names."""
        # Empty name
        user_agent = UserAgent("")
        assert user_agent.id.key == ""

        # Very long name
        long_name = "a" * 100
        system4 = System4(long_name)
        assert system4.name == f"System4_{long_name}"

    def test_message_without_required_fields(self):
        """Test messages with missing fields."""
        # Skip tests that violate type hints - these would be caught by type checking
        # UserMessage without source (should still work)
        # message = UserMessage(content="Test", source=None)  # Type error
        # UserMessage without content (should still work)
        # message = UserMessage(content=None, source="User")  # Type error

        # Test valid message instead
        message = UserMessage(content="Test", source="User")
        assert message.content == "Test"
        assert message.source == "User"


@pytest.mark.asyncio
async def test_basic_agent_functionality():
    """Basic test to ensure agents can be instantiated."""
    # This is a basic smoke test
    user_agent = UserAgent("test_user")
    system4 = System4("test_system4")

    # Test that agents have the expected attributes
    assert hasattr(user_agent, "id")
    assert hasattr(system4, "name")
    assert hasattr(system4, "agent_id")

    print(f"UserAgent created: {user_agent.id.key}")
    print(f"System4 created: {system4.name}")

    # Test message creation
    message = UserMessage(content="Hello", source="User")
    assert message.content == "Hello"
    assert message.source == "User"


@pytest.mark.asyncio
async def test_user_agent_updates_pending_question_on_system4_message():
    clear_pending_questions()
    user_agent = UserAgent("test_user")
    sender = AgentId(type=System4.__name__, key="root")
    ctx = MessageContext(
        sender=sender,
        topic_id=TopicId(type="System4", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )
    message = TextMessage(
        content="Any other constraints to consider?",
        source="System4",
        metadata={"ask_user": "true"},
    )
    await user_agent.handle_assistant_text_message(message, ctx)

    pending = get_pending_question()
    assert pending is not None
    assert pending.content == "Any other constraints to consider?"


@pytest.mark.asyncio
async def test_user_agent_logs_informational_message():
    clear_messages()
    clear_pending_questions()
    user_agent = UserAgent("test_user")
    sender = AgentId(type=System4.__name__, key="root")
    ctx = MessageContext(
        sender=sender,
        topic_id=TopicId(type="System4", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )
    message = TextMessage(
        content="Status update: research in progress.",
        source="System4",
        metadata={"inform_user": "true"},
    )
    await user_agent.handle_assistant_text_message(message, ctx)

    assert get_pending_question() is None
    notice = get_latest_user_notice()
    assert notice is not None
    assert notice.content == "Status update: research in progress."


@pytest.mark.asyncio
async def test_user_agent_records_notice_for_non_question_message():
    clear_messages()
    clear_pending_questions()
    user_agent = UserAgent("test_user")
    sender = AgentId(type=System4.__name__, key="root")
    ctx = MessageContext(
        sender=sender,
        topic_id=TopicId(type="System4", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )
    message = TextMessage(
        content="General update without metadata.",
        source="System4",
    )
    await user_agent.handle_assistant_text_message(message, ctx)

    assert get_pending_question() is None
    notice = get_latest_user_notice()
    assert notice is not None
    assert notice.content == "General update without metadata."


@pytest.mark.asyncio
async def test_user_agent_includes_question_context_in_reply():
    clear_pending_questions()
    clear_messages()
    enqueue_pending_question("What outcome do you want?", asked_by="System4")
    user_agent = UserAgent("test_user")

    user_agent.publish_message = AsyncMock()
    ctx = MessageContext(
        sender=AgentId(type="UserAgent", key="root"),
        topic_id=TopicId(type="UserAgent", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )

    message = UserMessage(content="Build a TUI-first app.", source="User")
    await user_agent.handle_user_message(message, ctx)

    assert user_agent.publish_message.await_count == 1
    published_message = user_agent.publish_message.await_args[0][0]
    assert "What outcome do you want?" in published_message.content
    assert "Build a TUI-first app." in published_message.content

    messages = get_messages()
    assert any(msg.is_user and msg.content == "Build a TUI-first app." for msg in messages)
