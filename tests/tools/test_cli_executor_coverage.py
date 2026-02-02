from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from autogen_core import CancellationToken

from src.cyberagent.core import runtime as core_runtime
from src.cyberagent.tools.cli_executor import (
    factory,
    secrets,
    skill_runtime,
    skill_tools,
)
from src.cyberagent.tools.cli_executor.cli_tool import CliTool
from src.cyberagent.tools.cli_executor.cli_tool import _set_executor_timeout
from src.cyberagent.tools.cli_executor.docker_env_executor import (
    EnvDockerCommandLineCodeExecutor,
)
from src.cyberagent.tools.cli_executor.skill_loader import (
    SkillDefinition,
    load_skill_definitions,
    load_skill_instructions,
)


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
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")

    with pytest.raises(ValueError):
        secrets.get_tool_secrets("web_search")


def test_tool_secrets_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "token")
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")

    assert secrets.get_tool_secrets("web_search") == {"BRAVE_API_KEY": "token"}

    assert secrets.get_tool_secrets("unknown_tool") == {}


def test_tool_secrets_merges_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "token")
    monkeypatch.setenv("EXTRA_KEY", "extra")
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")

    result = secrets.get_tool_secrets("web_search", required_env=["EXTRA_KEY"])

    assert result["BRAVE_API_KEY"] == "token"
    assert result["EXTRA_KEY"] == "extra"


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
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")
    executor = _FakeExecutor(json.dumps({"ok": True}))
    tool = CliTool(executor)

    result = await tool.execute("web_search", query="x")

    assert result["success"] is True
    assert executor.envs[0] == {"BRAVE_API_KEY": "token"}
    assert executor.envs[-1] == {}
    assert executor.code_blocks is not None
    assert "web_search" in executor.code_blocks[0].code


@pytest.mark.asyncio
async def test_cli_tool_execute_requires_token_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")
    monkeypatch.delenv("GIT_TOKEN", raising=False)
    executor = _FakeExecutor(json.dumps({"ok": True}))
    tool = CliTool(executor)

    result = await tool.execute(
        "git_readonly_sync",
        token_env="GIT_TOKEN",
        repo="https://example.com/repo.git",
        dest="repo",
    )

    assert result["success"] is False
    assert "GIT_TOKEN" in result["error"]


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
async def test_env_executor_executes_command(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = _make_env_executor()
    executor.set_exec_env({"KEY": "VALUE"})
    executor._container = _FakeContainer(0, "ok")
    executor._running = True
    executor._loop = asyncio.get_running_loop()
    executor._cancellation_futures = []

    async def _fake_to_thread(func, *args, **kwargs):
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


def _make_skill_definition(name: str) -> SkillDefinition:
    return SkillDefinition(
        name=name,
        description=f"{name} description",
        location=Path(f"src/tools/skills/{name}"),
        tool_name=name.replace("-", "_"),
        subcommand=None,
        required_env=(),
        timeout_class="standard",
        timeout_seconds=60,
        input_schema={"properties": {"query": {"type": "string"}}},
        output_schema={"properties": {"results": {"type": "array"}}},
        skill_file=Path(f"src/tools/skills/{name}/SKILL.md"),
        instructions="",
    )


def _write_skill(root: Path, name: str, body: str = "Use this skill.") -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "description: test skill\n"
        "metadata:\n"
        "  cyberagent:\n"
        "    tool: web_search\n"
        "    subcommand: run\n"
        "    required_env:\n"
        "      - BRAVE_API_KEY\n"
        "input_schema:\n"
        "  type: object\n"
        "  properties:\n"
        "    query:\n"
        "      type: string\n"
        "output_schema:\n"
        "  type: object\n"
        "  properties:\n"
        "    results:\n"
        "      type: array\n"
        "---\n\n"
        f"{body}\n",
        encoding="utf-8",
    )


def test_load_skill_definitions_reads_frontmatter(tmp_path: Path) -> None:
    _write_skill(tmp_path, "web-search")

    skills = load_skill_definitions(tmp_path)

    assert len(skills) == 1
    skill = skills[0]
    assert skill.name == "web-search"
    assert skill.tool_name == "web_search"
    assert skill.subcommand == "run"
    assert skill.required_env == ("BRAVE_API_KEY",)
    assert skill.input_schema["properties"]["query"]["type"] == "string"
    assert skill.output_schema["properties"]["results"]["type"] == "array"


def test_load_skill_instructions_reads_body(tmp_path: Path) -> None:
    _write_skill(tmp_path, "web-fetch", body="Fetch and summarize pages.")
    skill = load_skill_definitions(tmp_path)[0]

    instructions = load_skill_instructions(skill)

    assert "Fetch and summarize pages." in instructions


