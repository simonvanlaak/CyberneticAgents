from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence

LEGACY_IMPORT_PATTERN = re.compile(r"^\s*(from|import)\s+src\.(agents|registry)(\.|$)")

ALLOWED_LEGACY_IMPORT_PATHS = {
    "agents/messages.py",
    "agents/registry.py",
    "agents/user_agent.py",
}

ONBOARDING_CALLBACK_BANNED_PATTERNS: Sequence[re.Pattern[str]] = (
    re.compile(r"from\s+src\.cyberagent\.cli\s+import\s+onboarding\s+as\s+onboarding_cli"),
    re.compile(r"onboarding_cli\._apply_onboarding_output\("),
)

ONBOARDING_LOC_GUARDRAILS: tuple[tuple[str, int], ...] = (
    ("src/cyberagent/cli/onboarding.py", 700),
    ("src/cyberagent/cli/onboarding_discovery.py", 700),
)


def collect_legacy_import_violations(root: Path) -> list[str]:
    """Collect forbidden legacy namespace imports under ``root``."""

    violations: list[str] = []
    normalized_root = root.resolve()

    for path in sorted(normalized_root.rglob("*.py")):
        rel = path.relative_to(normalized_root).as_posix()
        if rel in ALLOWED_LEGACY_IMPORT_PATHS:
            continue
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if LEGACY_IMPORT_PATTERN.search(line):
                violations.append(f"{rel}:{index}: {line.strip()}")

    return violations


def collect_onboarding_callback_violations(root: Path) -> list[str]:
    """Collect onboarding files that use private cross-module callback imports."""

    violations: list[str] = []
    normalized_root = root.resolve()

    for path in sorted(normalized_root.rglob("onboarding*.py")):
        rel = path.relative_to(normalized_root).as_posix()
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern in ONBOARDING_CALLBACK_BANNED_PATTERNS:
                if pattern.search(line):
                    violations.append(f"{rel}:{index}: {line.strip()}")
                    break

    return violations


def collect_loc_violations(
    repo_root: Path, guardrails: Iterable[tuple[str, int]]
) -> list[str]:
    """Collect Python files that exceed their configured line-count limits."""

    violations: list[str] = []
    for relative_path, max_lines in guardrails:
        path = (repo_root / relative_path).resolve()
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > max_lines:
            violations.append(
                f"{relative_path}: {line_count} lines (max {max_lines})"
            )
    return violations
