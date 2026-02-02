from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from autogen_core import CancellationToken

from src.cyberagent.core import runtime as core_runtime
from src.cyberagent.tools.cli_executor import factory, secrets, skill_tools
from src.cyberagent.tools.cli_executor.cli_tool import CliTool
from src.cyberagent.tools.cli_executor.docker_env_executor import (
    EnvDockerCommandLineCodeExecutor,
)
from src.cyberagent.tools.cli_executor.skill_loader import SkillDefinition


class _FakeExecutor:
    def __init__(self, output: str) -> None:
        self.output = output
        self.code_blocks = None
        self.envs: List[Dict[str, str]] = []

    def set_exec_env(self, env: Dict[str, str]) -> None:
        self.envs.append(env)

    async def execute_code_blocks(
        self, code_blocks: Any, cancellation_token: CancellationToken
    ) -> SimpleNamespace:
        self.code_blocks = code_blocks
        return SimpleNamespace(exit_code=0, output=self.output)


class _FakeContainer:
    def __init__(self, exit_code: int, output: str) -> None:
        self._exit_code = exit_code
        self._output = output
        self.last_command: List[str] | None = None
        self.last_env: Dict[str, str] | None = None

    def exec_run(self, command: List[str], **kwargs: Any) -> SimpleNamespace:
        self.last_command = command
        self.last_env = kwargs.get("environment")
        return SimpleNamespace(exit_code=self._exit_code, output=self._output.encode())


class _FakeRuntime:
    def __init__(self, tracer_provider: object | None = None) -> None:
        self.tracer_provider = tracer_provider
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    async def stop_when_idle(self) -> None:
        self.stopped = True


class _FakeLangfuse:
    def auth_check(self) -> bool:
        return True


class _FakeBatchSpanProcessor:
    def __init__(self, exporter: object) -> None:
        self.exporter = exporter


class _FakeTracerProvider:
    def __init__(self, resource: object) -> None:
        self.resource = resource
        self.processors: List[object] = []

    def add_span_processor(self, processor: object) -> None:
        self.processors.append(processor)


class _FakeExporter:
    def __init__(self, endpoint: str, headers: Dict[str, str]) -> None:
        self.endpoint = endpoint
        self.headers = headers


class _FakeDockerExecutor:
    def __init__(
        self, work_dir: str, image: str, container_name: str, auto_remove: bool
    ) -> None:
        self.work_dir = work_dir
        self.image = image
        self.container_name = container_name
        self.auto_remove = auto_remove


def _make_env_executor() -> EnvDockerCommandLineCodeExecutor:
    executor = EnvDockerCommandLineCodeExecutor.__new__(
        EnvDockerCommandLineCodeExecutor
    )
    executor._exec_env = {}
    executor._container = None
    executor._running = False
    executor._loop = None
    executor._cancellation_futures = []
    return executor


def test_configure_tracing_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    assert core_runtime.configure_tracing() is None


def test_configure_tracing_with_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://langfuse.test")

    monkeypatch.setattr(core_runtime, "Langfuse", _FakeLangfuse)
    monkeypatch.setattr(core_runtime, "BatchSpanProcessor", _FakeBatchSpanProcessor)
    monkeypatch.setattr(core_runtime, "TracerProvider", _FakeTracerProvider)
    monkeypatch.setattr(core_runtime, "OTLPSpanExporter", _FakeExporter)

    seen: Dict[str, object] = {}

    def _record(provider: object) -> None:
        seen["provider"] = provider

    monkeypatch.setattr(core_runtime.trace, "set_tracer_provider", _record)

    provider = core_runtime.configure_tracing()

    assert provider is seen["provider"]


def test_get_runtime_uses_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    created: Dict[str, object] = {}

    def _fake_factory():
        created["executor"] = "exec"
        return "exec"

    monkeypatch.setattr(core_runtime, "SingleThreadedAgentRuntime", _FakeRuntime)
    monkeypatch.setattr(core_runtime, "create_cli_executor", _fake_factory)
    core_runtime._runtime = None
    core_runtime._cli_executor = None

    runtime_instance = core_runtime.get_runtime()

    assert isinstance(runtime_instance, _FakeRuntime)
    assert runtime_instance.started is True
    assert created["executor"] == "exec"
    core_runtime._runtime = None
    core_runtime._cli_executor = None


@pytest.mark.asyncio
async def test_stop_runtime_resets() -> None:
    core_runtime._runtime = _FakeRuntime()

    await core_runtime.stop_runtime()

    assert core_runtime._runtime is None


def test_create_cli_executor_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLI_TOOLS_IMAGE", "example/image:tag")
    monkeypatch.setattr(
        factory, "EnvDockerCommandLineCodeExecutor", _FakeDockerExecutor
    )

    executor = factory.create_cli_executor()

    assert executor is not None
    assert executor.image == "example/image:tag"


