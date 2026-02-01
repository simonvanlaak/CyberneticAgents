from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from autogen_core import CancellationToken

from src import runtime
from src.tools.cli_executor import factory, secrets
from src.tools.cli_executor.docker_env_executor import EnvDockerCommandLineCodeExecutor
from src.tools.cli_executor.openclaw_tool import OpenClawTool


class _FakeExecutor:
    def __init__(self, output: str) -> None:
        self.output = output
        self.code_blocks = None
        self.envs: List[Dict[str, str]] = []

    def set_exec_env(self, env: Dict[str, str]) -> None:
        self.envs.append(env)

    async def execute_code_blocks(self, code_blocks, cancellation_token):
        self.code_blocks = code_blocks
        return SimpleNamespace(exit_code=0, output=self.output)


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
        self, work_dir, image: str, container_name: str, auto_remove: bool
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

    assert runtime.configure_tracing() is None


def test_configure_tracing_with_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://langfuse.test")

    monkeypatch.setattr(runtime, "Langfuse", _FakeLangfuse)
    monkeypatch.setattr(runtime, "BatchSpanProcessor", _FakeBatchSpanProcessor)
    monkeypatch.setattr(runtime, "TracerProvider", _FakeTracerProvider)
    monkeypatch.setattr(runtime, "OTLPSpanExporter", _FakeExporter)

    seen: Dict[str, object] = {}

    def _record(provider: object) -> None:
        seen["provider"] = provider

    monkeypatch.setattr(runtime.trace, "set_tracer_provider", _record)

    provider = runtime.configure_tracing()

    assert provider is seen["provider"]


def test_get_runtime_uses_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    created: Dict[str, object] = {}

    def _fake_factory():
        created["executor"] = "exec"
        return "exec"

    monkeypatch.setattr(runtime, "SingleThreadedAgentRuntime", _FakeRuntime)
    monkeypatch.setattr(runtime, "create_cli_executor", _fake_factory)
    runtime._runtime = None
    runtime._cli_executor = None

    runtime_instance = runtime.get_runtime()

    assert isinstance(runtime_instance, _FakeRuntime)
    assert runtime_instance.started is True
    assert created["executor"] == "exec"
    runtime._runtime = None
    runtime._cli_executor = None


@pytest.mark.asyncio
async def test_stop_runtime_resets() -> None:
    runtime._runtime = _FakeRuntime()

    await runtime.stop_runtime()

    assert runtime._runtime is None


def test_create_cli_executor_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCLAW_TOOLS_IMAGE", "example/image:tag")
    monkeypatch.setattr(
        factory, "EnvDockerCommandLineCodeExecutor", _FakeDockerExecutor
    )

    executor = factory.create_cli_executor()

    assert executor is not None
    assert executor.image == "example/image:tag"


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


def test_openclaw_build_cli_args() -> None:
    tool = OpenClawTool(_FakeExecutor("{}"))

    args = tool._build_cli_args({"query": "hello", "count": 2, "verbose": True})

    assert "--query hello" in args
    assert "--count 2" in args
    assert "--verbose" in args


def test_openclaw_parse_result_json() -> None:
    tool = OpenClawTool(_FakeExecutor("{}"))
    result = SimpleNamespace(exit_code=0, output=json.dumps({"ok": True}))

    parsed = tool._parse_result(result)

    assert parsed["success"] is True
    assert parsed["output"]["ok"] is True


def test_openclaw_parse_result_error() -> None:
    tool = OpenClawTool(_FakeExecutor("{}"))
    result = SimpleNamespace(exit_code=1, output="boom")

    parsed = tool._parse_result(result)

    assert parsed["success"] is False
    assert parsed["error"] == "boom"


@pytest.mark.asyncio
async def test_openclaw_execute_sets_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "token")
    executor = _FakeExecutor(json.dumps({"ok": True}))
    tool = OpenClawTool(executor)

    result = await tool.execute("web_search", query="x")

    assert result["success"] is True
    assert executor.envs[0] == {"BRAVE_API_KEY": "token"}
    assert executor.envs[-1] == {}
    assert executor.code_blocks is not None
    assert "openclaw web_search" in executor.code_blocks[0].code


def test_env_executor_injects_env() -> None:
    executor = _make_env_executor()
    executor.set_exec_env({"KEY": "VALUE"})

    assert executor._build_exec_env() == {"KEY": "VALUE"}


@pytest.mark.asyncio
async def test_env_executor_requires_running() -> None:
    executor = _make_env_executor()

    with pytest.raises(ValueError):
        await executor._execute_command(["echo", "hi"], CancellationToken())
