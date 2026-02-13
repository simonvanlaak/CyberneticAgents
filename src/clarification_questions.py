from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ClarificationPrompt:
    title: str
    body: str


def _extract_paths(text: str) -> list[str]:
    # Very small heuristic: look for markdown-ish paths.
    candidates = set(re.findall(r"(?:^|\s)([\w./-]+\.(?:md|py|sh|toml|json))", text, flags=re.M))
    cleaned: list[str] = []
    for c in sorted(candidates):
        c = c.strip()
        if not c or c.startswith("http"):
            continue
        cleaned.append(c)
    return cleaned


def build_clarification_prompt(issue_title: str, issue_body: str) -> ClarificationPrompt:
    """Build a more specific clarification prompt.

    This intentionally avoids LLM usage: it's a deterministic heuristic template.
    """

    issue_body = (issue_body or "").strip()
    paths = _extract_paths(issue_body)

    lines: list[str] = [
        "stage:needs-clarification",
        "",
        f"Ticket: {issue_title}",
        "",
        "To implement this correctly, please answer:",
    ]

    # Heuristic specialization
    lower = (issue_title + "\n" + issue_body).lower()
    if "agents.md" in lower:
        lines += [
            "1) Which section(s) of AGENTS.md should change? (quote headings if possible)",
            "2) Provide the exact wording to add/remove (preferred), or a short example.",
            "3) What is the success criterion? e.g. which scenario should no longer block the agent?",
        ]
    else:
        lines += [
            "1) Expected outcome (what should be different?)",
            "2) Acceptance criteria (bullet list)",
            "3) Constraints (if any)",
            "4) How to test (commands + expected results)",
        ]

    if paths:
        lines += [
            "",
            "I noticed these referenced paths (confirm if relevant):",
            *[f"- {p}" for p in paths[:10]],
        ]

    lines += [
        "",
        "When done, set label to: stage:ready-to-implement",
    ]

    return ClarificationPrompt(title="Clarification needed", body="\n".join(lines).strip() + "\n")


def should_post_prompt(last_comment_bodies: Sequence[str], new_prompt_body: str) -> bool:
    """Avoid spamming duplicates: if the most recent comment already contains this exact prompt, skip."""

    if not last_comment_bodies:
        return True
    last = (last_comment_bodies[0] or "").strip()
    return last != (new_prompt_body or "").strip()
