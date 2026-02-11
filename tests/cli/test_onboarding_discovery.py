from __future__ import annotations

import asyncio
import os
from pathlib import Path
import threading

from typing import Any, cast
import pytest

from src.cyberagent.cli import onboarding_discovery
from src.cyberagent.tools.cli_executor.cli_tool import CliTool


class _Args:
    def __init__(self) -> None:
        self.user_name = "Test User"
        self.pkm_source = "github"
        self.repo_url = "https://github.com/example/repo"
        self.profile_links: list[str] = []
        self.token_env = "GITHUB_READONLY_TOKEN"
        self.token_username = "x-access-token"


def _default_args() -> _Args:
    return _Args()


def _stub_system4(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeSystem:
        agent_id_str = "System4/root"

    monkeypatch.setattr(
        onboarding_discovery,
        "get_system_by_type",
        lambda *_args, **_kwargs: _FakeSystem(),
    )


def _stub_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    def _get_message(_group: str, key: str, **_kwargs: object) -> str:
        if key == "pkm_sync_skipped":
            return "PKM sync skipped. The onboarding interview will take longer without it."
        if key == "pkm_access_unavailable":
            return "We couldn't access your PKM vault yet."
        if key == "pkm_sync_failed":
            return "We couldn't sync your PKM vault."
        if key == "pkm_sync_starting":
            return "Syncing your PKM vault..."
        if key == "pkm_sync_still_running":
            return "Still syncing your PKM vault..."
        if key == "onepassword_cli_not_ready":
            return "1Password CLI authentication failed."
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


def test_prepare_obsidian_vault_path_env_sets_expected_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
    expected = (tmp_path / "obsidian" / "repo").resolve()
    monkeypatch.setattr(
        onboarding_discovery, "resolve_data_path", lambda *_parts: expected
    )

    resolved = onboarding_discovery.prepare_obsidian_vault_path_env(
        pkm_source="github",
        repo_url="https://github.com/example/repo",
    )

    assert resolved == str(expected)
    assert os.environ.get("OBSIDIAN_VAULT_PATH") == str(expected)


def test_prepare_obsidian_vault_path_env_skips_non_github(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)

    resolved = onboarding_discovery.prepare_obsidian_vault_path_env(
        pkm_source="notion",
        repo_url="https://github.com/example/repo",
    )

    assert resolved is None
    assert os.environ.get("OBSIDIAN_VAULT_PATH") is None


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
    monkeypatch.setattr(onboarding_discovery, "has_onepassword_auth", lambda: False)
    monkeypatch.setattr(
        onboarding_discovery,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: (None, "1Password CLI not authenticated."),
    )
    monkeypatch.setattr(onboarding_discovery, "_create_cli_tool", lambda: object())
    _stub_system4(monkeypatch)
    monkeypatch.setattr(
        onboarding_discovery,
        "_fetch_profile_links",
        lambda *_args, **_kwargs: "profiles",
    )
    monkeypatch.setattr(onboarding_discovery, "_write_onboarding_summary", _fake_write)
    monkeypatch.setattr("builtins.input", lambda *_: "y")

    summary_path = onboarding_discovery.run_discovery_onboarding(
        _default_args(), team_id=1
    )

    assert summary_path == tmp_path / "summary.md"
    assert "PKM sync skipped" in captured["summary"]


def test_discovery_aborts_without_token_when_declined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        onboarding_discovery, "_ensure_onboarding_token", lambda *_: False
    )
    _stub_messages(monkeypatch)
    monkeypatch.setattr(onboarding_discovery, "has_onepassword_auth", lambda: False)
    monkeypatch.setattr(
        onboarding_discovery,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: (None, "1Password CLI not authenticated."),
    )
    monkeypatch.setattr(onboarding_discovery, "_create_cli_tool", lambda: object())
    _stub_system4(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *_: "n")

    summary_path = onboarding_discovery.run_discovery_onboarding(
        _default_args(), team_id=1
    )

    assert summary_path is None


