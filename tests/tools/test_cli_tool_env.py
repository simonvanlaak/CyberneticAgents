from __future__ import annotations

from typing import Any, Dict

import pytest

from src.cyberagent.tools.cli_executor.cli_tool import CliTool


class DummyExecutor:
    def __init__(self) -> None:
        self.exec_env: Dict[str, str] | None = None
        self.env_history: list[Dict[str, str]] = []
        self.execute_calls: int = 0

    def set_exec_env(self, exec_env: Dict[str, str]) -> None:
        self.exec_env = exec_env
        self.env_history.append(dict(exec_env))

    async def execute_code_blocks(self, code_blocks, **_kwargs) -> Any:
        self.execute_calls += 1
        return type(
            "obj",
            (object,),
            {"exit_code": 0, "output": '{"ok": true}', "code_file": "tmp"},
        )


class NoEnvExecutor:
    async def execute_code_blocks(self, code_blocks, **_kwargs) -> Any:
        return type(
            "obj",
            (object,),
            {"exit_code": 0, "output": "plain", "code_file": "tmp"},
        )


@pytest.mark.asyncio
async def test_execute_injects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "brave")
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")

    executor = DummyExecutor()
    tool = CliTool(executor)

    result = await tool.execute("web_search", query="test")

    assert result["success"] is True
    assert executor.exec_env == {}
    assert executor.env_history == [{"BRAVE_API_KEY": "brave"}, {}]
    assert executor.execute_calls == 1


@pytest.mark.asyncio
async def test_execute_returns_error_on_missing_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")

    executor = DummyExecutor()
    tool = CliTool(executor)

    result = await tool.execute("web_search", query="test")

    assert result["success"] is False
    assert "Missing required secrets for tool" in result["error"]


@pytest.mark.asyncio
async def test_execute_requires_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_TOKEN", raising=False)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")

    executor = DummyExecutor()
    tool = CliTool(executor)

    result = await tool.execute(
        "git_readonly_sync",
        token_env="GIT_TOKEN",
        repo="https://example.com/repo.git",
        dest="repo",
    )

    assert result["success"] is False
    assert "GIT_TOKEN" in result["error"]


@pytest.mark.asyncio
async def test_execute_accepts_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_TOKEN", "token")
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")

    executor = DummyExecutor()
    tool = CliTool(executor)

    result = await tool.execute(
        "git_readonly_sync",
        token_env="GIT_TOKEN",
        repo="https://example.com/repo.git",
        dest="repo",
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_execute_returns_error_on_rbac_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = DummyExecutor()
    tool = CliTool(executor)

    monkeypatch.setattr(tool, "_check_permission", lambda *_args, **_kwargs: False)

    result = await tool.execute("web_search", agent_id="agent-1")

    assert result["success"] is False
    assert "not authorized" in result["error"]


@pytest.mark.asyncio
async def test_execute_without_env_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "brave")
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")

    tool = CliTool(NoEnvExecutor())
    result = await tool.execute("web_search", query="test")

    assert result["success"] is True


def test_parse_result_non_json() -> None:
    tool = CliTool(NoEnvExecutor())
    result = tool._parse_result(
        type("obj", (object,), {"exit_code": 0, "output": "raw"})
    )

    assert result["success"] is True
    assert result["output"] == "raw"


def test_parse_result_json() -> None:
    tool = CliTool(NoEnvExecutor())
    result = tool._parse_result(
        type("obj", (object,), {"exit_code": 0, "output": '{"ok": true}'})
    )

    assert result["success"] is True
    assert result["output"] == {"ok": True}


def test_parse_result_error() -> None:
    tool = CliTool(NoEnvExecutor())
    result = tool._parse_result(
        type("obj", (object,), {"exit_code": 1, "output": "boom"})
    )

    assert result["success"] is False
    assert result["error"] == "boom"
