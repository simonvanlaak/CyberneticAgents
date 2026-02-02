import argparse
from pathlib import Path

import pytest

from src.cyberagent.cli import cyberagent
from src.cyberagent.tools.cli_executor.skill_loader import SkillDefinition


@pytest.mark.asyncio
async def test_handle_tool_test_invalid_args_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = argparse.Namespace(
        tool_name="web-search",
        args="{invalid",
        agent_id=None,
    )
    exit_code = await cyberagent._handle_tool_test(args)
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Invalid --args JSON" in captured.err


@pytest.mark.asyncio
async def test_handle_tool_test_missing_skill(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_skill = SkillDefinition(
        name="another-skill",
        description="Test",
        location=Path("skills/another-skill"),
        tool_name="another_tool",
        subcommand=None,
        required_env=(),
        timeout_class="standard",
        timeout_seconds=60,
        input_schema={},
        output_schema={},
        skill_file=Path("skills/another-skill/SKILL.md"),
        instructions="",
    )

    monkeypatch.setattr(
        cyberagent, "load_skill_definitions", lambda _root: [fake_skill]
    )

    args = argparse.Namespace(
        tool_name="web-search",
        args="{}",
        agent_id=None,
    )
    exit_code = await cyberagent._handle_tool_test(args)
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Unknown tool" in captured.err


@pytest.mark.asyncio
async def test_handle_tool_test_executes_skill(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_skill = SkillDefinition(
        name="web-search",
        description="Test",
        location=Path("skills/web-search"),
        tool_name="web_search",
        subcommand=None,
        required_env=(),
        timeout_class="standard",
        timeout_seconds=60,
        input_schema={},
        output_schema={},
        skill_file=Path("skills/web-search/SKILL.md"),
        instructions="",
    )

    recorded: dict[str, object] = {}

    class DummyTool:
        async def execute(  # noqa: D401
            self,
            tool_name,
            agent_id=None,
            subcommand=None,
            timeout_seconds=None,
            skill_name=None,
            required_env=None,
            **kwargs,
        ):
            recorded["tool_name"] = tool_name
            recorded["agent_id"] = agent_id
            recorded["subcommand"] = subcommand
            recorded["timeout_seconds"] = timeout_seconds
            recorded["skill_name"] = skill_name
            recorded["required_env"] = required_env
            recorded["kwargs"] = kwargs
            return {"success": True, "output": {"ok": True}}

    monkeypatch.setattr(
        cyberagent, "load_skill_definitions", lambda _root: [fake_skill]
    )
    monkeypatch.setattr(cyberagent, "_create_cli_tool", lambda: DummyTool())

    args = argparse.Namespace(
        tool_name="web-search",
        args='{"q": "hello"}',
        agent_id="System4/root",
    )
    exit_code = await cyberagent._handle_tool_test(args)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert recorded["tool_name"] == "web_search"
    assert recorded["agent_id"] == "System4/root"
    assert recorded["skill_name"] == "web-search"
    assert recorded["kwargs"] == {"q": "hello"}
    assert '"ok": true' in captured.out


@pytest.mark.asyncio
async def test_handle_tool_test_starts_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_skill = SkillDefinition(
        name="web-search",
        description="Test",
        location=Path("skills/web-search"),
        tool_name="web_search",
        subcommand=None,
        required_env=(),
        timeout_class="standard",
        timeout_seconds=60,
        input_schema={},
        output_schema={},
        skill_file=Path("skills/web-search/SKILL.md"),
        instructions="",
    )

    class DummyExecutor:
        def __init__(self) -> None:
            self.started = False
            self.stopped = False

        async def start(self) -> None:
            self.started = True

        async def stop(self) -> None:
            self.stopped = True

    class DummyTool:
        def __init__(self) -> None:
            self.executor = DummyExecutor()

        async def execute(self, *args, **kwargs):  # noqa: ANN001
            return {"success": True, "output": {"ok": True}}

    dummy_tool = DummyTool()
    monkeypatch.setattr(
        cyberagent, "load_skill_definitions", lambda _root: [fake_skill]
    )
    monkeypatch.setattr(cyberagent, "_create_cli_tool", lambda: dummy_tool)

    args = argparse.Namespace(
        tool_name="web-search",
        args="{}",
        agent_id=None,
    )
    exit_code = await cyberagent._handle_tool_test(args)

    assert exit_code == 0
    assert dummy_tool.executor.started is True
    assert dummy_tool.executor.stopped is True


@pytest.mark.asyncio
async def test_handle_tool_test_reports_executor_start_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_skill = SkillDefinition(
        name="file-reader",
        description="Test",
        location=Path("skills/file-reader"),
        tool_name="exec",
        subcommand="run",
        required_env=(),
        timeout_class="standard",
        timeout_seconds=60,
        input_schema={},
        output_schema={},
        skill_file=Path("skills/file-reader/SKILL.md"),
        instructions="",
    )

    class DummyExecutor:
        async def start(self) -> None:
            raise RuntimeError("docker unavailable")

    class DummyTool:
        def __init__(self) -> None:
            self.executor = DummyExecutor()

        async def execute(self, *args, **kwargs):  # noqa: ANN001
            return {"success": True}

    monkeypatch.setattr(
        cyberagent, "load_skill_definitions", lambda _root: [fake_skill]
    )
    monkeypatch.setattr(cyberagent, "_create_cli_tool", lambda: DummyTool())

    args = argparse.Namespace(
        tool_name="file-reader",
        args="{}",
        agent_id=None,
    )
    exit_code = await cyberagent._handle_tool_test(args)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Failed to start CLI tool executor" in captured.err


@pytest.mark.asyncio
async def test_handle_tool_test_reexecs_on_permission_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_skill = SkillDefinition(
        name="file-reader",
        description="Test",
        location=Path("skills/file-reader"),
        tool_name="exec",
        subcommand="run",
        required_env=(),
        timeout_class="standard",
        timeout_seconds=60,
        input_schema={},
        output_schema={},
        skill_file=Path("skills/file-reader/SKILL.md"),
        instructions="",
    )

    class DummyExecutor:
        async def start(self) -> None:
            raise PermissionError("Operation not permitted")

    class DummyTool:
        def __init__(self) -> None:
            self.executor = DummyExecutor()

        async def execute(self, *args, **kwargs):  # noqa: ANN001
            return {"success": True}

    class DummyProc:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "ok\n"
            self.stderr = ""

    def fake_run(cmd, capture_output, text, env):  # noqa: ANN001
        assert "CYBERAGENT_TOOL_TEST_REEXEC" in env
        return DummyProc()

    monkeypatch.setattr(
        cyberagent, "load_skill_definitions", lambda _root: [fake_skill]
    )
    monkeypatch.setattr(cyberagent, "_create_cli_tool", lambda: DummyTool())
    monkeypatch.setattr(cyberagent.shutil, "which", lambda _name: "python3")
    monkeypatch.setattr(cyberagent, "_repo_root", lambda: Path("/tmp/repo"))
    monkeypatch.setattr(cyberagent.subprocess, "run", fake_run)
    monkeypatch.delenv("CYBERAGENT_TOOL_TEST_REEXEC", raising=False)

    args = argparse.Namespace(
        tool_name="file-reader",
        args="{}",
        agent_id=None,
    )
    exit_code = await cyberagent._handle_tool_test(args)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ok" in captured.out
