"""Runtime wiring for loading skills and exposing them as agent tools."""

from __future__ import annotations

from pathlib import Path

from autogen_core.tools import FunctionTool

from src.cyberagent.tools.cli_executor.cli_tool import CliTool
from src.cyberagent.tools.cli_executor.factory import create_cli_executor
from src.cyberagent.tools.cli_executor.skill_loader import (
    SkillDefinition,
    load_skill_definitions,
)
from src.cyberagent.tools.cli_executor.skill_tools import build_skill_tools
from src.cyberagent.db.models.system import get_system_from_agent_id
from src.cyberagent.services import systems as systems_service

DEFAULT_SKILLS_ROOT = Path("src/tools/skills")
MAX_AGENT_SKILLS = 5

_shared_cli_tool: CliTool | None = None


def get_agent_skill_tools(agent_id: str) -> list[FunctionTool]:
    """Return skill-backed FunctionTool objects for the given agent id."""
    cli_tool = _get_shared_cli_tool()
    if cli_tool is None:
        return []

    skills = load_skill_definitions(DEFAULT_SKILLS_ROOT)
    if not skills:
        return []
    filtered = _filter_granted_skills(skills, agent_id)
    if not filtered:
        return []
    return build_skill_tools(cli_tool, filtered[:MAX_AGENT_SKILLS], agent_id=agent_id)


def get_agent_skill_prompt_entries(agent_id: str) -> list[str]:
    """Return concise skill metadata lines for prompt injection."""
    if _get_shared_cli_tool() is None:
        return []

    skills = load_skill_definitions(DEFAULT_SKILLS_ROOT)
    if not skills:
        return []
    filtered = _filter_granted_skills(skills, agent_id)
    if not filtered:
        return []
    return [_format_skill_prompt_entry(skill) for skill in filtered[:MAX_AGENT_SKILLS]]


def _format_skill_prompt_entry(skill: SkillDefinition) -> str:
    location = skill.location.as_posix()
    return f"{skill.name}: {skill.description} (location: {location})"


def _filter_granted_skills(
    skills: list[SkillDefinition], agent_id: str
) -> list[SkillDefinition]:
    system = get_system_from_agent_id(agent_id)
    if system is None:
        return []
    granted = set(systems_service.list_granted_skills(system.id))
    if not granted:
        return []
    return [skill for skill in skills if skill.name in granted]


def _get_shared_cli_tool() -> CliTool | None:
    global _shared_cli_tool
    if _shared_cli_tool is not None:
        return _shared_cli_tool

    executor = create_cli_executor()
    if executor is None:
        return None
    _shared_cli_tool = CliTool(executor)
    return _shared_cli_tool
