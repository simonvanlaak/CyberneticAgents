from autogen_core import AgentId, MessageContext, message_handler

from src.agents.system_base import SystemBase
from src.cyberagent.services import tasks as task_service

from .messages import TaskAssignMessage, TaskReviewMessage


class System1(SystemBase):
    def __init__(self, name: str, trace_context: dict | None = None):
        super().__init__(
            name,
            """
            You are an operational execution system responsible for performing specific tasks.
            You execute operations directly and return results to the requesting system.
            """,
            [
                "1. Execute tasks assigned by the requesting system.",
                "2. Return results to the requesting system.",
                "3. In case you are lacking the ability to execute a task, you request additional capabilities from the requesting system.",
            ],
            trace_context,
        )

    @message_handler
    async def handle_assign_task_message(
        self, message: TaskAssignMessage, ctx: MessageContext
    ) -> None:
        if ctx.sender is not None:
            self.task_requestor = ctx.sender
        else:
            self.task_requestor = AgentId.from_str(message.source)
        task = task_service.start_task(message.task_id)
        response = await self.run([message], ctx)
        latest_message = self._get_last_message(response)
        result = (
            latest_message.to_model_text()
            if hasattr(latest_message, "to_model_text")
            else str(latest_message)
        )
        task_service.complete_task(task, result)
        await self._publish_message_to_agent(
            TaskReviewMessage(
                task_id=message.task_id,
                content=result,
                assignee_agent_id_str=str(self.agent_id),
                source=str(self.agent_id),
            ),
            self.task_requestor,
        )
