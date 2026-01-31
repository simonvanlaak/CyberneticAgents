import pytest
from unittest.mock import AsyncMock

from autogen_core import AgentId, CancellationToken
from autogen_core.models import FunctionExecutionResult

from src.tools.contact_user import (
    ContactUserArgsType,
    ContactUserTool,
    InformUserArgsType,
    InformUserTool,
)


def test_contact_user_args_accepts_question():
    args = ContactUserArgsType(question="What is the timeline?")
    assert args.question == "What is the timeline?"


def test_contact_user_args_accepts_content_alias():
    args = ContactUserArgsType(content="What is the timeline?")
    assert args.question == "What is the timeline?"


def test_inform_user_args_accepts_message():
    args = InformUserArgsType(message="Status update")
    assert args.message == "Status update"


def test_inform_user_args_accepts_content_alias():
    args = InformUserArgsType(content="Status update")
    assert args.message == "Status update"


@pytest.mark.asyncio
async def test_contact_user_send_handles_none_response(monkeypatch):
    tool = ContactUserTool(AgentId.from_str("System4/root"))
    cancellation_token = CancellationToken()

    runtime = AsyncMock()
    runtime.send_message = AsyncMock(return_value=None)
    monkeypatch.setattr("src.tools.contact_user.get_runtime", lambda: runtime)

    result = await tool._send_message_to_user(  # type: ignore[attr-defined]
        message=AsyncMock(), cancellation_token=cancellation_token
    )

    assert isinstance(result, FunctionExecutionResult)
    assert result.is_error is False
