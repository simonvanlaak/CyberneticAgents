from pathlib import Path

from src.cyberagent.cli import onboarding as onboarding_cli


def test_build_onboarding_prompt_includes_summary_path() -> None:
    prompt = onboarding_cli._build_onboarding_prompt(
        summary_path=Path("data/onboarding/20260204_120000/summary.md"),
        summary_text="Summary content here.",
    )
    assert "Onboarding Summary" in prompt
    assert "data/onboarding/20260204_120000/summary.md" in prompt
