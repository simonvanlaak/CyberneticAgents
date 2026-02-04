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


def _stub_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    def _get_message(_group: str, key: str, **_kwargs: object) -> str:
        if key == "pkm_sync_skipped":
            return "PKM sync skipped. The onboarding interview will take longer without it."
        if key == "pkm_access_unavailable":
            return "We couldn't access your PKM vault yet."
        if key == "pkm_sync_failed":
            return "We couldn't sync your PKM vault."
        if key == "continue_without_pkm_prompt":
            return "Continue without PKM sync? [y/N]: "
        if key == "need_github_token":
            return "We need a GitHub read-only token to sync your private vault."
        if key == "store_github_token":
            return "Store it in 1Password."
        if key == "cli_tool_unavailable":
            return "CLI tool executor unavailable; cannot sync onboarding repo."
        if key == "failed_sync_repo":
            return "Failed to sync onboarding repo."
        if key == "onboarding_interview_longer":
            return "The onboarding interview will take longer without your PKM."
        return "msg"

    monkeypatch.setattr(onboarding_discovery, "get_message", _get_message)


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
    _stub_messages(monkeypatch)
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
    _stub_messages(monkeypatch)
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
    _stub_messages(monkeypatch)
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
    _stub_messages(monkeypatch)
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


def test_run_cli_tool_starts_and_stops_executor() -> None:
    class _FakeExecutor:
        def __init__(self) -> None:
            self.started = False
            self.stopped = False
            self._running = False

        async def start(self) -> None:
            self.started = True
            self._running = True

        async def stop(self) -> None:
            self.stopped = True
            self._running = False

    class _FakeCliTool:
        def __init__(self) -> None:
            self.executor = _FakeExecutor()

        async def execute(
            self, _tool_name: str, **_kwargs: object
        ) -> dict[str, object]:
            return {"success": True}

    cli_tool = _FakeCliTool()

    result = onboarding_discovery._run_cli_tool(cli_tool, "web-fetch", url="x")

    assert result["success"] is True
    assert cli_tool.executor.started is True
    assert cli_tool.executor.stopped is True
