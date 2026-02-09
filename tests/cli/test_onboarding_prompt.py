from pathlib import Path

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.cli import onboarding_discovery


def test_build_onboarding_prompt_includes_summary_path() -> None:
    prompt = onboarding_cli._build_onboarding_prompt(
        summary_path=Path("data/onboarding/20260204_120000/summary.md"),
        summary_text="Summary content here.",
    )
    assert "Onboarding Summary" in prompt
    assert "data/onboarding/20260204_120000/summary.md" in prompt


def test_build_onboarding_prompt_truncates_large_summary() -> None:
    large_summary = "X" * (
        onboarding_discovery.ONBOARDING_PROMPT_SUMMARY_CHAR_LIMIT + 50
    )

    prompt = onboarding_cli._build_onboarding_prompt(
        summary_path=Path("data/onboarding/20260204_120000/summary.md"),
        summary_text=large_summary,
    )

    assert "Summary truncated for prompt" in prompt
    assert (
        len(prompt) < onboarding_discovery.ONBOARDING_PROMPT_SUMMARY_CHAR_LIMIT + 1000
    )
