from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.cli import onboarding_discovery


def _default_args() -> object:
    class Args:
        user_name = "Test User"
        repo_url = "https://github.com/example/repo"
        profile_links: list[str] = []
        token_env = "GITHUB_READONLY_TOKEN"
        token_username = "x-access-token"

    return Args()


def test_discovery_prompts_and_continues_without_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, str] = {}

    def _fake_write(summary_text: str) -> Path:
        captured["summary"] = summary_text
        return tmp_path / "summary.md"

    monkeypatch.setattr(
        onboarding_discovery, "_ensure_onboarding_token", lambda *_: False
    )
    monkeypatch.setattr(onboarding_discovery, "_create_cli_tool", lambda: object())
    monkeypatch.setattr(
        onboarding_discovery, "_fetch_profile_links", lambda *_: "profiles"
    )
    monkeypatch.setattr(onboarding_discovery, "_write_onboarding_summary", _fake_write)
    monkeypatch.setattr("builtins.input", lambda *_: "y")

    summary_path = onboarding_discovery.run_discovery_onboarding(_default_args())

    assert summary_path == tmp_path / "summary.md"
    assert "PKM sync skipped" in captured["summary"]


def test_discovery_aborts_without_token_when_declined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        onboarding_discovery, "_ensure_onboarding_token", lambda *_: False
    )
    monkeypatch.setattr(onboarding_discovery, "_create_cli_tool", lambda: object())
    monkeypatch.setattr("builtins.input", lambda *_: "n")

    summary_path = onboarding_discovery.run_discovery_onboarding(_default_args())

    assert summary_path is None


def test_discovery_aborts_on_sync_failure_when_declined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        onboarding_discovery, "_ensure_onboarding_token", lambda *_: True
    )
    monkeypatch.setattr(onboarding_discovery, "_create_cli_tool", lambda: object())
    monkeypatch.setattr(
        onboarding_discovery, "_resolve_default_branch", lambda *_: "main"
    )
    monkeypatch.setattr(
        onboarding_discovery, "_sync_obsidian_repo", lambda **_: (Path("x"), False)
    )
    monkeypatch.setattr("builtins.input", lambda *_: "no")

    summary_path = onboarding_discovery.run_discovery_onboarding(_default_args())

    assert summary_path is None


def test_discovery_continues_on_sync_failure_when_accepted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, str] = {}

    def _fake_write(summary_text: str) -> Path:
        captured["summary"] = summary_text
        return tmp_path / "summary.md"

    monkeypatch.setattr(
        onboarding_discovery, "_ensure_onboarding_token", lambda *_: True
    )
    monkeypatch.setattr(onboarding_discovery, "_create_cli_tool", lambda: object())
    monkeypatch.setattr(
        onboarding_discovery, "_resolve_default_branch", lambda *_: "main"
    )
    monkeypatch.setattr(
        onboarding_discovery, "_sync_obsidian_repo", lambda **_: (Path("x"), False)
    )
    monkeypatch.setattr(
        onboarding_discovery, "_fetch_profile_links", lambda *_: "profiles"
    )
    monkeypatch.setattr(onboarding_discovery, "_write_onboarding_summary", _fake_write)
    monkeypatch.setattr("builtins.input", lambda *_: "yes")

    summary_path = onboarding_discovery.run_discovery_onboarding(_default_args())

    assert summary_path == tmp_path / "summary.md"
    assert "PKM sync skipped" in captured["summary"]
