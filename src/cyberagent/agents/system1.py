import json
from typing import Any, Literal

from autogen_core import AgentId, MessageContext, message_handler
from pydantic import BaseModel

from src.cyberagent.agents.system_base import SystemBase
from src.cyberagent.services import tasks as task_service

from .messages import TaskAssignMessage, TaskReviewMessage


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


def _serialize_execution_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_serialize_execution_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_execution_value(item) for item in value]
    if isinstance(value, dict):
        serialized: dict[str, object] = {}
        for key, item in value.items():
            serialized[str(key)] = _serialize_execution_value(item)
        return serialized
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
        except Exception:
            return str(value)
        return _serialize_execution_value(dumped)
    if hasattr(value, "__dict__"):
        try:
            payload = dict(vars(value))
        except Exception:
            return str(value)
        return _serialize_execution_value(payload)
    return str(value)


def _build_task_execution_log(messages: list[Any]) -> str:
    """
    Build a stable JSON execution trace from all task run messages.

    The trace includes intermediate model text, tool-call events, and metadata so
    System3/System1 can review how the task was resolved.
    """
    execution_entries: list[dict[str, object]] = []
    for message in messages:
        entry: dict[str, object] = {"type": message.__class__.__name__}
        source = getattr(message, "source", None)
        if source is not None:
            entry["source"] = str(source)
        if hasattr(message, "to_model_text"):
            try:
                entry["model_text"] = message.to_model_text()
            except Exception:
                entry["model_text"] = str(message)
        content = getattr(message, "content", None)
        if content is not None:
            entry["content"] = _serialize_execution_value(content)
        metadata = getattr(message, "metadata", None)
        if metadata:
            entry["metadata"] = _serialize_execution_value(metadata)
        execution_entries.append(entry)
    return json.dumps(execution_entries, ensure_ascii=True)


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
                (
                    "3. In case you are lacking the ability or context, first use "
                    "task_search and memory_crud to find prior team evidence; "
                    "only then request additional capabilities."
                ),
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
        try:
            response = await self.run(
                [message],
                ctx,
                message_specific_prompts=[
                    (
                        "Return a JSON object for the task outcome with fields: "
                        "status ('done' or 'blocked'), result (string), and optional "
                        "reasoning (string). Do not call a tool named "
                        "TaskExecutionResult."
                    ),
                    (
                        "If key information is missing, call task_search to inspect "
                        "previous team task outputs before marking this task blocked."
                    ),
                    (
                        "If task_search is insufficient, read team/global memory via "
                        "memory_crud list before escalating."
                    ),
                ],
                enable_tools=True,
            )
            task_service.set_task_execution_log(
                task,
                _build_task_execution_log(getattr(response, "messages", [])),
            )
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
        except Exception as exc:
            failure_reason = (
                "Task execution failed due to an internal error: "
                f"{type(exc).__name__}: {exc}"
            )
            task_service.mark_task_blocked(task, failure_reason)
            await self._publish_message_to_agent(
                TaskReviewMessage(
                    task_id=message.task_id,
                    content=failure_reason,
                    assignee_agent_id_str=str(self.agent_id),
                    source=str(self.agent_id),
                ),
                self.task_requestor,
            )
