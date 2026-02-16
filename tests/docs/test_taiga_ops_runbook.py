from __future__ import annotations

from pathlib import Path


def test_taiga_ops_runbook_contains_required_mvp_sections() -> None:
    runbook_path = (
        Path(__file__).resolve().parents[2]
        / "docs/technical/taiga_compose_ops_runbook_2026-02-16.md"
    )

    assert runbook_path.exists(), "Expected Taiga ops runbook markdown file to exist."

    content = runbook_path.read_text(encoding="utf-8")

    required_snippets = [
        "docker compose -f docker-compose.taiga.yml --env-file .env.taiga up -d",
        "docker compose -f docker-compose.taiga.yml --env-file .env.taiga ps",
        "curl -f http://localhost:${TAIGA_PORT}/api/v1/",
        "pg_isready",
        "7 daily backups",
        "backup",
        "restore",
        "secrets out of git",
        "#119",
    ]

    for snippet in required_snippets:
        assert snippet in content
