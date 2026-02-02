import logging

from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, MessageContext, RoutedAgent, TopicId, message_handler

from src.agents.messages import UserMessage
from src.cli_session import get_pending_question, resolve_pending_question
from src.cli_session import enqueue_pending_question
from src.agents.system4 import System4

logger = logging.getLogger(__name__)


class UserAgent(RoutedAgent):
    def __init__(self, description: str):
        super().__init__(description)
        if not hasattr(self, "_id"):
            self._id = AgentId(type=self.__class__.__name__, key=description)

    @message_handler
    async def handle_user_message(
        self, message: UserMessage, ctx: MessageContext
    ) -> None:
        logger.debug("[user]: %s", message.content)
        resolved = resolve_pending_question(message.content)
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
            ask_user_flag = str(message.metadata.get("ask_user", "")).lower() in {
                "true",
                "1",
                "yes",
            }
            if ask_user_flag and message.metadata.get("question_id") is None:
                asked_by = str(ctx.sender) if ctx.sender else None
                enqueue_pending_question(message.content, asked_by=asked_by)
        pending_question = get_pending_question()
        if pending_question:
            logger.debug("Pending question (System4): %s", pending_question.content)

    async def handle_task_result(
        self, message: TextMessage, ctx: MessageContext
    ) -> None:
        """Fallback handler for task result style messages."""