def test_get_agent_skill_tools_returns_empty_when_no_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(skill_runtime, "_shared_cli_tool", None)
    monkeypatch.setattr(skill_runtime, "_get_shared_cli_tool", lambda: None)

    tools = skill_runtime.get_agent_skill_tools("System4/root")

    assert tools == []


def test_get_agent_skill_tools_applies_max_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skills = [_make_skill_definition(f"skill-{i}") for i in range(7)]
    monkeypatch.setattr(
        skill_runtime,
        "get_system_from_agent_id",
        lambda _agent_id: type("obj", (), {"id": 1}),
    )
    monkeypatch.setattr(
        skill_runtime,
        "systems_service",
        type(
            "obj",
            (),
            {"list_granted_skills": lambda _system_id: [s.name for s in skills]},
        ),
    )
    monkeypatch.setattr(skill_runtime, "_get_shared_cli_tool", lambda: object())
    monkeypatch.setattr(skill_runtime, "load_skill_definitions", lambda _root: skills)

    built_count = {"count": 0}

    def _build(_tool, loaded_skills, agent_id: str):
        built_count["count"] = len(loaded_skills)
        return []

    monkeypatch.setattr(skill_runtime, "build_skill_tools", _build)

    skill_runtime.get_agent_skill_tools("System4/root")

    assert built_count["count"] == skill_runtime.MAX_AGENT_SKILLS


def test_get_agent_skill_prompt_entries_include_locations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skills = [_make_skill_definition(f"skill-{i}") for i in range(2)]
    monkeypatch.setattr(
        skill_runtime,
        "get_system_from_agent_id",
        lambda _agent_id: type("obj", (), {"id": 1}),
    )
    monkeypatch.setattr(
        skill_runtime,
        "systems_service",
        type(
            "obj",
            (),
            {"list_granted_skills": lambda _system_id: [s.name for s in skills]},
        ),
    )
    monkeypatch.setattr(skill_runtime, "_shared_cli_tool", object())
    monkeypatch.setattr(skill_runtime, "_get_shared_cli_tool", lambda: object())
    monkeypatch.setattr(skill_runtime, "load_skill_definitions", lambda _root: skills)

    entries = skill_runtime.get_agent_skill_prompt_entries("System4/root")

    assert "skill-0" in entries[0]
    assert "skill-0 description" in entries[0]
    assert "src/tools/skills/skill-0" in entries[0]


def test_get_agent_skill_tools_returns_empty_when_no_skills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        skill_runtime,
        "get_system_from_agent_id",
        lambda _agent_id: type("obj", (), {"id": 1}),
    )
    monkeypatch.setattr(
        skill_runtime,
        "systems_service",
        type("obj", (), {"list_granted_skills": lambda _system_id: ["skill-1"]}),
    )
    monkeypatch.setattr(skill_runtime, "_get_shared_cli_tool", lambda: object())
    monkeypatch.setattr(skill_runtime, "load_skill_definitions", lambda _root: [])

    assert skill_runtime.get_agent_skill_tools("System4/root") == []


def test_get_shared_cli_tool_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, int] = {"count": 0}

    def _fake_factory():
        created["count"] += 1
        return object()

    monkeypatch.setattr(skill_runtime, "create_cli_executor", _fake_factory)
    skill_runtime._shared_cli_tool = None

    first = skill_runtime._get_shared_cli_tool()
    second = skill_runtime._get_shared_cli_tool()

    assert first is second
    assert created["count"] == 1


@pytest.mark.asyncio
async def test_build_skill_tools_invokes_cli_tool() -> None:
    class _DummyCliTool:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def execute(self, tool_name: str, **kwargs: Any) -> dict[str, Any]:
            self.calls.append({"tool_name": tool_name, **kwargs})
            return {"success": True}

    skill = _make_skill_definition("web-search")
    cli_tool = _DummyCliTool()

    tools = skill_tools.build_skill_tools(cli_tool, [skill], agent_id="System4/root")

    assert len(tools) == 1
    result = await tools[0].run_json(
        args={"arguments_json": json.dumps({"query": "cybernetic"})},
        cancellation_token=CancellationToken(),
    )

    assert result == {"success": True}
    assert len(cli_tool.calls) == 1
    call = cli_tool.calls[0]
    assert call["tool_name"] == "web_search"
    assert call["agent_id"] == "System4/root"
    assert call["skill_name"] == "web-search"
    assert call["query"] == "cybernetic"


@pytest.mark.asyncio
async def test_build_skill_tools_rejects_bad_arguments() -> None:
    class _DummyCliTool:
        async def execute(self, tool_name: str, **kwargs: Any) -> dict[str, Any]:
            return {"success": True}

    skill = _make_skill_definition("web-search")
    cli_tool = _DummyCliTool()
    tools = skill_tools.build_skill_tools(cli_tool, [skill])

    result = await tools[0].run_json(
        args={"arguments_json": "not json"},
        cancellation_token=CancellationToken(),
    )

    assert result["success"] is False