def test_create_cli_executor_default_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLI_TOOLS_IMAGE", raising=False)
    monkeypatch.setattr(
        factory, "EnvDockerCommandLineCodeExecutor", _FakeDockerExecutor
    )

    executor = factory.create_cli_executor()

    assert executor is not None
    assert executor.image == "ghcr.io/simonvanlaak/cyberneticagents-cli-tools:latest"


def test_create_cli_executor_handles_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(factory, "EnvDockerCommandLineCodeExecutor", _raise)

    assert factory.create_cli_executor() is None


def test_tool_secrets_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)

    with pytest.raises(ValueError):
        secrets.get_tool_secrets("web_search")


def test_tool_secrets_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "token")

    assert secrets.get_tool_secrets("web_search") == {"BRAVE_API_KEY": "token"}
    assert secrets.get_tool_secrets("unknown_tool") == {}


def test_cli_tool_build_cli_args() -> None:
    tool = CliTool(_FakeExecutor("{}"))

    args = tool._build_cli_args({"query": "hello", "count": 2, "verbose": True})

    assert "--query hello" in args
    assert "--count 2" in args
    assert "--verbose" in args


def test_cli_tool_parse_result_json() -> None:
    tool = CliTool(_FakeExecutor("{}"))
    result = SimpleNamespace(exit_code=0, output=json.dumps({"ok": True}))

    parsed = tool._parse_result(result)

    assert parsed["success"] is True
    assert parsed["output"]["ok"] is True


def test_cli_tool_parse_result_error() -> None:
    tool = CliTool(_FakeExecutor("{}"))
    result = SimpleNamespace(exit_code=1, output="boom")

    parsed = tool._parse_result(result)

    assert parsed["success"] is False
    assert parsed["error"] == "boom"


@pytest.mark.asyncio
async def test_cli_tool_execute_sets_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "token")
    executor = _FakeExecutor(json.dumps({"ok": True}))
    tool = CliTool(executor)

    result = await tool.execute("web_search", query="x")

    assert result["success"] is True
    assert executor.envs[0] == {"BRAVE_API_KEY": "token"}
    assert executor.envs[-1] == {}
    assert executor.code_blocks is not None
    assert "web_search" in executor.code_blocks[0].code


def test_env_executor_injects_env() -> None:
    executor = _make_env_executor()
    executor.set_exec_env({"KEY": "VALUE"})

    assert executor._build_exec_env() == {"KEY": "VALUE"}


def test_env_executor_builds_empty_env() -> None:
    executor = _make_env_executor()

    assert executor._build_exec_env() == {}


@pytest.mark.asyncio
async def test_env_executor_requires_running() -> None:
    executor = _make_env_executor()

    with pytest.raises(ValueError):
        await executor._execute_command(["echo", "hi"], CancellationToken())


@pytest.mark.asyncio
async def test_env_executor_executes_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _make_env_executor()
    executor.set_exec_env({"KEY": "VALUE"})
    executor._container = _FakeContainer(0, "ok")
    executor._running = True
    executor._loop = asyncio.get_running_loop()
    executor._cancellation_futures = []

    async def _fake_to_thread(func: Any, *args: Any, **kwargs: Any) -> SimpleNamespace:
        return func(*args, **kwargs)

    monkeypatch.setattr(
        "src.cyberagent.tools.cli_executor.docker_env_executor.asyncio.to_thread",
        _fake_to_thread,
    )

    output, exit_code = await executor._execute_command(
        ["echo", "hi"], CancellationToken()
    )

    assert exit_code == 0
    assert output == "ok"
    assert executor._container.last_env == {"KEY": "VALUE"}


@pytest.mark.asyncio
async def test_build_skill_tools_runs_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: Dict[str, Any] = {}

    async def _execute(tool_name: str, **kwargs: Any) -> Dict[str, Any]:
        seen["tool_name"] = tool_name
        seen["kwargs"] = kwargs
        return {"success": True}

    skill = SkillDefinition(
        name="web-search",
        description="Search",
        location=Path("src/tools/skills/web-search"),
        tool_name="web_search",
        subcommand="run",
        required_env=(),
        skill_file=Path("src/tools/skills/web-search/SKILL.md"),
        instructions="",
    )

    tools = skill_tools.build_skill_tools(SimpleNamespace(execute=_execute), [skill])
    result = await tools[0].run_json(
        args={"arguments_json": json.dumps({"query": "x"})},
        cancellation_token=CancellationToken(),
    )

    assert result["success"] is True
    assert seen["tool_name"] == "web_search"
    assert seen["kwargs"]["subcommand"] == "run"
