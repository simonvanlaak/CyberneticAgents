from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CYBERAGENT_RUNTIME_ROOTS = (
    REPO_ROOT / "src" / "cyberagent" / "cli",
    REPO_ROOT / "src" / "cyberagent" / "channels",
)
CYBERAGENT_ROOT = REPO_ROOT / "src" / "cyberagent"


def test_runtime_paths_do_not_import_legacy_agent_namespaces() -> None:
    legacy_import = re.compile(r"^\s*(from|import)\s+src\.(agents|registry)(\.|$)")
    violations: list[str] = []

    for root in CYBERAGENT_RUNTIME_ROOTS:
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            for index, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if legacy_import.search(line):
                    violations.append(f"{rel}:{index}: {line.strip()}")

    assert not violations, "Legacy agent imports found in runtime paths:\n" + "\n".join(
        violations
    )


def test_cyberagent_namespace_is_fully_detached_from_legacy_namespaces() -> None:
    legacy_import = re.compile(
        r"^\s*(from|import)\s+src\.(agents|rbac|tools|registry)(?=\.|\s|$)"
    )
    violations: list[str] = []

    for path in sorted(CYBERAGENT_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if legacy_import.search(line):
                violations.append(f"{rel}:{index}: {line.strip()}")

    assert (
        not violations
    ), "Legacy namespace imports found in src/cyberagent:\n" + "\n".join(violations)
