from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.tools.cli_executor import skill_runtime
from src.cyberagent.tools.cli_executor.skill_loader import SkillDefinition


def _make_skill(name: str) -> SkillDefinition:
    return SkillDefinition(
        name=name,
        description=f"{name} desc",
        location=Path(f"src/tools/skills/{name}"),
        tool_name="exec",
        subcommand=None,
        required_env=(),
        timeout_class="standard",
        timeout_seconds=60,
        input_schema={"properties": {"query": {"type": "string"}}},
        output_schema={"properties": {"results": {"type": "array"}}},
        skill_file=Path(f"src/tools/skills/{name}/SKILL.md"),
        instructions="",
    )


def test_get_agent_skill_tools_returns_empty_when_no_cli_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(skill_runtime, "_shared_cli_tool", None)
    monkeypatch.setattr(skill_runtime, "_get_shared_cli_tool", lambda: None)

    tools = skill_runtime.get_agent_skill_tools("System4/root")

    assert tools == []


def test_get_agent_skill_tools_applies_max_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skills = [_make_skill(f"skill-{i}") for i in range(7)]
    monkeypatch.setattr(
        skill_runtime,
        "get_system_from_agent_id",
        lambda _agent_id: type("obj", (), {"id": 1}),
    )
    monkeypatch.setattr(
        skill_runtime,
        "systems_service",
        type(
            "obj",
            (),
            {"list_granted_skills": lambda _system_id: [s.name for s in skills]},
        ),
    )
    monkeypatch.setattr(skill_runtime, "_get_shared_cli_tool", lambda: object())
    monkeypatch.setattr(skill_runtime, "load_skill_definitions", lambda _root: skills)

    built_count = {"count": 0}

    def _build(_tool, loaded_skills, agent_id: str):
        built_count["count"] = len(loaded_skills)
        return []

    monkeypatch.setattr(skill_runtime, "build_skill_tools", _build)

    skill_runtime.get_agent_skill_tools("System4/root")

    assert built_count["count"] == skill_runtime.MAX_AGENT_SKILLS


def test_get_agent_skill_tools_returns_empty_when_no_grants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skills = [_make_skill("skill-0")]
    monkeypatch.setattr(
        skill_runtime,
        "get_system_from_agent_id",
        lambda _agent_id: type("obj", (), {"id": 1}),
    )
    monkeypatch.setattr(
        skill_runtime,
        "systems_service",
        type("obj", (), {"list_granted_skills": lambda _system_id: []}),
    )
    monkeypatch.setattr(skill_runtime, "_get_shared_cli_tool", lambda: object())
    monkeypatch.setattr(skill_runtime, "load_skill_definitions", lambda _root: skills)

    assert skill_runtime.get_agent_skill_tools("System4/root") == []


def test_get_agent_skill_prompt_entries_include_locations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skills = [_make_skill(f"skill-{i}") for i in range(2)]
    monkeypatch.setattr(
        skill_runtime,
        "get_system_from_agent_id",
        lambda _agent_id: type("obj", (), {"id": 1}),
    )
    monkeypatch.setattr(
        skill_runtime,
        "systems_service",
        type(
            "obj",
            (),
            {"list_granted_skills": lambda _system_id: [s.name for s in skills]},
        ),
    )
    monkeypatch.setattr(skill_runtime, "_shared_cli_tool", object())
    monkeypatch.setattr(skill_runtime, "_get_shared_cli_tool", lambda: object())
    monkeypatch.setattr(skill_runtime, "load_skill_definitions", lambda _root: skills)

    entries = skill_runtime.get_agent_skill_prompt_entries("System4/root")

    assert "skill-0" in entries[0]
    assert "skill-0 desc" in entries[0]
    assert "src/tools/skills/skill-0" in entries[0]
    assert "inputs:" in entries[0]
    assert "outputs:" in entries[0]
