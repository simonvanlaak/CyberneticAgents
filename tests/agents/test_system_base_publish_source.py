from unittest.mock import AsyncMock

import pytest
from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId

from src.agents.system1 import System1


@pytest.mark.asyncio
async def test_publish_message_to_agent_normalizes_invalid_source_name() -> None:
    system1 = System1("System1/worker1")
    system1._id = AgentId.from_str("System1/worker1")  # type: ignore[attr-defined]
    message = TextMessage(content="hello", source="System3/root")
    publish = AsyncMock()
    system1.publish_message = publish  # type: ignore[method-assign]

    await system1._publish_message_to_agent(message, AgentId.from_str("System3/root"))

    assert message.source == "System3_root"
