from typing import Literal

from autogen_core import AgentId, MessageContext, message_handler
from pydantic import BaseModel

from src.agents.system_base import SystemBase
from src.cyberagent.services import tasks as task_service

from .messages import CapabilityGapMessage, TaskAssignMessage, TaskReviewMessage


class TaskExecutionResult(BaseModel):
    status: Literal["done", "blocked"]
    result: str
    reasoning: str | None = None


def _parse_task_execution_result(raw_result: str) -> TaskExecutionResult:
    """
    Parse a task execution response into a strict execution contract.

    Any ambiguous, malformed, or underspecified output is treated as blocked so
    tasks are never completed by accident.
    """
    try:
        execution = TaskExecutionResult.model_validate_json(raw_result)
    except Exception:
        return TaskExecutionResult(
            status="blocked",
            result=raw_result,
            reasoning="Ambiguous or non-JSON task execution output.",
        )

    if execution.status == "done" and not execution.result.strip():
        return TaskExecutionResult(
            status="blocked",
            result=raw_result,
            reasoning="Task marked done without a concrete result.",
        )
    return execution


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
        raw_result = (
            latest_message.to_model_text()
            if hasattr(latest_message, "to_model_text")
            else str(latest_message)
        )

        execution = _parse_task_execution_result(raw_result)

        if execution.status == "blocked":
            reasoning = execution.reasoning or execution.result
            task_service.mark_task_blocked(task, reasoning)
            await self._publish_message_to_agent(
                TaskReviewMessage(
                    task_id=message.task_id,
                    content=reasoning,
                    assignee_agent_id_str=str(self.agent_id),
                    source=str(self.agent_id),
                ),
                self.task_requestor,
            )
            await self._publish_message_to_agent(
                CapabilityGapMessage(
                    task_id=message.task_id,
                    content=reasoning,
                    assignee_agent_id_str=str(self.agent_id),
                    source=str(self.agent_id),
                ),
                self.task_requestor,
            )
            return

        task_service.complete_task(task, execution.result)
        await self._publish_message_to_agent(
            TaskReviewMessage(
                task_id=message.task_id,
                content=execution.result,
                assignee_agent_id_str=str(self.agent_id),
                source=str(self.agent_id),
            ),
            self.task_requestor,
        )
