import pytest

from src.agents.system1 import System1
from src.agents.system4 import System4


@pytest.mark.asyncio
async def test_memory_prompt_includes_system4_global_permissions() -> None:
    system4 = System4("System4/controller1")
    await system4._set_system_prompt([])
    content = "\n".join(message.content for message in system4._agent._system_messages)
    assert "# MEMORY" in content
    assert "Permission override: you may read/write team and global scopes" in content


@pytest.mark.asyncio
async def test_memory_prompt_restricts_system1_team_writes() -> None:
    system1 = System1("System1/controller1")
    await system1._set_system_prompt([])
    content = "\n".join(message.content for message in system1._agent._system_messages)
    assert "# MEMORY" in content
    assert (
        "Permission override: you may read team and global scopes but must not write team/global"
        in content
    )


@pytest.mark.asyncio
async def test_memory_prompt_hides_memory_tool_guidance_when_tools_disabled() -> None:
    system4 = System4("System4/controller1")
    await system4._set_system_prompt([], active_tools=[])
    content = "\n".join(message.content for message in system4._agent._system_messages)
    assert "Memory tool unavailable for this run." in content
    assert "Use memory_crud to store durable facts" not in content
    assert "No tools available" in content