def test_discovery_aborts_on_sync_failure_when_declined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        onboarding_discovery, "_ensure_onboarding_token", lambda *_: True
    )
    _stub_messages(monkeypatch)
    monkeypatch.setattr(onboarding_discovery, "has_onepassword_auth", lambda: False)
    monkeypatch.setattr(
        onboarding_discovery,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: ("token", None),
    )
    monkeypatch.setattr(onboarding_discovery, "_create_cli_tool", lambda: object())
    _stub_system4(monkeypatch)
    monkeypatch.setattr(
        onboarding_discovery, "_resolve_default_branch", lambda *_: "main"
    )
    monkeypatch.setattr(
        onboarding_discovery, "_sync_obsidian_repo", lambda **_: (Path("x"), False)
    )
    monkeypatch.setattr("builtins.input", lambda *_: "no")

    summary_path = onboarding_discovery.run_discovery_onboarding(
        _default_args(), team_id=1
    )

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
    monkeypatch.setattr(onboarding_discovery, "has_onepassword_auth", lambda: False)
    monkeypatch.setattr(
        onboarding_discovery,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: ("token", None),
    )
    monkeypatch.setattr(onboarding_discovery, "_create_cli_tool", lambda: object())
    _stub_system4(monkeypatch)
    monkeypatch.setattr(
        onboarding_discovery, "_resolve_default_branch", lambda *_: "main"
    )
    monkeypatch.setattr(
        onboarding_discovery, "_sync_obsidian_repo", lambda **_: (Path("x"), False)
    )
    monkeypatch.setattr(
        onboarding_discovery,
        "_fetch_profile_links",
        lambda *_args, **_kwargs: "profiles",
    )
    monkeypatch.setattr(onboarding_discovery, "_write_onboarding_summary", _fake_write)
    monkeypatch.setattr("builtins.input", lambda *_: "yes")

    summary_path = onboarding_discovery.run_discovery_onboarding(
        _default_args(), team_id=1
    )

    assert summary_path == tmp_path / "summary.md"
    assert "PKM sync skipped" in captured["summary"]


def test_discovery_notion_prompts_and_continues_without_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, str] = {}

    def _fake_write(summary_text: str) -> Path:
        captured["summary"] = summary_text
        return tmp_path / "summary.md"

    args = _default_args()
    args.pkm_source = "notion"
    args.repo_url = ""

    monkeypatch.setattr(onboarding_discovery, "_ensure_notion_token", lambda *_: False)
    _stub_messages(monkeypatch)
    monkeypatch.setattr(onboarding_discovery, "has_onepassword_auth", lambda: False)
    monkeypatch.setattr(
        onboarding_discovery,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: (None, "1Password CLI not authenticated."),
    )
    monkeypatch.setattr(onboarding_discovery, "_create_cli_tool", lambda: object())
    _stub_system4(monkeypatch)
    monkeypatch.setattr(
        onboarding_discovery,
        "_fetch_profile_links",
        lambda *_args, **_kwargs: "profiles",
    )
    monkeypatch.setattr(onboarding_discovery, "_write_onboarding_summary", _fake_write)
    monkeypatch.setattr("builtins.input", lambda *_: "y")

    summary_path = onboarding_discovery.run_discovery_onboarding(args, team_id=1)

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

    result = onboarding_discovery._run_cli_tool(
        cli_tool, "web-fetch", agent_id="System4/root", url="x"
    )

    assert result["success"] is True
    assert cli_tool.executor.started is True
    assert cli_tool.executor.stopped is True


def test_start_discovery_background_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: dict[str, bool] = {"value": False}

    class _FakeThread:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def start(self) -> None:
            started["value"] = True

    monkeypatch.setenv("CYBERAGENT_DISABLE_BACKGROUND_DISCOVERY", "1")
    monkeypatch.setattr(threading, "Thread", _FakeThread)

    onboarding_discovery.start_discovery_background(_default_args(), team_id=1)

    assert started["value"] is False


def test_start_discovery_background_starts_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: dict[str, bool] = {"value": False}

    class _FakeThread:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def start(self) -> None:
            started["value"] = True

    monkeypatch.delenv("CYBERAGENT_DISABLE_BACKGROUND_DISCOVERY", raising=False)
    monkeypatch.setattr(threading, "Thread", _FakeThread)

    onboarding_discovery.start_discovery_background(_default_args(), team_id=1)

    assert started["value"] is True


def test_start_discovery_background_calls_on_complete_with_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")
    calls: list[Path] = []

    class _FakeThread:
        def __init__(
            self,
            *,
            target: object,
            kwargs: dict[str, object] | None = None,
            **_kw: object,
        ) -> None:
            self._target = target
            self._kwargs = kwargs or {}

        def start(self) -> None:
            assert callable(self._target)
            self._target(**self._kwargs)

    monkeypatch.delenv("CYBERAGENT_DISABLE_BACKGROUND_DISCOVERY", raising=False)
    monkeypatch.setattr(threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        onboarding_discovery, "_run_discovery_pipeline", lambda **_kwargs: summary_path
    )

    onboarding_discovery.start_discovery_background(
        _default_args(),
        team_id=1,
        on_complete=lambda resolved_path: calls.append(resolved_path),
    )

    assert calls == [summary_path]


