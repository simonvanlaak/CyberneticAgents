from __future__ import annotations

from pathlib import Path


def test_planka_env_template_contains_required_keys() -> None:
    env_template_path = Path(__file__).resolve().parents[2] / ".env.planka.example"

    assert env_template_path.exists(), "Expected .env.planka.example to exist."

    content = env_template_path.read_text(encoding="utf-8")

    required_keys = [
        "PLANKA_PUBLIC_BIND=",
        "PLANKA_PUBLIC_PORT=",
        "PLANKA_BASE_URL=",
        "PLANKA_SECRET_KEY=",
        "PLANKA_DB_NAME=",
        "PLANKA_DB_USER=",
        "PLANKA_DB_PASSWORD=",
        "PLANKA_DEFAULT_ADMIN_EMAIL=",
        "PLANKA_DEFAULT_ADMIN_USERNAME=",
        "PLANKA_DEFAULT_ADMIN_NAME=",
        "PLANKA_DEFAULT_ADMIN_PASSWORD=",
    ]

    for key in required_keys:
        assert key in content


def test_planka_runbook_references_env_template_and_backup_restore() -> None:
    runbook_path = (
        Path(__file__).resolve().parents[2]
        / "docs/technical/planka_compose_ops_runbook_2026-02-16.md"
    )

    assert runbook_path.exists(), "Expected Planka ops runbook markdown file to exist."

    content = runbook_path.read_text(encoding="utf-8")

    required_snippets = [
        "cp .env.planka.example .env.planka",
        "docker compose -f docker-compose.planka.yml --env-file .env.planka up -d",
        "7 daily backups",
        "Restore DB dump",
        "Restore data archive",
        "#131",
    ]

    for snippet in required_snippets:
        assert snippet in content