@pytest.mark.asyncio
async def test_build_skill_tools_rejects_non_mapping_arguments() -> None:
    class _DummyCliTool:
        async def execute(self, tool_name: str, **kwargs: Any) -> dict[str, Any]:
            return {"success": True}

    skill = _make_skill_definition("web-search")
    cli_tool = _DummyCliTool()
    tools = skill_tools.build_skill_tools(cli_tool, [skill])

    result = await tools[0].run_json(
        args={"arguments_json": json.dumps(["not", "a", "dict"])},
        cancellation_token=CancellationToken(),
    )

    assert result["success"] is False


@pytest.mark.asyncio
async def test_cli_tool_execute_denies_skill_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cyberagent.tools.cli_executor import cli_tool as cli_tool_module

    class _DummySystem:
        id = 42
        team_id = 7

    class _RecordingExecutor:
        def __init__(self) -> None:
            self.executed = False

        async def execute_code_blocks(self, *args, **kwargs):
            self.executed = True
            return SimpleNamespace(exit_code=0, output="{}")

    monkeypatch.setattr(
        cli_tool_module, "get_system_from_agent_id", lambda _a: _DummySystem
    )
    monkeypatch.setattr(
        cli_tool_module.systems_service,
        "can_execute_skill",
        lambda _sid, _skill: (False, "team_envelope"),
    )

    tool = CliTool(_RecordingExecutor())
    tool._check_permission = lambda *_args, **_kwargs: True

    result = await tool.execute(
        "web_search",
        agent_id="System4/root",
        skill_name="web-search",
        query="x",
    )

    assert result["success"] is False
    assert result["details"]["team_id"] == 7
    assert result["details"]["system_id"] == 42
    assert result["details"]["skill_name"] == "web-search"
    assert result["details"]["failed_rule_category"] == "team_envelope"
    assert tool.executor.executed is False


@pytest.mark.asyncio
async def test_cli_tool_execute_denies_skill_permission_top_level_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cyberagent.tools.cli_executor import cli_tool as cli_tool_module

    class _DummySystem:
        id = 99
        team_id = 12

    class _RecordingExecutor:
        def __init__(self) -> None:
            self.executed = False

        async def execute_code_blocks(self, *args, **kwargs):
            self.executed = True
            return SimpleNamespace(exit_code=0, output="{}")

    monkeypatch.setattr(
        cli_tool_module, "get_system_from_agent_id", lambda _a: _DummySystem
    )
    monkeypatch.setattr(
        cli_tool_module.systems_service,
        "can_execute_skill",
        lambda _sid, _skill: (False, "system_grant"),
    )

    tool = CliTool(_RecordingExecutor())
    tool._check_permission = lambda *_args, **_kwargs: True

    result = await tool.execute(
        "web_search",
        agent_id="System4/root",
        skill_name="web-search",
        query="x",
    )

    assert result["success"] is False
    assert result["team_id"] == 12
    assert result["system_id"] == 99
    assert result["skill_name"] == "web-search"
    assert result["failed_rule_category"] == "system_grant"


@pytest.mark.asyncio
async def test_cli_tool_execute_allows_skill_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cyberagent.tools.cli_executor import cli_tool as cli_tool_module

    class _DummySystem:
        id = 8
        team_id = 3

    class _RecordingExecutor:
        def __init__(self) -> None:
            self.executed = False

        async def execute_code_blocks(self, *args, **kwargs):
            self.executed = True
            return SimpleNamespace(exit_code=0, output="{}")

    monkeypatch.setattr(
        cli_tool_module, "get_system_from_agent_id", lambda _a: _DummySystem
    )
    monkeypatch.setattr(
        cli_tool_module.systems_service,
        "can_execute_skill",
        lambda _sid, _skill: (True, None),
    )

    tool = CliTool(_RecordingExecutor())
    tool._check_permission = lambda *_args, **_kwargs: True

    result = await tool.execute(
        "web_search",
        agent_id="System4/root",
        skill_name="web-search",
        query="x",
    )

    assert result["success"] is True
    assert tool.executor.executed is True


@pytest.mark.asyncio
async def test_cli_tool_execute_requires_agent_id_for_skill() -> None:
    class _RecordingExecutor:
        def __init__(self) -> None:
            self.executed = False

        async def execute_code_blocks(self, *args, **kwargs):
            self.executed = True
            return SimpleNamespace(exit_code=0, output="{}")

    tool = CliTool(_RecordingExecutor())

    result = await tool.execute("web_search", skill_name="web-search", query="x")

    assert result["success"] is False
    assert "agent_id" in result["error"]
    assert tool.executor.executed is False


def test_set_executor_timeout_rejects_zero() -> None:
    # Guard against invalid timeout input during coverage runs (integration audit).
    with pytest.raises(ValueError, match="Timeout must be greater"):
        _set_executor_timeout(object(), 0)