def test_prompt_continue_without_pkm_handles_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_messages(monkeypatch)
    monkeypatch.setattr(onboarding_discovery, "has_onepassword_auth", lambda: False)

    def _raise_eof(*_args: object, **_kwargs: object) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)

    assert onboarding_discovery._prompt_continue_without_pkm("reason") is False


def test_run_cli_tool_returns_error_when_start_fails() -> None:
    class _FailExecutor:
        def __init__(self) -> None:
            self._running = False

        async def start(self) -> None:
            raise RuntimeError("start failed")

    class _FakeCliTool:
        def __init__(self) -> None:
            self.executor = _FailExecutor()

        async def execute(
            self, _tool_name: str, **_kwargs: object
        ) -> dict[str, object]:
            return {"success": True}

    cli_tool = _FakeCliTool()

    result = onboarding_discovery._run_cli_tool(
        cli_tool, "web-fetch", agent_id="System4/root", url="x"
    )

    assert result["success"] is False
    assert "start failed" in str(result["error"])


def test_ensure_onboarding_token_reports_op_auth_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_messages(monkeypatch)
    monkeypatch.delenv("GITHUB_READONLY_TOKEN", raising=False)
    monkeypatch.setattr(onboarding_discovery, "has_onepassword_auth", lambda: True)
    monkeypatch.setattr(
        onboarding_discovery,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: (None, "not signed in"),
    )
    monkeypatch.setattr(
        onboarding_discovery,
        "check_onepassword_cli_access",
        lambda: (False, "not signed in"),
    )

    assert (
        onboarding_discovery._ensure_onboarding_token("GITHUB_READONLY_TOKEN") is False
    )
    captured = capsys.readouterr().out
    assert "1Password CLI authentication failed" in captured


def test_sync_repo_uses_kebab_case_token_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_run_cli_tool(*_args: object, **kwargs: object) -> dict[str, object]:
        assert kwargs["agent_id"] == "System4/root"
        captured.update(kwargs)
        return {"success": True}

    monkeypatch.setattr(onboarding_discovery, "_run_cli_tool", _fake_run_cli_tool)

    onboarding_discovery._sync_obsidian_repo(
        cli_tool=cast(CliTool, object()),
        agent_id="System4/root",
        repo_url="https://github.com/example/repo",
        branch="main",
        token_env="GITHUB_READONLY_TOKEN",
        token_username="x-access-token",
    )

    assert "token-env" in captured
    assert "token-username" in captured
    assert "token_env" not in captured
    assert "token_username" not in captured


def test_sync_repo_reports_stderr_when_error_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _fake_run_cli_tool(
        *_args: object, agent_id: str | None, **_kwargs: object
    ) -> dict[str, object]:
        assert agent_id == "System4/root"
        return {"success": False, "stderr": "boom"}

    monkeypatch.setattr(onboarding_discovery, "_run_cli_tool", _fake_run_cli_tool)

    onboarding_discovery._sync_obsidian_repo(
        cli_tool=cast(CliTool, object()),
        agent_id="System4/root",
        repo_url="https://github.com/example/repo",
        branch="main",
        token_env="TOKEN",
        token_username="x-access-token",
    )

    captured = capsys.readouterr().out
    assert "boom" in captured


def test_fetch_profile_links_calls_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def _fake_run_cli_tool(
        *_args: object, agent_id: str | None, **_kwargs: object
    ) -> dict[str, object]:
        assert agent_id == "System4/root"
        return {"success": True, "output": {"content": "Profile content"}}

    def _on_entry(link: str, content: str) -> None:
        calls.append((link, content))

    monkeypatch.setattr(onboarding_discovery, "_run_cli_tool", _fake_run_cli_tool)

    summary = onboarding_discovery._fetch_profile_links(
        cli_tool=cast(CliTool, object()),
        links=["https://example.com/profile"],
        agent_id="System4/root",
        on_entry=_on_entry,
    )

    assert "Profile content" in summary
    assert calls == [("https://example.com/profile", "Profile content")]


