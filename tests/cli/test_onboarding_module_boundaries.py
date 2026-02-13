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
