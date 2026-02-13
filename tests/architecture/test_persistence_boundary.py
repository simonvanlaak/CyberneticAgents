from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_application_flows_do_not_use_active_record_write_methods() -> None:
    """Application flows should not call model add()/update() directly."""

    banned_calls = {
        "task.add(": ["src/cyberagent/services/tasks.py"],
        "task.update(": [
            "src/cyberagent/services/tasks.py",
            "src/agents/system3.py",
        ],
        "strategy.add(": ["src/cyberagent/services/strategies.py"],
        "strategy.update(": ["src/cyberagent/services/strategies.py"],
        "initiative.add(": ["src/cyberagent/services/initiatives.py"],
        "initiative.update(": ["src/cyberagent/services/initiatives.py"],
        "purpose.update(": [
            "src/cyberagent/cli/onboarding_bootstrap.py",
            "src/cyberagent/cli/onboarding_output.py",
        ],
    }

    violations: list[str] = []
    for snippet, paths in banned_calls.items():
        for rel_path in paths:
            for index, line in enumerate(_read(rel_path).splitlines(), 1):
                if snippet in line:
                    violations.append(f"{rel_path}:{index}: {line.strip()}")

    assert not violations, "Active-record write usage detected:\n" + "\n".join(
        violations
    )


def test_selected_modules_use_session_context_not_next_get_db() -> None:
    """Persistence-oriented modules should use shared session context helper."""

    paths = [
        "src/cyberagent/services/tasks.py",
        "src/cyberagent/services/initiatives.py",
        "src/cyberagent/services/strategies.py",
        "src/cyberagent/cli/onboarding_bootstrap.py",
        "src/cyberagent/cli/onboarding_output.py",
        "src/cyberagent/db/models/task.py",
        "src/cyberagent/db/models/initiative.py",
        "src/cyberagent/db/models/strategy.py",
        "src/cyberagent/db/models/purpose.py",
    ]

    violations: list[str] = []
    for rel_path in paths:
        for index, line in enumerate(_read(rel_path).splitlines(), 1):
            if "next(get_db())" in line:
                violations.append(f"{rel_path}:{index}: {line.strip()}")

    assert not violations, "Direct next(get_db()) usage detected:\n" + "\n".join(
        violations
    )
