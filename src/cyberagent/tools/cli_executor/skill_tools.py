"""Factory helpers that expose loaded skills as AutoGen tools."""

from __future__ import annotations

import json
from typing import Any

from autogen_core.tools import FunctionTool

from src.cyberagent.tools.cli_executor.skill_loader import SkillDefinition


def build_skill_tools(
    cli_tool: Any,
    skills: list[SkillDefinition],
    agent_id: str | None = None,
) -> list[FunctionTool]:
    """Create one FunctionTool wrapper for each loaded skill."""
    tools: list[FunctionTool] = []
    for skill in skills:
        runner = _build_skill_runner(cli_tool, skill, agent_id)
        tool_name = skill.name.replace("-", "_")
        tools.append(FunctionTool(runner, skill.description, name=tool_name))
    return tools


def _build_skill_runner(cli_tool: Any, skill: SkillDefinition, agent_id: str | None):
    async def run_skill(arguments_json: str = "{}") -> dict[str, Any]:
        try:
            arguments = json.loads(arguments_json)
        except json.JSONDecodeError as exc:
            return {"success": False, "error": f"Invalid arguments_json: {exc}"}
        if not isinstance(arguments, dict):
            return {
                "success": False,
                "error": "arguments_json must decode to an object.",
            }
        return await cli_tool.execute(
            skill.tool_name,
            agent_id=agent_id,
            subcommand=skill.subcommand,
            timeout_seconds=getattr(skill, "timeout_seconds", None),
            skill_name=skill.name,
            required_env=list(skill.required_env),
            **arguments,
        )

    run_skill.__name__ = f"run_{skill.name.replace('-', '_')}"
    run_skill.__doc__ = skill.description
    return run_skill
