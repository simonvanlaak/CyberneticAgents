from __future__ import annotations

from typing import Any, Dict

import pytest

from src.cyberagent.tools.cli_executor.openclaw_tool import OpenClawTool


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

    executor = DummyExecutor()
    tool = OpenClawTool(executor)

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

    executor = DummyExecutor()
    tool = OpenClawTool(executor)

    result = await tool.execute("web_search", query="test")

    assert result["success"] is False
    assert "Missing required secrets for tool" in result["error"]


@pytest.mark.asyncio
async def test_execute_returns_error_on_rbac_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = DummyExecutor()
    tool = OpenClawTool(executor)

    monkeypatch.setattr(tool, "_check_permission", lambda *_args, **_kwargs: False)

    result = await tool.execute("web_search", agent_id="agent-1")

    assert result["success"] is False
    assert "not authorized" in result["error"]


@pytest.mark.asyncio
async def test_execute_without_env_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "brave")

    tool = OpenClawTool(NoEnvExecutor())
    result = await tool.execute("web_search", query="test")

    assert result["success"] is True


def test_parse_result_non_json() -> None:
    tool = OpenClawTool(NoEnvExecutor())
    result = tool._parse_result(
        type("obj", (object,), {"exit_code": 0, "output": "raw"})
    )

    assert result["success"] is True
    assert result["output"] == "raw"


def test_parse_result_json() -> None:
    tool = OpenClawTool(NoEnvExecutor())
    result = tool._parse_result(
        type("obj", (object,), {"exit_code": 0, "output": '{"ok": true}'})
    )

    assert result["success"] is True
    assert result["output"] == {"ok": True}


def test_parse_result_error() -> None:
    tool = OpenClawTool(NoEnvExecutor())
    result = tool._parse_result(
        type("obj", (object,), {"exit_code": 1, "output": "boom"})
    )

    assert result["success"] is False
    assert result["error"] == "boom"
