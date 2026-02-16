from __future__ import annotations

from pathlib import Path


def test_planka_migration_scope_doc_exists_with_required_sections() -> None:
    doc_path = (
        Path(__file__).resolve().parents[2]
        / "docs/technical/planka_migration_scope_decision_2026-02-16.md"
    )

    assert doc_path.exists(), "Expected Planka migration scope decision doc to exist."

    content = doc_path.read_text(encoding="utf-8")

    required_snippets = [
        "Ticket: #130",
        "Taiga UI",
        "Taiga adapter/worker",
        "GitHub `stage:*` labels",
        "| Planka primitive | Maps from Taiga | Purpose in CyberneticAgents |",
        "| Project | Taiga Project |",
        "| Board | Taiga board/workflow view |",
        "| List | Taiga task status column |",
        "| Card | Taiga task |",
        "Phase 1 — Scope + contracts",
        "Phase 2 — Runtime migration",
        "Phase 3 — Operator cutover",
    ]

    for snippet in required_snippets:
        assert snippet in content
