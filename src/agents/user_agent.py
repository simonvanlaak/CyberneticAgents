import asyncio
import logging
from dataclasses import dataclass

from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, MessageContext, RoutedAgent, TopicId, message_handler

from src.agents.messages import UserMessage
from src.agents.system4 import System4
from src.cli_session import (
    add_inbox_entry,
    enqueue_pending_question,
    get_pending_question,
    resolve_pending_question,
)
from src.cyberagent.channels.inbox import DEFAULT_CHANNEL, DEFAULT_SESSION_ID
from src.cyberagent.channels.telegram.outbound import (
    send_message as send_telegram_message,
)
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
        add_inbox_entry(
            "user_prompt",
            message.content,
            channel=channel,
            session_id=session_id,
        )
        resolved = resolve_pending_question(
            message.content, channel=channel, session_id=session_id
        )
        if resolved:
            message.content = (
                "User answered a pending question.\n"
                f"Question: {resolved.content}\n"
                f"Answer: {resolved.answer}"
            )
        message.source = self.id.key
        topic_id = TopicId(f"{System4.__name__}:", "root")
        logger.debug(
            "%s -> %s -> %s/root",
            self.id.__str__(),
            message.__class__.__name__,
            System4.__name__,
        )
        if getattr(self, "_runtime", None) is None:
            return
        await self.publish_message(
            message,
            topic_id=topic_id,
        )

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

    async def _send_telegram_prompt(self, chat_id: int, text: str) -> None:
        if not get_secret("TELEGRAM_BOT_TOKEN"):
            return
        try:
            await asyncio.to_thread(send_telegram_message, chat_id, text)
        except Exception:  # pragma: no cover - safety net
            logger.exception("Failed to deliver Telegram prompt to chat %s", chat_id)
