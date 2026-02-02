from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from autogen_core import CancellationToken

from src.cyberagent.tools.cli_executor.skill_loader import SkillDefinition
from src.cyberagent.tools.cli_executor.skill_tools import build_skill_tools


class _DummyCliTool:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, tool_name: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"tool_name": tool_name, **kwargs})
        return {"success": True}


@pytest.mark.asyncio
async def test_build_skill_tools_invokes_cli_tool() -> None:
    skill = SkillDefinition(
        name="web-search",
        description="Search the web.",
        location=Path("skills/web-search"),
        tool_name="web_search",
        subcommand="run",
        required_env=("BRAVE_API_KEY",),
        timeout_class="standard",
        timeout_seconds=60,
        skill_file=Path("skills/web-search/SKILL.md"),
        instructions="",
    )
    cli_tool = _DummyCliTool()

    tools = build_skill_tools(cli_tool, [skill], agent_id="System4/root")

    assert len(tools) == 1
    result = await tools[0].run_json(
        args={"arguments_json": json.dumps({"query": "cybernetic"})},
        cancellation_token=CancellationToken(),
    )

    assert result == {"success": True}
    assert len(cli_tool.calls) == 1
    call = cli_tool.calls[0]
    assert call["tool_name"] == "web_search"
    assert call["agent_id"] == "System4/root"
    assert call["subcommand"] == "run"
    assert call["timeout_seconds"] == 60
    assert call["query"] == "cybernetic"