def test_discovery_repo_sync_stores_split_markdown_memory_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = _default_args()
    repo_dir = tmp_path / "repo"
    (repo_dir / "notes").mkdir(parents=True)
    (repo_dir / "notes" / "alpha.md").write_text(
        "# Alpha\nAlpha line 1\nAlpha line 2\n", encoding="utf-8"
    )
    (repo_dir / "notes" / "beta.md").write_text(
        "# Beta\nBeta line 1\nBeta line 2\n", encoding="utf-8"
    )
    captured_entries: list[dict[str, object]] = []

    monkeypatch.setattr(
        onboarding_discovery, "_ensure_onboarding_token", lambda *_: True
    )
    _stub_messages(monkeypatch)
    monkeypatch.setattr(onboarding_discovery, "has_onepassword_auth", lambda: False)
    monkeypatch.setattr(
        onboarding_discovery,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: ("token", None),
    )
    monkeypatch.setattr(onboarding_discovery, "_create_cli_tool", lambda: object())
    _stub_system4(monkeypatch)
    monkeypatch.setattr(
        onboarding_discovery, "_resolve_default_branch", lambda *_: "main"
    )
    monkeypatch.setattr(
        onboarding_discovery, "_sync_obsidian_repo", lambda **_: (repo_dir, True)
    )
    monkeypatch.setattr(
        onboarding_discovery,
        "_fetch_profile_links",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        onboarding_discovery, "store_onboarding_memory", lambda *_: None
    )
    monkeypatch.setattr(onboarding_discovery, "enqueue_suggestion", lambda *_: None)
    monkeypatch.setattr(
        onboarding_discovery,
        "_write_onboarding_summary",
        lambda _text: tmp_path / "summary.md",
    )

    def _capture_store_entry(
        *,
        team_id: int,
        content: str,
        tags: list[str],
        source: object,
        priority: object,
        layer: object,
        namespace: str = "user",
        confidence: float = 0.6,
    ) -> bool:
        captured_entries.append(
            {
                "team_id": team_id,
                "content": content,
                "tags": tags,
                "namespace": namespace,
                "confidence": confidence,
            }
        )
        return True

    monkeypatch.setattr(
        onboarding_discovery, "store_onboarding_memory_entry", _capture_store_entry
    )
    monkeypatch.setattr(
        onboarding_discovery,
        "fetch_onboarding_memory_contents",
        lambda *_args, **_kwargs: [
            cast(str, entry["content"]) for entry in captured_entries
        ],
    )

    summary_path = onboarding_discovery.run_discovery_onboarding(args, team_id=1)

    assert summary_path == tmp_path / "summary.md"
    pkm_overview = [
        entry for entry in captured_entries if entry["tags"] == ["onboarding", "pkm"]
    ]
    assert len(pkm_overview) == 1
    pkm_file_entries = [
        entry
        for entry in captured_entries
        if "pkm_file" in cast(list[str], entry["tags"])
    ]
    assert len(pkm_file_entries) == 2
    contents = [cast(str, entry["content"]) for entry in pkm_file_entries]
    assert any("PKM file: notes/alpha.md" in content for content in contents)
    assert any("PKM file: notes/beta.md" in content for content in contents)
    captured = capsys.readouterr().out
    assert "PKM memory verification (obsidian): 3/3 entries verified." in captured


