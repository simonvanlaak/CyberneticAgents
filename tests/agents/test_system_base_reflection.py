import pytest
from unittest.mock import AsyncMock

from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, CancellationToken, MessageContext
from pydantic import BaseModel

from src.agents.system4 import System4


class DummyStructuredResponse(BaseModel):
    value: str


@pytest.mark.asyncio
async def test_system4_run_disables_reflection_without_structured_output():
    system4 = System4("System4/intelligence1")
    system4._set_system_prompt = AsyncMock()
    system4._agent.run = AsyncMock(
        return_value=TaskResult(messages=[TextMessage(content="ok", source="test")])
    )
    ctx = MessageContext(
        sender=AgentId.from_str("User/user"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test",
    )

    await system4.run([TextMessage(content="hi", source="User")], ctx)

    assert system4._agent._reflect_on_tool_use is False


@pytest.mark.asyncio
async def test_system4_run_enables_reflection_with_structured_output():
    system4 = System4("System4/intelligence1")
    system4._set_system_prompt = AsyncMock()
    system4._agent.run = AsyncMock(
        return_value=TaskResult(messages=[TextMessage(content="ok", source="test")])
    )
    ctx = MessageContext(
        sender=AgentId.from_str("User/user"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test",
    )

    await system4.run(
        [TextMessage(content="hi", source="User")],
        ctx,
        output_content_type=DummyStructuredResponse,
    )

    assert system4._agent._reflect_on_tool_use is True
