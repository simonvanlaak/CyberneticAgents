from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"


def _iter_source_files() -> list[Path]:
    return sorted(path for path in SRC_ROOT.rglob("*.py") if path.is_file())


def test_no_legacy_src_cli_imports() -> None:
    legacy_import = re.compile(r"^\s*(from|import)\s+src\.cli(\.|$)")
    violations: list[str] = []

    for path in _iter_source_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if legacy_import.search(line):
                violations.append(f"{rel}:{index}: {line.strip()}")

    assert not violations, "Legacy src.cli imports found:\n" + "\n".join(violations)


def test_private_autogen_access_is_allowlisted() -> None:
    """
    Guardrail: private AutoGen internals may only be used in known bridge files.

    This allows the current transitional compatibility surface while preventing
    any new private-member usage from spreading.
    """

    private_patterns = [
        re.compile(r"runtime\._known_agent_names"),
        re.compile(r"self\._agent\._reflect_on_tool_use"),
        re.compile(r"self\._agent\._model_client"),
        re.compile(r"self\._agent\._workbench"),
        re.compile(r"self\._agent\._output_content_type"),
        re.compile(r"self\._agent\._system_messages"),
    ]
    allowlist = {
        "src/agents/system_base.py": {
            "self._agent._reflect_on_tool_use",
            "self._agent._model_client",
            "self._agent._workbench",
            "self._agent._output_content_type",
            "self._agent._system_messages",
        },
    }
    violations: list[str] = []

    for path in _iter_source_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        allowed_tokens = allowlist.get(rel, set())
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern in private_patterns:
                if not pattern.search(line):
                    continue
                token = pattern.pattern.replace("\\", "")
                if token in allowed_tokens:
                    continue
                violations.append(f"{rel}:{index}: {line.strip()}")

    assert (
        not violations
    ), "New private AutoGen member usage detected outside allowlist:\n" + "\n".join(
        violations
    )