def test_discovery_notion_sync_stores_split_item_memory_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args = _default_args()
    args.pkm_source = "notion"
    args.repo_url = ""
    captured_entries: list[dict[str, object]] = []

    monkeypatch.setattr(onboarding_discovery, "_ensure_notion_token", lambda *_: True)
    _stub_messages(monkeypatch)
    monkeypatch.setattr(onboarding_discovery, "has_onepassword_auth", lambda: False)
    monkeypatch.setattr(
        onboarding_discovery,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: ("token", None),
    )
    monkeypatch.setattr(onboarding_discovery, "_create_cli_tool", lambda: object())
    _stub_system4(monkeypatch)
    monkeypatch.setattr(
        onboarding_discovery,
        "_sync_notion_workspace",
        lambda **_: (
            "Notion items analyzed: 2\n- [page] A\n- [database] B",
            ["Notion item: [page] A", "Notion item: [database] B"],
            True,
        ),
    )
    monkeypatch.setattr(
        onboarding_discovery,
        "_fetch_profile_links",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        onboarding_discovery, "store_onboarding_memory", lambda *_: None
    )
    monkeypatch.setattr(onboarding_discovery, "enqueue_suggestion", lambda *_: None)
    monkeypatch.setattr(
        onboarding_discovery,
        "_write_onboarding_summary",
        lambda _text: tmp_path / "summary.md",
    )

    def _capture_store_entry(
        *,
        team_id: int,
        content: str,
        tags: list[str],
        source: object,
        priority: object,
        layer: object,
        namespace: str = "user",
        confidence: float = 0.6,
    ) -> None:
        captured_entries.append(
            {
                "team_id": team_id,
                "content": content,
                "tags": tags,
                "namespace": namespace,
                "confidence": confidence,
            }
        )

    monkeypatch.setattr(
        onboarding_discovery, "store_onboarding_memory_entry", _capture_store_entry
    )

    summary_path = onboarding_discovery.run_discovery_onboarding(args, team_id=1)

    assert summary_path == tmp_path / "summary.md"
    pkm_overview = [
        entry for entry in captured_entries if entry["tags"] == ["onboarding", "pkm"]
    ]
    assert len(pkm_overview) == 1
    pkm_item_entries = [
        entry
        for entry in captured_entries
        if "pkm_notion_item" in cast(list[str], entry["tags"])
    ]
    assert len(pkm_item_entries) == 2
    contents = [cast(str, entry["content"]) for entry in pkm_item_entries]
    assert any("Notion item: [page] A" in content for content in contents)
    assert any("Notion item: [database] B" in content for content in contents)


def test_sync_repo_reports_unknown_error_when_missing_details(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _fake_run_cli_tool(
        *_args: object, agent_id: str | None, **_kwargs: object
    ) -> dict[str, object]:
        assert agent_id == "System4/root"
        return {"success": False}

    monkeypatch.setattr(onboarding_discovery, "_run_cli_tool", _fake_run_cli_tool)

    onboarding_discovery._sync_obsidian_repo(
        cli_tool=cast(CliTool, object()),
        agent_id="System4/root",
        repo_url="https://github.com/example/repo",
        branch="main",
        token_env="TOKEN",
        token_username="x-access-token",
    )

    captured = capsys.readouterr().out
    assert "Unknown error" in captured


def test_sync_repo_passes_timeout_to_cli_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_run_cli_tool(*_args: object, **kwargs: object) -> dict[str, object]:
        assert kwargs["agent_id"] == "System4/root"
        captured.update(kwargs)
        return {"success": True}

    monkeypatch.setattr(onboarding_discovery, "_run_cli_tool", _fake_run_cli_tool)

    onboarding_discovery._sync_obsidian_repo(
        cli_tool=cast(CliTool, object()),
        agent_id="System4/root",
        repo_url="https://github.com/example/repo",
        branch="main",
        token_env="GITHUB_READONLY_TOKEN",
        token_username="x-access-token",
    )

    assert "timeout_seconds" in captured
    assert captured["timeout_seconds"] == onboarding_discovery.GIT_SYNC_TIMEOUT_SECONDS


def test_run_cli_tool_returns_timeout_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyTool:
        executor = None

        async def execute(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {"success": True}

    async def _fake_wait_for(*_args: object, **_kwargs: object) -> dict[str, object]:
        coro = cast(Any, _args[0])
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        raise asyncio.TimeoutError

    monkeypatch.setattr(onboarding_discovery.asyncio, "wait_for", _fake_wait_for)

    result = onboarding_discovery._run_cli_tool(
        DummyTool(),
        "git-readonly-sync",
        agent_id="System4/root",
        timeout_seconds=1,
    )

    assert result["success"] is False
    assert result["error"] == "Timeout"


def test_build_onboarding_prompt_truncates_large_summary_text() -> None:
    summary_path = Path("data/onboarding/20260209_120000/summary.md")
    oversized_summary = "A" * (
        onboarding_discovery.ONBOARDING_PROMPT_SUMMARY_CHAR_LIMIT + 200
    )

    prompt = onboarding_discovery.build_onboarding_prompt(
        summary_path=summary_path,
        summary_text=oversized_summary,
    )

    assert "Summary truncated for prompt" in prompt
    assert str(summary_path) in prompt


def test_build_onboarding_interview_prompt_includes_question_cap() -> None:
    prompt = onboarding_discovery.build_onboarding_interview_prompt(
        user_name="Simon",
        pkm_source="github",
        repo_url="https://github.com/example/repo",
        profile_links=["https://example.com/profile"],
        first_question="What is your primary outcome?",
    )

    assert "Ask no more than 10 questions total" in prompt
