import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.modules.setdefault("langfuse", MagicMock())

from src.agents.system4 import System4  # noqa: E402


@pytest.mark.asyncio
async def test_create_strategy_tool_sends_direct_message():
    system4 = System4("System4/root")
    system4._id = system4.agent_id
    system4.send_message = AsyncMock()
    system4._publish_message_to_agent = AsyncMock()

    ok, err = await system4.create_strategy_tool("strategy content")

    assert ok is True
    assert err is None
    system4.send_message.assert_awaited_once()
    system4._publish_message_to_agent.assert_not_called()
