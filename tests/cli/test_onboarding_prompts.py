from __future__ import annotations

import argparse

import pytest

from src.cyberagent.cli import onboarding_prompts


def _base_args(**overrides: object) -> argparse.Namespace:
    data = {
        "user_name": "Test User",
        "pkm_source": "notion",
        "repo_url": "",
        "profile_links": [],
        "token_env": "GITHUB_READONLY_TOKEN",
        "token_username": "x-access-token",
    }
    data.update(overrides)
    return argparse.Namespace(**data)


def test_prompt_for_missing_inputs_notion_aborts_before_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _base_args()
    monkeypatch.setattr(onboarding_prompts, "check_notion_token", lambda: False)
    monkeypatch.setattr(
        "builtins.input",
        lambda *_: (_ for _ in ()).throw(AssertionError("Should not prompt")),
    )

    assert onboarding_prompts._prompt_for_missing_inputs(args) is False


def test_prompt_for_missing_inputs_github_prompts_repo_and_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _base_args(pkm_source="github")
    responses = iter(
        [
            "https://github.com/example/repo",
            "https://example.com/profile",
        ]
    )

    monkeypatch.setattr("builtins.input", lambda *_: next(responses))

    assert onboarding_prompts._prompt_for_missing_inputs(args) is True
    assert args.repo_url == "https://github.com/example/repo"
    assert args.profile_links == ["https://example.com/profile"]
