# User-Agent to System4 Communication Tests
# Tests for communication between UserAgent and System4

import pytest
from typing import cast
from unittest.mock import AsyncMock
from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, AgentRuntime, MessageContext, TopicId
from autogen_core._cancellation_token import CancellationToken

from src.agents.user_agent import ChannelContext, UserAgent
from src.agents.system4 import System4
from src.agents.messages import UserMessage
from src.cyberagent.channels.inbox import (
    DEFAULT_CHANNEL,
    DEFAULT_SESSION_ID,
    clear_pending_questions,
    list_inbox_entries,
)
from src.cyberagent.channels.telegram import session_store
from src.cyberagent.db.db_utils import get_db
from src.cli_session import enqueue_pending_question, get_pending_question
from src.cyberagent.core.state import get_last_team_id
from src.cyberagent.services import routing as routing_service
from src.cyberagent.services import systems as systems_service
from src.cyberagent.db.models.routing_rule import RoutingRule
from src.enums import SystemType


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

    def test_user_agent_primes_telegram_context_when_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prefer the most recent Telegram session when token is available."""
        sessions = [
            session_store.TelegramSession(
                telegram_user_id=1,
                telegram_chat_id=111,
                agent_session_id="telegram:chat-111:user-1",
                user_info={},
                chat_type="private",
                created_at=10.0,
                last_activity=10.0,
                context={},
            ),
            session_store.TelegramSession(
                telegram_user_id=2,
                telegram_chat_id=222,
                agent_session_id="telegram:chat-222:user-2",
                user_info={},
                chat_type="private",
                created_at=20.0,
                last_activity=30.0,
                context={},
            ),
        ]
        monkeypatch.setattr("src.agents.user_agent.get_secret", lambda *_: "token")
        monkeypatch.setattr(
            "src.agents.user_agent.session_store.list_sessions",
            lambda: sessions,
        )

        user_agent = UserAgent("test_user")

        assert user_agent._last_channel_context == ChannelContext(
            channel="telegram",
            session_id="telegram:chat-222:user-2",
            telegram_chat_id=222,
        )


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
    user_agent.publish_message = AsyncMock()
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
    user_agent.publish_message = AsyncMock()
    user_agent.publish_message = AsyncMock()
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
    await user_agent.handle_assistant_text_message(
        message=message,
        ctx=ctx,
    )  # type: ignore[call-arg]

    pending = get_pending_question()
    assert pending is not None
    assert pending.content == "Any other constraints to consider?"
    entries = list_inbox_entries(kind="system_question", status="pending")
    assert len(entries) == 1
    assert entries[0].content == "Any other constraints to consider?"


@pytest.mark.asyncio
async def test_user_agent_informational_message_does_not_enqueue_question():
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
    await user_agent.handle_assistant_text_message(
        message=message,
        ctx=ctx,
    )  # type: ignore[call-arg]

    assert get_pending_question() is None
    entries = list_inbox_entries(kind="system_response")
    assert len(entries) == 1
    assert entries[0].content == "Status update: research in progress."


@pytest.mark.asyncio
async def test_user_agent_forwards_informational_message_to_telegram() -> None:
    clear_pending_questions()
    user_agent = UserAgent("test_user")
    user_agent._last_channel_context = ChannelContext(
        channel="telegram",
        session_id="telegram:chat-99:user-42",
        telegram_chat_id=99,
    )
    user_agent._send_telegram_prompt = AsyncMock()
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
    await user_agent.handle_assistant_text_message(
        message=message,
        ctx=ctx,
    )  # type: ignore[call-arg]

    user_agent._send_telegram_prompt.assert_awaited_once_with(99, message.content)
    assert get_pending_question() is None
    entries = list_inbox_entries(kind="system_response")
    assert len(entries) == 1
    assert entries[0].channel == "telegram"


@pytest.mark.asyncio
async def test_user_agent_forwards_question_with_id_to_telegram() -> None:
    clear_pending_questions()
    user_agent = UserAgent("test_user")
    user_agent._last_channel_context = ChannelContext(
        channel="telegram",
        session_id="telegram:chat-99:user-42",
        telegram_chat_id=99,
    )
    user_agent._send_telegram_prompt = AsyncMock()
    sender = AgentId(type=System4.__name__, key="root")
    ctx = MessageContext(
        sender=sender,
        topic_id=TopicId(type="System4", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )
    message = TextMessage(
        content="Hello! How can I help you today?",
        source="System4",
        metadata={"ask_user": "true", "question_id": "1"},
    )
    await user_agent.handle_assistant_text_message(
        message=message,
        ctx=ctx,
    )  # type: ignore[call-arg]

    user_agent._send_telegram_prompt.assert_awaited_once_with(99, message.content)
    entries = list_inbox_entries(kind="system_question")
    assert len(entries) == 1
    assert entries[0].content == "Hello! How can I help you today?"


@pytest.mark.asyncio
async def test_user_agent_non_question_message_does_not_enqueue_question():
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
    await user_agent.handle_assistant_text_message(
        message=message,
        ctx=ctx,
    )  # type: ignore[call-arg]

    assert get_pending_question() is None
    entries = list_inbox_entries()
    assert entries == []


@pytest.mark.asyncio
async def test_user_agent_includes_question_context_in_reply():
    clear_pending_questions()
    enqueue_pending_question("What outcome do you want?", asked_by="System4")
    user_agent = UserAgent("test_user")

    user_agent.publish_message = AsyncMock()
    setattr(user_agent, "_runtime", cast(AgentRuntime, object()))
    ctx = MessageContext(
        sender=AgentId(type="UserAgent", key="root"),
        topic_id=TopicId(type="UserAgent", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )

    message = UserMessage(content="Build a CLI-first app.", source="User")
    await user_agent.handle_user_message(
        message=message,
        ctx=ctx,
    )  # type: ignore[call-arg]

    assert user_agent.publish_message.await_count == 1
    await_args = user_agent.publish_message.await_args
    assert await_args is not None
    published_message = await_args.kwargs["message"]
    assert "What outcome do you want?" in published_message.content
    assert "Build a CLI-first app." in published_message.content
    entries = list_inbox_entries(kind="user_prompt")
    assert len(entries) == 1
    assert entries[0].content == "Build a CLI-first app."


@pytest.mark.asyncio
async def test_user_agent_skips_inbox_entry_when_already_recorded() -> None:
    clear_pending_questions()
    user_agent = UserAgent("test_user")
    user_agent.publish_message = AsyncMock()
    setattr(user_agent, "_runtime", cast(AgentRuntime, object()))
    ctx = MessageContext(
        sender=AgentId(type="UserAgent", key="root"),
        topic_id=TopicId(type="UserAgent", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )
    message = UserMessage(content="Voice transcript", source="User")
    message.metadata = {
        "channel": "telegram",
        "session_id": "telegram:chat-1:user-2",
        "inbox_recorded": "true",
    }

    await user_agent.handle_user_message(message=message, ctx=ctx)  # type: ignore[call-arg]

    entries = list_inbox_entries(kind="user_prompt")
    assert entries == []


@pytest.mark.asyncio
async def test_user_agent_does_not_resolve_cross_channel_question() -> None:
    clear_pending_questions()
    enqueue_pending_question(
        "Telegram-only question?",
        asked_by="System4",
        channel="telegram",
        session_id="telegram:chat-99:user-42",
    )
    user_agent = UserAgent("test_user")
    user_agent.publish_message = AsyncMock()
    setattr(user_agent, "_runtime", cast(AgentRuntime, object()))
    ctx = MessageContext(
        sender=AgentId(type="UserAgent", key="root"),
        topic_id=TopicId(type="UserAgent", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )
    message = UserMessage(content="CLI reply", source="User")
    message.metadata = {"channel": "cli", "session_id": "cli-main"}

    await user_agent.handle_user_message(
        message=message,
        ctx=ctx,
    )  # type: ignore[call-arg]

    pending = get_pending_question()
    assert pending is not None
    assert pending.content == "Telegram-only question?"
    await_args = user_agent.publish_message.await_args
    assert await_args is not None
    published_message = await_args.kwargs["message"]
    assert "Telegram-only question?" not in published_message.content


@pytest.mark.asyncio
async def test_user_agent_enqueues_pending_question_with_channel_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_pending_questions()
    user_agent = UserAgent("test_user")
    user_agent.publish_message = AsyncMock()
    setattr(user_agent, "_runtime", cast(AgentRuntime, object()))

    ctx = MessageContext(
        sender=AgentId(type="UserAgent", key="root"),
        topic_id=TopicId(type="UserAgent", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )

    inbound = UserMessage(content="Hi", source="User")
    inbound.metadata = {
        "channel": "telegram",
        "session_id": "telegram:chat-99:user-42",
        "telegram_chat_id": "99",
    }
    await user_agent.handle_user_message(message=inbound, ctx=ctx)  # type: ignore[call-arg]

    sender = AgentId(type=System4.__name__, key="root")
    reply_ctx = MessageContext(
        sender=sender,
        topic_id=TopicId(type="System4", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message-2",
    )
    message = TextMessage(
        content="Need confirmation?",
        source="System4",
        metadata={"ask_user": "true"},
    )
    await user_agent.handle_assistant_text_message(
        message=message,
        ctx=reply_ctx,
    )  # type: ignore[call-arg]

    pending = get_pending_question()
    assert pending is not None
    assert pending.channel == "telegram"
    assert pending.session_id == "telegram:chat-99:user-42"
    entries = list_inbox_entries(kind="system_question")
    assert len(entries) == 1
    assert entries[0].channel == "telegram"


@pytest.mark.asyncio
async def test_user_agent_uses_cli_defaults_without_channel_metadata() -> None:
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
        content="Need confirmation?",
        source="System4",
        metadata={"ask_user": "true"},
    )
    await user_agent.handle_assistant_text_message(
        message=message,
        ctx=ctx,
    )  # type: ignore[call-arg]

    pending = get_pending_question()
    assert pending is not None
    assert pending.channel == DEFAULT_CHANNEL
    assert pending.session_id == DEFAULT_SESSION_ID
    entries = list_inbox_entries(kind="system_question")
    assert len(entries) == 1
    assert entries[0].channel == DEFAULT_CHANNEL


@pytest.mark.asyncio
async def test_user_agent_routes_message_to_configured_system() -> None:
    user_agent = UserAgent("test_user")
    user_agent.publish_message = AsyncMock()
    setattr(user_agent, "_runtime", cast(AgentRuntime, object()))
    team_id = get_last_team_id()
    assert team_id is not None
    systems1 = systems_service.get_systems_by_type(team_id, SystemType.OPERATION)
    assert systems1
    target = systems1[0]
    routing_service.create_routing_rule(
        team_id=team_id,
        name="telegram route",
        channel="telegram",
        filters={"telegram_user_id": "123"},
        targets=[{"system_id": target.id}],
        priority=5,
    )
    ctx = MessageContext(
        sender=AgentId(type="UserAgent", key="root"),
        topic_id=TopicId(type="UserAgent", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )
    message = UserMessage(content="hello", source="User")
    message.metadata = {
        "channel": "telegram",
        "session_id": "telegram:chat-1:user-123",
        "telegram_user_id": "123",
    }

    await user_agent.handle_user_message(message=message, ctx=ctx)  # type: ignore[call-arg]

    assert user_agent.publish_message.await_count == 1
    call = user_agent.publish_message.await_args
    assert call is not None
    topic_id = call.kwargs["topic_id"]
    assert topic_id.type == "System1:"
    assert topic_id.source == "root"


@pytest.mark.asyncio
async def test_user_agent_includes_dlq_metadata_on_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_pending_questions()
    user_agent = UserAgent("test_user")
    user_agent.publish_message = AsyncMock()
    setattr(user_agent, "_runtime", cast(AgentRuntime, object()))
    team_id = get_last_team_id()
    assert team_id is not None
    monkeypatch.setenv("CYBERAGENT_ACTIVE_TEAM_ID", str(team_id))
    session = next(get_db())
    try:
        session.query(RoutingRule).delete()
        session.commit()
    finally:
        session.close()
    ctx = MessageContext(
        sender=AgentId(type="UserAgent", key="root"),
        topic_id=TopicId(type="UserAgent", source="root"),
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test-message",
    )
    message = UserMessage(content="Unroutable", source="User")
    await user_agent.handle_user_message(message=message, ctx=ctx)  # type: ignore[call-arg]

    await_args = user_agent.publish_message.await_args
    assert await_args is not None
    published_message = await_args.kwargs["message"]
    assert published_message.metadata is not None
    assert "dlq_entry_id" in published_message.metadata
