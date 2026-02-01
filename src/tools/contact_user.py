import asyncio

from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, CancellationToken
from autogen_core.models import FunctionExecutionResult
from autogen_core.tools import BaseTool
from pydantic import BaseModel, model_validator

from src.agent_utils import get_user_agent_id
from src.cli_session import enqueue_pending_question, wait_for_answer
from src.cyberagent.core.runtime import get_runtime


class ContactUserArgsType(BaseModel):
    question: str
    wait_for_response: bool = False
    timeout_seconds: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_question(cls, data):
        if isinstance(data, dict) and "question" not in data and "content" in data:
            data = {**data, "question": data["content"]}
        return data


class InformUserArgsType(BaseModel):
    message: str

    @model_validator(mode="before")
    @classmethod
    def _coerce_message(cls, data):
        if isinstance(data, dict) and "message" not in data and "content" in data:
            data = {**data, "message": data["content"]}
        return data


class ContactUserTool(BaseTool):
    def __init__(self, agent_id: AgentId):
        self.agent_id = agent_id
        description = (
            "Ask the user a question. "
            "Use wait_for_response only if you cannot proceed without an answer."
        )
        super().__init__(
            name=self.__class__.__name__,
            description=description,
            return_type=FunctionExecutionResult,
            args_type=ContactUserArgsType,
        )

    async def run(
        self, args: ContactUserArgsType, cancellation_token: CancellationToken
    ) -> FunctionExecutionResult:
        call_id = f"{self.name}_{asyncio.get_running_loop().time()}"
        question_id = enqueue_pending_question(
            args.question, asked_by=self.agent_id.key, loop=asyncio.get_running_loop()
        )
        message = TextMessage(
            content=args.question,
            source=self.agent_id.key,
            metadata={"ask_user": "true", "question_id": str(question_id)},
        )

        send_result = await self._send_message_to_user(
            message, cancellation_token=cancellation_token
        )
        if send_result.is_error or not args.wait_for_response:
            return send_result

        answer = await wait_for_answer(question_id, args.timeout_seconds)
        if answer is None:
            return FunctionExecutionResult(
                content="No answer received yet.",
                name=self.name,
                call_id=call_id,
                is_error=True,
            )
        return FunctionExecutionResult(
            content=f"Question: {args.question}\nAnswer: {answer}",
            name=self.name,
            call_id=call_id,
            is_error=False,
        )

    async def _send_message_to_user(
        self, message: TextMessage, cancellation_token: CancellationToken
    ) -> FunctionExecutionResult:
        call_id = f"{self.name}_{asyncio.get_running_loop().time()}"
        try:
            runtime = get_runtime()
            response_message = await runtime.send_message(
                message,
                recipient=get_user_agent_id(),
                sender=self.agent_id,
                cancellation_token=cancellation_token,
            )
            if response_message is None:
                response_content = "Message sent."
            else:
                response_content = getattr(
                    response_message, "content", str(response_message)
                )
            return FunctionExecutionResult(
                call_id=call_id,
                content=response_content,
                name=self.name,
                is_error=False,
            )
        except Exception as exc:
            return FunctionExecutionResult(
                call_id=call_id,
                content=f"Error sending message: {exc}",
                name=self.name,
                is_error=True,
            )


class InformUserTool(BaseTool):
    def __init__(self, agent_id: AgentId):
        self.agent_id = agent_id
        description = "Inform the user about progress or status updates."
        super().__init__(
            name=self.__class__.__name__,
            description=description,
            return_type=FunctionExecutionResult,
            args_type=InformUserArgsType,
        )

    async def run(
        self, args: InformUserArgsType, cancellation_token: CancellationToken
    ) -> FunctionExecutionResult:
        call_id = f"{self.name}_{asyncio.get_running_loop().time()}"
        message = TextMessage(
            content=args.message,
            source=self.agent_id.key,
            metadata={"inform_user": "true"},
        )
        send_result = await ContactUserTool(self.agent_id)._send_message_to_user(
            message, cancellation_token=cancellation_token
        )
        if send_result.is_error:
            return send_result
        return FunctionExecutionResult(
            call_id=call_id,
            content=args.message,
            name=self.name,
            is_error=False,
        )
