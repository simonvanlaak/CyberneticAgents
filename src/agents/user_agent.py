from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, MessageContext, RoutedAgent, TopicId, message_handler

from src.agents.messages import UserMessage
from src.cli_session import get_pending_question, resolve_pending_question
from src.cli_session import enqueue_pending_question
from src.agents.system4 import System4
from src.ui_state import add_message, add_user_notice


class UserAgent(RoutedAgent):
    def __init__(self, description: str):
        super().__init__(description)
        if not hasattr(self, "_id"):
            self._id = AgentId(type=self.__class__.__name__, key=description)

    @message_handler
    async def handle_user_message(
        self, message: UserMessage, ctx: MessageContext
    ) -> None:
        print(f"[user]: {message.content}", flush=True)
        add_message(sender="User", content=message.content, is_user=True)
        resolved = resolve_pending_question(message.content)
        if resolved:
            message.content = (
                "User answered a pending question.\n"
                f"Question: {resolved.content}\n"
                f"Answer: {resolved.answer}"
            )
        message.source = self.id.key
        print(f"{'-' * 80}\n[{self.id.__str__()}]:{message.content}")
        topic_id = TopicId(f"{System4.__name__}:", "root")
        print(
            f"{self.id.__str__()} -> {message.__class__.__name__} -> {System4.__name__}/root"
        )
        await self.publish_message(
            message,
            topic_id=topic_id,
        )

    @message_handler
    async def handle_assistant_text_message(
        self, message: TextMessage, ctx: MessageContext
    ) -> None:
        print(f"{'-' * 80} You received a message! {'-' * 80}")
        print(f"[{ctx.sender.__str__()}]: {message.content}")
        if message.metadata:
            ask_user_flag = str(message.metadata.get("ask_user", "")).lower() in {
                "true",
                "1",
                "yes",
            }
            inform_user_flag = str(message.metadata.get("inform_user", "")).lower() in {
                "true",
                "1",
                "yes",
            }
            if ask_user_flag and message.metadata.get("question_id") is None:
                asked_by = str(ctx.sender) if ctx.sender else None
                enqueue_pending_question(message.content, asked_by=asked_by)
            if ask_user_flag:
                add_message(
                    sender=str(ctx.sender) if ctx.sender else "Unknown",
                    content=message.content,
                    is_user=False,
                )
            elif inform_user_flag or not ask_user_flag:
                add_user_notice(
                    sender=str(ctx.sender) if ctx.sender else "Unknown",
                    content=message.content,
                )
        else:
            add_user_notice(
                sender=str(ctx.sender) if ctx.sender else "Unknown",
                content=message.content,
            )
        pending_question = get_pending_question()
        if pending_question:
            print(f"Pending question (System4): {pending_question.content}")

    async def handle_task_result(
        self, message: TextMessage, ctx: MessageContext
    ) -> None:
        """Fallback handler for task result style messages."""
        add_message(
            sender=str(ctx.sender) if ctx.sender else "Unknown",
            content=message.content,
            is_user=False,
        )
