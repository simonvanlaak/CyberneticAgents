from __future__ import annotations

from src.clarification_questions import build_clarification_prompt, should_post_prompt


def test_build_prompt_special_cases_agents_md() -> None:
    p = build_clarification_prompt(
        "Docs: clarify unexpected-change handling for agents",
        "Clarify AGENTS.md rule: do not stop on unrelated working tree changes",
    )
    assert "AGENTS.md" in p.body
    assert "stage:ready-to-implement" in p.body


def test_build_prompt_extracts_paths() -> None:
    p = build_clarification_prompt("x", "See docs/features/planned/task_flow.md")
    assert "docs/features/planned/task_flow.md" in p.body


def test_should_post_prompt_skips_exact_duplicate() -> None:
    body = "hello"
    assert should_post_prompt([body], body) is False
    assert should_post_prompt(["other"], body) is True
