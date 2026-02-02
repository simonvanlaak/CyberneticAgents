from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.tools.cli_executor.skill_loader import (
    load_skill_definitions,
    load_skill_instructions,
)


def _write_skill(root: Path, skill_name: str, body: str = "Use this skill.") -> None:
    skill_dir = root / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {skill_name}\n"
        "description: test skill\n"
        "metadata:\n"
        "  cyberagent:\n"
        "    tool: web_search\n"
        "    subcommand: run\n"
        "    required_env:\n"
        "      - BRAVE_API_KEY\n"
        "---\n\n"
        f"{body}\n",
        encoding="utf-8",
    )


def test_load_skill_definitions_reads_frontmatter(tmp_path: Path) -> None:
    _write_skill(tmp_path, "web-search")

    skills = load_skill_definitions(tmp_path)

    assert len(skills) == 1
    skill = skills[0]
    assert skill.name == "web-search"
    assert skill.tool_name == "web_search"
    assert skill.subcommand == "run"
    assert skill.required_env == ("BRAVE_API_KEY",)
    assert skill.instructions == ""


def test_load_skill_instructions_reads_markdown_body(tmp_path: Path) -> None:
    _write_skill(tmp_path, "web-fetch", body="Fetch and summarize pages.")
    skill = load_skill_definitions(tmp_path)[0]

    instructions = load_skill_instructions(skill)

    assert "Fetch and summarize pages." in instructions


def test_load_skill_definitions_rejects_missing_required_fields(
    tmp_path: Path,
) -> None:
    broken_dir = tmp_path / "broken"
    broken_dir.mkdir(parents=True, exist_ok=True)
    (broken_dir / "SKILL.md").write_text(
        "---\n" "name: broken\n" "---\n\n" "missing description\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="description"):
        load_skill_definitions(tmp_path)


def test_load_skill_definitions_rejects_invalid_name(tmp_path: Path) -> None:
    skill_dir = tmp_path / "bad--name"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n" "name: bad--name\n" "description: invalid name\n" "---\n\n" "body\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="name"):
        load_skill_definitions(tmp_path)


def test_load_skill_definitions_rejects_name_dir_mismatch(tmp_path: Path) -> None:
    skill_dir = tmp_path / "web-search"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n" "name: web-fetch\n" "description: mismatch\n" "---\n\n" "body\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="directory"):
        load_skill_definitions(tmp_path)


def test_load_skill_definitions_rejects_long_description(tmp_path: Path) -> None:
    skill_dir = tmp_path / "web-search"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n" "name: web-search\n" f"description: {'a' * 1025}\n" "---\n\n" "body\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="description"):
        load_skill_definitions(tmp_path)
