from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from src.cyberagent.tools.cli_executor import cli_tool as cli_tool_module
from src.cyberagent.tools.cli_executor.skill_loader import (
    SkillDefinition,
    load_skill_definitions,
    load_skill_instructions,
)
from src.cyberagent.tools.cli_executor.skill_tools import build_skill_tools


def _write_skill(
    root: Path, name: str, description: str = "Test skill", body: str = "Use it."
) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                "metadata:",
                "  cyberagent:",
                "    tool: demo_tool",
                "    subcommand: run",
                "    timeout_class: short",
                "    required_env:",
                "      - DEMO_TOKEN",
                "input_schema:",
                "  type: object",
                "  properties:",
                "    query:",
                "      type: string",
                "output_schema:",
                "  type: object",
                "  properties:",
                "    results:",
                "      type: array",
                "---",
                "",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_load_skill_definitions_and_instructions(tmp_path: Path) -> None:
    _write_skill(tmp_path, "demo-skill", body="Run demo.")
    skills = load_skill_definitions(tmp_path)
    assert len(skills) == 1
    skill = skills[0]
    assert skill.name == "demo-skill"
    assert skill.tool_name == "demo_tool"
    assert skill.subcommand == "run"
    assert skill.required_env == ("DEMO_TOKEN",)
    assert load_skill_instructions(skill) == "Run demo."


@dataclass
class _FakeResult:
    exit_code: int
    output: str


def test_cli_tool_build_args_and_parse_result() -> None:
    tool = cli_tool_module.CliTool(executor=object())
    args = tool._build_cli_args({"flag": True, "items": ["a", "b"], "q": "x"})
    assert "--flag" in args
    assert "--items a" in args
    assert "--items b" in args
    assert "--q x" in args
    parsed = tool._parse_result(_FakeResult(exit_code=0, output='{"ok": true}'))
    assert parsed["success"] is True
    assert parsed["output"]["ok"] is True


@pytest.mark.asyncio
async def test_build_skill_tools_rejects_invalid_args_json() -> None:
    skill = SkillDefinition(
        name="demo-skill",
        description="Demo",
        location=Path("skills/demo-skill"),
        tool_name="demo_tool",
        subcommand="run",
        required_env=(),
        timeout_class="short",
        timeout_seconds=30,
        input_schema={},
        output_schema={},
        skill_file=Path("skills/demo-skill/SKILL.md"),
        instructions="",
    )

    class DummyCliTool:
        async def execute(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {"success": True}

    tools = build_skill_tools(DummyCliTool(), [skill], agent_id="System4/root")
    runner = tools[0]._func
    result = await runner(arguments_json="not-json")
    assert result["success"] is False
    assert "Invalid arguments_json" in result["error"]
