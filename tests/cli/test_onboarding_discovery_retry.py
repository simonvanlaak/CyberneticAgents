from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest

from src.cyberagent.cli import onboarding_discovery
from src.cyberagent.tools.cli_executor.cli_tool import CliTool


def test_sync_repo_retries_after_interpreter_shutdown_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    def _fake_run_cli_tool(
        *_args: object, agent_id: str | None, **_kwargs: object
    ) -> dict[str, object]:
        assert agent_id == "System4/root"
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "success": False,
                "error": "cannot schedule new futures after interpreter shutdown",
            }
        return {"success": True}

    monkeypatch.setattr(onboarding_discovery, "_run_cli_tool", _fake_run_cli_tool)

    _, success = onboarding_discovery._sync_obsidian_repo(
        cli_tool=cast(CliTool, object()),
        agent_id="System4/root",
        repo_url="https://github.com/example/repo",
        branch="main",
        token_env="TOKEN",
        token_username="x-access-token",
    )

    assert success is True
    assert calls["count"] == 2


def test_sync_repo_falls_back_to_git_after_second_shutdown_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
    calls = {"count": 0}
    fallback_calls = {"count": 0}

    def _fake_run_cli_tool(
        *_args: object, agent_id: str | None, **_kwargs: object
    ) -> dict[str, object]:
        assert agent_id == "System4/root"
        calls["count"] += 1
        return {
            "success": False,
            "error": "cannot schedule new futures after interpreter shutdown",
        }

    def _fake_sync_with_git(**kwargs: object) -> tuple[bool, str | None]:
        fallback_calls["count"] += 1
        assert kwargs["repo_url"] == "https://github.com/example/repo"
        assert kwargs["branch"] == "main"
        assert cast(Path, kwargs["dest"]).name == "repo"
        return True, None

    monkeypatch.setattr(onboarding_discovery, "_run_cli_tool", _fake_run_cli_tool)
    monkeypatch.setattr(
        onboarding_discovery, "_sync_obsidian_repo_with_git", _fake_sync_with_git
    )
    monkeypatch.setattr(
        onboarding_discovery,
        "resolve_data_path",
        lambda *_parts: tmp_path / "obsidian" / "repo",
    )

    dest, success = onboarding_discovery._sync_obsidian_repo(
        cli_tool=cast(CliTool, object()),
        agent_id="System4/root",
        repo_url="https://github.com/example/repo",
        branch="main",
        token_env="TOKEN",
        token_username="x-access-token",
    )

    assert success is True
    assert dest == tmp_path / "obsidian" / "repo"
    assert calls["count"] == 2
    assert fallback_calls["count"] == 1
    assert os.environ.get("OBSIDIAN_VAULT_PATH") == str(dest.resolve())


def test_sync_repo_reports_git_fallback_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _fake_run_cli_tool(
        *_args: object, agent_id: str | None, **_kwargs: object
    ) -> dict[str, object]:
        assert agent_id == "System4/root"
        return {
            "success": False,
            "error": "cannot schedule new futures after interpreter shutdown",
        }

    monkeypatch.setattr(onboarding_discovery, "_run_cli_tool", _fake_run_cli_tool)
    monkeypatch.setattr(
        onboarding_discovery,
        "_sync_obsidian_repo_with_git",
        lambda **_kwargs: (False, "git fallback failed"),
    )

    _, success = onboarding_discovery._sync_obsidian_repo(
        cli_tool=cast(CliTool, object()),
        agent_id="System4/root",
        repo_url="https://github.com/example/repo",
        branch="main",
        token_env="TOKEN",
        token_username="x-access-token",
    )

    assert success is False
    assert "git fallback failed" in capsys.readouterr().out
