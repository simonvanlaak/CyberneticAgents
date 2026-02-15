from __future__ import annotations

from pathlib import Path


FORBIDDEN_SNIPPETS = (
    "gh api graphql",
    "gh project ",
)


def test_active_scripts_avoid_projects_graphql_calls() -> None:
    """Label-based automation should avoid Projects v2/GraphQL in active scripts."""

    repo_root = Path(__file__).resolve().parents[2]
    scripts_dir = repo_root / "scripts"

    active_scripts = list(scripts_dir.glob("*.sh"))

    for script in active_scripts:
        text = script.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_SNIPPETS:
            assert snippet not in text, f"{script} still contains forbidden snippet: {snippet}"
