"""Skill loading helpers for Agent Skills style SKILL.md files."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SkillDefinition:
    """Runtime metadata for a single skill."""

    name: str
    description: str
    location: Path
    tool_name: str
    subcommand: str | None
    required_env: tuple[str, ...]
    timeout_class: str
    timeout_seconds: int
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    skill_file: Path
    instructions: str


TIMEOUTS_BY_CLASS = {
    "short": 30,
    "standard": 60,
    "long": 180,
}


def load_skill_definitions(skills_root: Path | str) -> list[SkillDefinition]:
    """
    Load skill metadata from subfolders containing ``SKILL.md``.

    This loads only frontmatter metadata to keep startup lightweight.
    """
    root = Path(skills_root)
    if not root.exists():
        return []

    skills: list[SkillDefinition] = []
    for skill_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        frontmatter, _ = _parse_skill_file(skill_file)
        skills.append(_build_skill_definition(skill_dir, skill_file, frontmatter))
    return skills


def load_skill_instructions(skill: SkillDefinition) -> str:
    """Load the full Markdown instructions body for a skill."""
    _frontmatter, body = _parse_skill_file(skill.skill_file)
    return body


def _parse_skill_file(skill_file: Path) -> tuple[dict[str, Any], str]:
    content = skill_file.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        raise ValueError(f"{skill_file} is missing YAML frontmatter.")

    parts = content.split("\n---\n", 1)
    if len(parts) != 2:
        raise ValueError(f"{skill_file} has invalid frontmatter delimiters.")

    frontmatter_raw = parts[0].replace("---\n", "", 1)
    body = parts[1].strip()
    frontmatter = yaml.safe_load(frontmatter_raw) or {}
    if not isinstance(frontmatter, dict):
        raise ValueError(f"{skill_file} frontmatter must be a mapping.")
    return frontmatter, body


def _build_skill_definition(
    skill_dir: Path, skill_file: Path, frontmatter: dict[str, Any]
) -> SkillDefinition:
    name = str(frontmatter.get("name", "")).strip()
    description = str(frontmatter.get("description", "")).strip()
    if not name:
        raise ValueError(f"{skill_file} is missing required field 'name'.")
    if not description:
        raise ValueError(f"{skill_file} is missing required field 'description'.")
    _validate_skill_name(name, skill_dir, skill_file)
    _validate_description(description, skill_file)

    metadata = _as_mapping(frontmatter.get("metadata", {}))
    cyberagent = _as_mapping(metadata.get("cyberagent", {}))

    tool_name = str(cyberagent.get("tool", name.replace("-", "_")))
    subcommand_raw = cyberagent.get("subcommand")
    subcommand = str(subcommand_raw) if subcommand_raw else None
    required_env_raw = cyberagent.get("required_env", [])
    required_env = tuple(str(key) for key in required_env_raw)
    timeout_class = str(cyberagent.get("timeout_class", "standard")).strip()
    timeout_seconds = _resolve_timeout_seconds(timeout_class, skill_file)
    input_schema = _schema_or_empty(frontmatter.get("input_schema"), skill_file)
    output_schema = _schema_or_empty(frontmatter.get("output_schema"), skill_file)

    return SkillDefinition(
        name=name,
        description=description,
        location=skill_dir,
        tool_name=tool_name,
        subcommand=subcommand,
        required_env=required_env,
        timeout_class=timeout_class,
        timeout_seconds=timeout_seconds,
        input_schema=input_schema,
        output_schema=output_schema,
        skill_file=skill_file,
        instructions="",
    )


def _validate_skill_name(name: str, skill_dir: Path, skill_file: Path) -> None:
    if len(name) > 64:
        raise ValueError(f"{skill_file} skill name must be 1-64 characters.")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError(
            f"{skill_file} skill name must be lowercase letters, numbers, "
            "and single hyphens only."
        )
    if name != skill_dir.name:
        raise ValueError(
            f"{skill_file} skill name must match directory '{skill_dir.name}'."
        )


def _validate_description(description: str, skill_file: Path) -> None:
    if len(description) > 1024:
        raise ValueError(f"{skill_file} description must be 1-1024 characters.")


def _resolve_timeout_seconds(timeout_class: str, skill_file: Path) -> int:
    if timeout_class not in TIMEOUTS_BY_CLASS:
        raise ValueError(
            f"{skill_file} timeout_class must be one of: "
            f"{', '.join(sorted(TIMEOUTS_BY_CLASS))}."
        )
    return TIMEOUTS_BY_CLASS[timeout_class]


def _schema_or_empty(value: Any, skill_file: Path) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{skill_file} schema must be a mapping.")
    return value


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
