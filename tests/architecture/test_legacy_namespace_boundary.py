from __future__ import annotations

import importlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CYBERAGENT_RUNTIME_ROOTS = (
    REPO_ROOT / "src" / "cyberagent" / "cli",
    REPO_ROOT / "src" / "cyberagent" / "channels",
)


def test_runtime_paths_do_not_import_legacy_agent_namespaces() -> None:
    legacy_import = re.compile(r"^\s*(from|import)\s+src\.(agents|registry)(\.|$)")
    violations: list[str] = []

    for root in CYBERAGENT_RUNTIME_ROOTS:
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if legacy_import.search(line):
                    violations.append(f"{rel}:{index}: {line.strip()}")

    assert not violations, "Legacy agent imports found in runtime paths:\n" + "\n".join(
        violations
    )


def test_legacy_namespaces_wrap_canonical_modules() -> None:
    legacy_registry = importlib.import_module("src.registry")
    canonical_registry = importlib.import_module("src.cyberagent.agents.registry")
    assert legacy_registry.register_systems is canonical_registry.register_systems

    legacy_messages = importlib.import_module("src.agents.messages")
    canonical_messages = importlib.import_module("src.cyberagent.agents.messages")
    assert legacy_messages.UserMessage is canonical_messages.UserMessage
