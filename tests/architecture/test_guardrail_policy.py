from __future__ import annotations

from pathlib import Path

from src.cyberagent.architecture_guardrails import (
    ONBOARDING_LOC_GUARDRAILS,
    collect_legacy_import_violations,
    collect_loc_violations,
    collect_onboarding_callback_violations,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"


def test_cyberagent_blocks_legacy_imports_outside_compatibility() -> None:
    violations = collect_legacy_import_violations(SRC_ROOT / "cyberagent")
    assert violations == []


def test_legacy_import_guardrail_flags_forbidden_import(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "from src.agents.messages import UserMessage\n", encoding="utf-8"
    )

    violations = collect_legacy_import_violations(tmp_path)
    assert violations == [
        "bad.py:1: from src.agents.messages import UserMessage"
    ]


def test_onboarding_callback_guardrail_blocks_private_cross_imports() -> None:
    onboarding_dir = SRC_ROOT / "cyberagent" / "cli"
    violations = collect_onboarding_callback_violations(onboarding_dir)
    assert violations == []


def test_onboarding_callback_guardrail_detects_private_callback_imports(
    tmp_path: Path,
) -> None:
    (tmp_path / "onboarding_discovery.py").write_text(
        "from src.cyberagent.cli import onboarding as onboarding_cli\n"
        "onboarding_cli._apply_onboarding_output({}, 1)\n",
        encoding="utf-8",
    )

    violations = collect_onboarding_callback_violations(tmp_path)
    assert violations == [
        "onboarding_discovery.py:1: from src.cyberagent.cli import onboarding as onboarding_cli",
        "onboarding_discovery.py:2: onboarding_cli._apply_onboarding_output({}, 1)",
    ]


def test_onboarding_loc_guardrail_limits_key_orchestration_files() -> None:
    violations = collect_loc_violations(REPO_ROOT, ONBOARDING_LOC_GUARDRAILS)
    assert violations == []
