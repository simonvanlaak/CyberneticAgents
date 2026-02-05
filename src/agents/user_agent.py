import asyncio
import logging
import os
from dataclasses import dataclass

from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, MessageContext, RoutedAgent, TopicId, message_handler

from src.agents.messages import UserMessage
from src.agents.system4 import System4
from src.cli_session import (
    add_inbox_entry,
    enqueue_pending_question,
    get_pending_question,
    resolve_pending_question_for_route,
)
from src.cyberagent.channels.routing import MessageRoute
from src.cyberagent.channels.inbox import DEFAULT_CHANNEL, DEFAULT_SESSION_ID
from src.cyberagent.channels.telegram import session_store
from src.cyberagent.channels.telegram.outbound import (
    send_message as send_telegram_message,
)
from src.cyberagent.core.state import get_last_team_id, mark_team_active
from src.cyberagent.services import routing as routing_service
from src.cyberagent.secrets import get_secret

logger = logging.getLogger(__name__)


@dataclass
class ChannelContext:
    channel: str
    session_id: str
    telegram_chat_id: int | None = None


class UserAgent(RoutedAgent):
    def __init__(self, description: str):
        super().__init__(description)
        if not hasattr(self, "_id"):
            self._id = AgentId(type=self.__class__.__name__, key=description)
        self._last_channel_context: ChannelContext | None = None
        self._prime_channel_context()

    @message_handler
    async def handle_user_message(
        self, message: UserMessage, ctx: MessageContext
    ) -> None:
        logger.debug("[user]: %s", message.content)
        self._capture_channel_context(message)
        channel = (
            self._last_channel_context.channel
            if self._last_channel_context
            else DEFAULT_CHANNEL
        )
        session_id = (
            self._last_channel_context.session_id
            if self._last_channel_context
            else DEFAULT_SESSION_ID
        )
        metadata = message.metadata if hasattr(message, "metadata") else None
        already_recorded = False
        if isinstance(metadata, dict):
            already_recorded = str(metadata.get("inbox_recorded", "")).lower() in {
                "true",
                "1",
                "yes",
            }
        if not already_recorded:
            add_inbox_entry(
                "user_prompt",
                message.content,
                channel=channel,
                session_id=session_id,
                metadata=metadata if isinstance(metadata, dict) else None,
            )
        resolved = resolve_pending_question_for_route(
            message.content, MessageRoute(channel=channel, session_id=session_id)
        )
        if resolved:
            message.content = (
                "User answered a pending question.\n"
                f"Question: {resolved.content}\n"
                f"Answer: {resolved.answer}"
            )
        message.source = self.id.key
        if getattr(self, "_runtime", None) is None:
            return
        team_id = self._resolve_team_id()
        routing_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        routing_metadata.setdefault("channel", channel)
        routing_metadata.setdefault("session_id", session_id)
        if team_id is None:
            await self._publish_to_agent(
                message, AgentId(type=System4.__name__, key="root")
            )
            return
        decision = routing_service.resolve_message_decision(
            team_id=team_id,
            channel=channel,
            metadata=routing_metadata,
        )
        if decision.dlq_entry_id is not None:
            dlq_metadata = (
                message.metadata if isinstance(message.metadata, dict) else {}
            )
            dlq_metadata = dict(dlq_metadata)
            dlq_metadata["dlq_entry_id"] = str(decision.dlq_entry_id)
            if decision.dlq_reason:
                dlq_metadata["dlq_reason"] = decision.dlq_reason
            message.metadata = dlq_metadata
        for target in decision.targets:
            await self._publish_to_agent(message, AgentId.from_str(target))

    @message_handler
    async def handle_assistant_text_message(
        self, message: TextMessage, ctx: MessageContext
    ) -> None:
        logger.debug("[%s]: %s", ctx.sender.__str__(), message.content)
        if message.metadata:
            inform_user_flag = str(message.metadata.get("inform_user", "")).lower() in {
                "true",
                "1",
                "yes",
            }
            ask_user_flag = str(message.metadata.get("ask_user", "")).lower() in {
                "true",
                "1",
                "yes",
            }
            channel = (
                self._last_channel_context.channel
                if self._last_channel_context
                else DEFAULT_CHANNEL
            )
            session_id = (
                self._last_channel_context.session_id
                if self._last_channel_context
                else DEFAULT_SESSION_ID
            )
            if ask_user_flag and message.metadata.get("question_id") is None:
                asked_by = str(ctx.sender) if ctx.sender else None
                enqueue_pending_question(
                    message.content,
                    asked_by=asked_by,
                    channel=channel,
                    session_id=session_id,
                )
                if (
                    self._last_channel_context
                    and self._last_channel_context.channel == "telegram"
                    and self._last_channel_context.telegram_chat_id is not None
                ):
                    await self._send_telegram_prompt(
                        self._last_channel_context.telegram_chat_id,
                        message.content,
                    )
            elif inform_user_flag:
                add_inbox_entry(
                    "system_response",
                    message.content,
                    channel=channel,
                    session_id=session_id,
                    asked_by=str(ctx.sender) if ctx.sender else None,
                )
                if (
                    self._last_channel_context
                    and self._last_channel_context.channel == "telegram"
                    and self._last_channel_context.telegram_chat_id is not None
                ):
                    await self._send_telegram_prompt(
                        self._last_channel_context.telegram_chat_id,
                        message.content,
                    )
            elif ask_user_flag:
                add_inbox_entry(
                    "system_question",
                    message.content,
                    channel=channel,
                    session_id=session_id,
                    asked_by=str(ctx.sender) if ctx.sender else None,
                    status="pending",
                )
                if (
                    self._last_channel_context
                    and self._last_channel_context.channel == "telegram"
                    and self._last_channel_context.telegram_chat_id is not None
                ):
                    await self._send_telegram_prompt(
                        self._last_channel_context.telegram_chat_id,
                        message.content,
                    )
        pending_question = get_pending_question()
        if pending_question:
            logger.debug("Pending question (System4): %s", pending_question.content)

    async def handle_task_result(
        self, message: TextMessage, ctx: MessageContext
    ) -> None:
        """Fallback handler for task result style messages."""

    def _capture_channel_context(self, message: UserMessage) -> None:
        metadata = message.metadata if hasattr(message, "metadata") else None
        if not isinstance(metadata, dict):
            return
        channel = metadata.get("channel")
        session_id = metadata.get("session_id")
        if not isinstance(channel, str) or not channel:
            return
        if not isinstance(session_id, str) or not session_id:
            session_id = DEFAULT_SESSION_ID
        telegram_chat_id = metadata.get("telegram_chat_id")
        if isinstance(telegram_chat_id, str) and telegram_chat_id.isdigit():
            telegram_chat_id = int(telegram_chat_id)
        if not isinstance(telegram_chat_id, int):
            telegram_chat_id = None
        self._last_channel_context = ChannelContext(
            channel=channel,
            session_id=session_id,
            telegram_chat_id=telegram_chat_id,
        )

    def _prime_channel_context(self) -> None:
        if self._last_channel_context is not None:
            return
        if not get_secret("TELEGRAM_BOT_TOKEN"):
            return
        sessions = session_store.list_sessions()
        if not sessions:
            return
        latest = max(sessions, key=lambda session: session.last_activity)
        self._last_channel_context = ChannelContext(
            channel="telegram",
            session_id=latest.agent_session_id,
            telegram_chat_id=latest.telegram_chat_id,
        )

    async def _send_telegram_prompt(self, chat_id: int, text: str) -> None:
        if not get_secret("TELEGRAM_BOT_TOKEN"):
            return
        try:
            await asyncio.to_thread(send_telegram_message, chat_id, text)
        except Exception:  # pragma: no cover - safety net
            logger.exception("Failed to deliver Telegram prompt to chat %s", chat_id)

    def _resolve_team_id(self) -> int | None:
        team_id_env = os.environ.get("CYBERAGENT_ACTIVE_TEAM_ID")
        if team_id_env:
            try:
                team_id = int(team_id_env)
            except ValueError:
                logger.warning("Invalid CYBERAGENT_ACTIVE_TEAM_ID '%s'.", team_id_env)
                return None
            mark_team_active(team_id)
            return team_id
        team_id = get_last_team_id()
        if team_id is not None:
            mark_team_active(team_id)
        return team_id

    async def _publish_to_agent(self, message: UserMessage, agent_id: AgentId) -> None:
        topic_type = f"{agent_id.type}:"
        topic_source = agent_id.key.replace("/", "_")
        logger.debug(
            "%s -> %s -> %s/%s",
            self.id.__str__(),
            message.__class__.__name__,
            agent_id.type,
            topic_source,
        )
        await self.publish_message(
            message=message, topic_id=TopicId(topic_type, topic_source)
        )
