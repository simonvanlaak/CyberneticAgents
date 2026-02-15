from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ONBOARDING_MODULES = (
    REPO_ROOT / "src/cyberagent/cli/onboarding.py",
    REPO_ROOT / "src/cyberagent/cli/onboarding_discovery.py",
)


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_onboarding_modules_stay_under_700_loc() -> None:
    for module_path in ONBOARDING_MODULES:
        assert (
            _line_count(module_path) <= 700
        ), f"{module_path.name} exceeds the 700 LOC limit"


def test_discovery_uses_shared_onboarding_output_service() -> None:
    discovery_source = (
        REPO_ROOT / "src/cyberagent/cli/onboarding_discovery.py"
    ).read_text(encoding="utf-8")

    assert "onboarding_cli._apply_onboarding_output" not in discovery_source
    assert (
        "from src.cyberagent.cli import onboarding as onboarding_cli"
        not in discovery_source
    )
    assert (
        "from src.cyberagent.cli.onboarding_output import apply_onboarding_output"
        in discovery_source
    )


def test_onboarding_module_does_not_reexport_patch_aliases() -> None:
    onboarding_source = (REPO_ROOT / "src/cyberagent/cli/onboarding.py").read_text(
        encoding="utf-8"
    )

    assert "_run_discovery_onboarding =" not in onboarding_source
    assert "_start_discovery_background =" not in onboarding_source
    assert "_build_onboarding_prompt =" not in onboarding_source
    assert "_trigger_onboarding_initiative =" not in onboarding_source
    assert "_load_runtime_pid = lambda" not in onboarding_source
    assert "_resolve_runtime_db_url = lambda" not in onboarding_source
