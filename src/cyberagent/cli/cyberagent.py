from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

try:
    import yaml  # type: ignore[import]

    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    YAML_AVAILABLE = False

try:
    import keyring  # type: ignore[import]

    KEYRING_AVAILABLE = True
except ImportError:
    keyring = None  # type: ignore[assignment]
    KEYRING_AVAILABLE = False
from autogen_core import AgentId

from src.agents.messages import UserMessage
from src.cli_session import list_inbox_entries
from src.cyberagent.channels.telegram.parser import build_session_id
from src.cyberagent.cli import dev as dev_cli
from src.cyberagent.cli import dashboard_launcher
from src.cyberagent.cli.env_loader import load_op_service_account_token
from src.cyberagent.cli import log_filters
from src.cyberagent.cli.log_session import get_session_log_files
from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.cli.cli_log_state import check_recent_runtime_errors
from src.cyberagent.cli.cyberagent_helpers import handle_help, handle_login
from src.cyberagent.cli.constants import (
    DASHBOARD_COMMAND,
    INBOX_COMMAND,
    INBOX_HINT_COMMAND,
    KEYRING_SERVICE,
    ParsedSuggestion,
    SERVE_COMMAND,
    START_COMMAND,
    STATUS_COMMAND,
    SUGGEST_COMMAND,
    SUGGEST_SEND_TIMEOUT_SECONDS,
    SUGGEST_SHUTDOWN_TIMEOUT_SECONDS,
    WATCH_COMMAND,
    WATCH_HINT_COMMAND,
)
from src.cyberagent.cli.commands import runtime_commands
from src.cyberagent.cli.parser import build_parser
from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.runtime_resume import queue_in_progress_initiatives
from src.cyberagent.cli.status import main as status_main
from src.cyberagent.cli.suggestion_queue import enqueue_suggestion
from src.cyberagent.cli.task_details import render_task_detail
from src.cyberagent.cli.transcribe import handle_transcribe
from src.cyberagent.core.runtime import get_runtime, stop_runtime
from src.cyberagent.core.paths import get_logs_dir, get_data_dir
from src.cyberagent.cli.pairing import handle_pairing
from src.cyberagent.core.state import get_last_team_id
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import init_db
from src.cyberagent.db.models.team import Team
from src.cyberagent.tools.cli_executor.cli_tool import CliTool
from src.cyberagent.tools.cli_executor.factory import create_cli_executor
from src.cyberagent.tools.cli_executor.skill_loader import (
    SkillDefinition,
    load_skill_definitions,
)
from src.cyberagent.tools.cli_executor.skill_runtime import DEFAULT_SKILLS_ROOT
from src.registry import register_systems

SYSTEM4_AGENT_ID = AgentId(type="System4", key="root")
LOGS_DIR = get_logs_dir()
RUNTIME_PID_FILE = runtime_commands.RUNTIME_PID_FILE
CLI_LOG_STATE_FILE = LOGS_DIR / "cli_last_seen.json"


def main(argv: Sequence[str] | None = None) -> int:
    load_op_service_account_token()
    parser = build_parser()
    args_list = list(argv) if argv is not None else list(sys.argv[1:])
    if not args_list:
        parser.print_help()
        return 0
    args = parser.parse_args(args_list)
    _check_recent_runtime_errors(args.command)
    if args.command == "help":
        return _handle_help(args)
    handler = _HANDLERS.get(args.command)
    if handler is None:
        print(
            get_message("cyberagent", "unknown_command", command=args.command),
            file=sys.stderr,
        )
        return 1
    if asyncio.iscoroutinefunction(handler):
        return asyncio.run(handler(args))
    return handler(args)


def _handle_ui(_: argparse.Namespace) -> int:
    dashboard_python = dashboard_launcher.resolve_dashboard_python()
    if dashboard_python is None:
        print(get_message("cyberagent", "streamlit_missing"), file=sys.stderr)
        return 1
    dashboard_path = Path(__file__).resolve().parents[1] / "ui" / "dashboard.py"
    cmd = [dashboard_python, "-m", "streamlit", "run", str(dashboard_path)]
    result = subprocess.run(
        cmd,
        check=False,
        env=os.environ.copy(),
    )
    return int(result.returncode)


async def _handle_restart(args: argparse.Namespace) -> int:
    await _handle_stop(args)
    return await _handle_start(args)


def _sync_runtime_command_dependencies() -> None:
    runtime_commands.get_last_team_id = get_last_team_id
    runtime_commands.get_message = get_message
    runtime_commands.init_db = init_db
    runtime_commands.queue_in_progress_initiatives = queue_in_progress_initiatives
    runtime_commands.RUNTIME_PID_FILE = RUNTIME_PID_FILE


async def _handle_start(args: argparse.Namespace) -> int:
    _sync_runtime_command_dependencies()
    return await runtime_commands._handle_start(args)


async def run_headless_session(initial_message: str | None = None) -> None:
    """Compatibility shim kept for legacy tests and external callers."""
    _ = initial_message
    return None


def _require_existing_team() -> int | None:
    _sync_runtime_command_dependencies()
    return runtime_commands._require_existing_team()


def _ensure_background_runtime() -> int | None:
    _sync_runtime_command_dependencies()
    return runtime_commands._ensure_background_runtime()


async def _handle_stop(args: argparse.Namespace) -> int:
    return await runtime_commands._handle_stop(args)


async def _handle_serve(args: argparse.Namespace) -> int:
    return await runtime_commands._handle_serve(args)


def _handle_status(args: argparse.Namespace) -> int:
    res_args: list[str] = []
    if args.team is not None:
        res_args.extend(["--team", str(args.team)])
    if args.active_only:
        res_args.append("--active-only")
    if args.json:
        res_args.append("--json")
    if getattr(args, "details", False):
        res_args.append("--details")
    return status_main(res_args)


def _handle_task(args: argparse.Namespace) -> int:
    rendered = render_task_detail(args.task_id)
    if rendered is None:
        print(get_message("cyberagent", "task_not_found", task_id=args.task_id))
        return 1
    print(rendered)
    return 0


def _handle_onboarding(args: argparse.Namespace) -> int:
    return onboarding_cli.handle_onboarding(args, SUGGEST_COMMAND, INBOX_COMMAND)


def _handle_suggest(args: argparse.Namespace) -> int:
    try:
        parsed = _parse_suggestion_args(args)
    except ValueError as exc:
        print(
            get_message("cyberagent", "invalid_payload", error=exc),
            file=sys.stderr,
        )
        print(get_message("cyberagent", "format_tips"), file=sys.stderr)
        print(
            get_message(
                "cyberagent", "format_tip_inline", suggest_command=SUGGEST_COMMAND
            ),
            file=sys.stderr,
        )
        print(get_message("cyberagent", "format_tip_file"), file=sys.stderr)
        print(get_message("cyberagent", "format_tip_yaml"), file=sys.stderr)
        return 2
    if _require_existing_team() is None:
        return 1
    runtime_pid = _ensure_background_runtime()
    enqueue_suggestion(parsed.payload_text)
    if runtime_pid is not None:
        print(get_message("cyberagent", "runtime_active_background", pid=runtime_pid))
    print(get_message("cyberagent", "suggestion_queued"))
    print(
        get_message(
            "cyberagent",
            "next_inbox_or_watch",
            inbox_command=INBOX_HINT_COMMAND,
            watch_command=WATCH_HINT_COMMAND,
        )
    )
    return 0


def _handle_inbox(args: argparse.Namespace) -> int:
    if _require_existing_team() is None:
        return 1
    channel, session_id = _resolve_inbox_filters(args)
    entries = list_inbox_entries(channel=channel, session_id=session_id)
    include_answered = bool(getattr(args, "answered", False))
    if not include_answered:
        entries = [
            entry
            for entry in entries
            if not (entry.kind == "system_question" and entry.status == "answered")
        ]
    if not entries:
        print(get_message("cyberagent", "no_messages"))
        print(
            get_message(
                "cyberagent",
                "next_watch_or_suggest",
                watch_command=WATCH_COMMAND,
                suggest_command=SUGGEST_COMMAND,
            )
        )
        return 0
    if any(entry.channel == "telegram" for entry in entries) and not os.environ.get(
        "TELEGRAM_BOT_TOKEN"
    ):
        print(get_message("cyberagent", "telegram_delivery_disabled"))
    user_prompts = [entry for entry in entries if entry.kind == "user_prompt"]
    system_questions = [entry for entry in entries if entry.kind == "system_question"]
    system_responses = [entry for entry in entries if entry.kind == "system_response"]
    if user_prompts:
        print(get_message("cyberagent", "user_prompts_header"))
        for entry in user_prompts:
            print(
                get_message(
                    "cyberagent",
                    "user_prompt_entry",
                    entry_id=entry.entry_id,
                    content=entry.content,
                    channel=entry.channel,
                    session_id=entry.session_id,
                )
            )
    if system_questions:
        print(get_message("cyberagent", "system_questions_header"))
        for entry in system_questions:
            status = entry.status or "pending"
            answer_suffix = (
                f" -> {entry.answer}" if status == "answered" and entry.answer else ""
            )
            print(
                get_message(
                    "cyberagent",
                    "system_question_entry",
                    entry_id=entry.entry_id,
                    content=entry.content,
                    answer_suffix=answer_suffix,
                    asked_by=entry.asked_by or "System4",
                    status=status,
                    channel=entry.channel,
                    session_id=entry.session_id,
                )
            )
    if system_responses:
        print(get_message("cyberagent", "system_responses_header"))
        for entry in system_responses:
            print(
                get_message(
                    "cyberagent",
                    "system_response_entry",
                    entry_id=entry.entry_id,
                    content=entry.content,
                    channel=entry.channel,
                    session_id=entry.session_id,
                )
            )
    return 0


async def _handle_watch(args: argparse.Namespace) -> int:
    if _require_existing_team() is None:
        return 1
    seen: set[int] = set()
    print(get_message("cyberagent", "watching_inbox"))
    channel, session_id = _resolve_inbox_filters(args)
    try:
        while True:
            entries = list_inbox_entries(channel=channel, session_id=session_id)
            entries = [
                entry
                for entry in entries
                if not (entry.kind == "system_question" and entry.status == "answered")
            ]
            for entry in entries:
                if entry.entry_id in seen:
                    continue
                print(
                    get_message(
                        "cyberagent",
                        "watch_entry",
                        entry_id=entry.entry_id,
                        content=entry.content,
                        kind=entry.kind,
                        channel=entry.channel,
                    )
                )
                seen.add(entry.entry_id)
            await asyncio.sleep(max(0.1, args.interval))
    except KeyboardInterrupt:
        print(get_message("cyberagent", "stopped_watching"))
    return 0


def _resolve_inbox_filters(args: argparse.Namespace) -> tuple[str | None, str | None]:
    channel = args.channel
    session_id = args.session_id
    if args.telegram_chat_id and args.telegram_user_id and not session_id:
        session_id = build_session_id(args.telegram_chat_id, args.telegram_user_id)
        if not channel:
            channel = "telegram"
    return channel, session_id


def _handle_logs(args: argparse.Namespace) -> int:
    if not LOGS_DIR.exists():
        print(get_message("cyberagent", "no_logs_dir"))
        print(
            get_message("cyberagent", "next_start_runtime", start_command=START_COMMAND)
        )
        return 0
    log_files = get_session_log_files(LOGS_DIR)
    if not log_files:
        print(get_message("cyberagent", "no_log_files"))
        print(
            get_message(
                "cyberagent",
                "next_start_or_status",
                start_command=START_COMMAND,
                status_command=STATUS_COMMAND,
            )
        )
        return 0
    target = log_files[-1]
    lines: list[str] = []
    for log_file in log_files:
        lines.extend(log_file.read_text(encoding="utf-8", errors="ignore").splitlines())
    levels = log_filters.resolve_log_levels(
        args.level, default_to_errors=args.level is None
    )
    if levels is None and args.level:
        print(get_message("cyberagent", "invalid_log_level"))
        return 2
    effective_limit = args.limit
    if args.level is None and args.filter is None and args.limit == 200:
        # Default logs view should show all errors in the active runtime session.
        effective_limit = max(200, len(lines))
    filtered = log_filters.filter_logs(lines, args.filter, effective_limit, levels)
    for line in filtered:
        print(line)
    if args.follow:
        try:
            with target.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(0, os.SEEK_END)
                while True:
                    line = handle.readline()
                    if line:
                        if log_filters.filter_logs([line], args.filter, 1, levels):
                            print(line.rstrip("\n"))
                    else:
                        time.sleep(0.3)
        except KeyboardInterrupt:
            print(get_message("cyberagent", "stopped_following_logs"))
    return 0


def _handle_config(args: argparse.Namespace) -> int:
    if args.config_command != "view":
        print(get_message("cyberagent", "unknown_config_command"), file=sys.stderr)
        return 1
    init_db()
    session = next(get_db())
    try:
        teams = session.query(Team).order_by(Team.name).all()
        if not teams:
            print(get_message("cyberagent", "no_teams_configured"))
            print(
                get_message(
                    "cyberagent",
                    "next_start_runtime_config",
                    start_command=START_COMMAND,
                )
            )
            return 0
        for team in teams:
            print(
                get_message(
                    "cyberagent",
                    "team_line",
                    team_name=team.name,
                    team_id=team.id,
                )
            )
            if not team.systems:
                print(get_message("cyberagent", "no_systems_registered"))
                continue
            for system in team.systems:
                print(
                    get_message(
                        "cyberagent",
                        "system_line",
                        system_type=system.type.name,
                        system_agent_id=system.agent_id_str,
                    )
                )
    finally:
        session.close()
    return 0


def _handle_login(args: argparse.Namespace) -> int:
    return handle_login(
        args.token,
        keyring_available=KEYRING_AVAILABLE,
        keyring_module=keyring,
        keyring_service=KEYRING_SERVICE,
    )


async def _handle_reset(args: argparse.Namespace) -> int:
    if not args.yes:
        response = input(get_message("cyberagent", "reset_prompt")).strip()
        if response.lower() not in {"y", "yes"}:
            print(get_message("cyberagent", "reset_canceled"))
            return 0

    await _handle_stop(args)

    _reset_data_dir(get_data_dir())
    _remove_dir(get_logs_dir())
    print(get_message("cyberagent", "reset_complete"))
    return 0


def _reset_data_dir(path: Path) -> None:
    _remove_dir_contents(path, keep_files={".gitkeep"})
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    gitkeep = path / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")


def _remove_dir(path: Path) -> None:
    if not path.exists():
        return
    if not path.is_dir():
        raise ValueError(f"Expected directory at {path}")
    shutil.rmtree(path)


def _remove_dir_contents(path: Path, keep_files: set[str] | None = None) -> None:
    if not path.exists():
        return
    if not path.is_dir():
        raise ValueError(f"Expected directory at {path}")
    keep = keep_files or set()
    for child in path.iterdir():
        if child.name in keep:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


async def _handle_dev(args: argparse.Namespace) -> int:
    return await dev_cli.handle_dev(
        args,
        handle_tool_test=_handle_tool_test,
        handle_dev_system_run=_handle_dev_system_run,
    )


async def _handle_dev_system_run(args: argparse.Namespace) -> int:
    return await dev_cli.handle_dev_system_run(
        args,
        init_db=init_db,
        register_systems=register_systems,
        get_runtime=get_runtime,
        stop_runtime_with_timeout=_stop_runtime_with_timeout,
        suggest_timeout_seconds=SUGGEST_SEND_TIMEOUT_SECONDS,
    )


async def _handle_tool_test(args: argparse.Namespace) -> int:
    return await dev_cli.handle_tool_test(
        args,
        create_cli_tool=_create_cli_tool,
        find_skill_definition=_find_skill_definition,
        list_skill_names=_list_skill_names,
        execute_skill_tool=_execute_skill_tool,
        maybe_reexec_tool_test=_maybe_reexec_tool_test,
        init_db=init_db,
    )


def _create_cli_tool() -> CliTool | None:
    executor = create_cli_executor()
    if executor is None:
        return None
    return CliTool(executor)


def _find_skill_definition(tool_name: str) -> SkillDefinition | None:
    tools = load_skill_definitions(DEFAULT_SKILLS_ROOT)
    for skill in tools:
        if skill.name == tool_name:
            return skill
    return None


def _list_skill_names() -> list[str]:
    tools = load_skill_definitions(DEFAULT_SKILLS_ROOT)
    return sorted(skill.name for skill in tools)


def _maybe_reexec_tool_test(args: argparse.Namespace, exc: Exception) -> int | None:
    if os.environ.get("CYBERAGENT_TOOL_TEST_REEXEC") == "1":
        return None
    if isinstance(exc, PermissionError):
        pass
    elif "PermissionError" not in str(exc):
        return None
    python = shutil.which("python3")
    if not python:
        return None
    repo_root = _repo_root()
    if repo_root is None:
        return None
    env = os.environ.copy()
    env["CYBERAGENT_TOOL_TEST_REEXEC"] = "1"
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{repo_root}{os.pathsep}{pythonpath}" if pythonpath else str(repo_root)
    )
    cmd = [
        python,
        "-m",
        "src.cyberagent.cli.cyberagent",
        "dev",
        "tool-test",
        args.tool_name,
        "--args",
        args.args or "{}",
    ]
    if args.agent_id:
        cmd.extend(["--agent-id", args.agent_id])
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


def _repo_root() -> Path | None:
    try:
        return Path(__file__).resolve().parents[3]
    except IndexError:
        return None


async def _execute_skill_tool(
    cli_tool: CliTool,
    skill: SkillDefinition,
    arguments: dict[str, Any],
    agent_id: str | None,
) -> dict[str, Any]:
    return await cli_tool.execute(
        skill.tool_name,
        agent_id=agent_id,
        subcommand=skill.subcommand,
        timeout_seconds=skill.timeout_seconds,
        skill_name=skill.name if agent_id else None,
        required_env=list(skill.required_env),
        **arguments,
    )


def _handle_help(args: argparse.Namespace) -> int:
    return handle_help(build_parser, args.topic)


def _check_recent_runtime_errors(command: str | None) -> None:
    if command == "logs":
        return
    check_recent_runtime_errors(
        command=command,
        logs_dir=LOGS_DIR,
        state_file=CLI_LOG_STATE_FILE,
    )


def _parse_suggestion_args(args: argparse.Namespace) -> ParsedSuggestion:
    raw = ""
    if args.message:
        raw = args.message
    elif args.payload:
        raw = args.payload
    elif args.file:
        if args.file == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(args.file).read_text()
    else:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
    if not raw or not raw.strip():
        raise ValueError(get_message("cyberagent", "payload_required"))
    parsed: Any
    if args.format == "yaml":
        if not YAML_AVAILABLE or yaml is None:
            raise ValueError(get_message("cyberagent", "yaml_requires_pyyaml"))
        parsed = yaml.safe_load(raw)
    else:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw.strip()
    payload_text = (
        json.dumps(parsed, indent=2, default=str)
        if not isinstance(parsed, str)
        else parsed
    )
    return ParsedSuggestion(payload_text=payload_text, payload_object=parsed)


async def _send_suggestion(parsed: ParsedSuggestion) -> None:
    init_db()
    await register_systems()
    runtime = get_runtime()
    message = UserMessage(content=parsed.payload_text, source="User")
    try:
        await asyncio.wait_for(
            asyncio.shield(
                runtime.send_message(
                    message=message,
                    recipient=SYSTEM4_AGENT_ID,
                    sender=AgentId(type="UserAgent", key="root"),
                )
            ),
            timeout=SUGGEST_SEND_TIMEOUT_SECONDS,
        )
        print(get_message("cyberagent", "suggestion_delivered"))
        print(
            get_message(
                "cyberagent",
                "next_inbox_or_watch",
                inbox_command=INBOX_HINT_COMMAND,
                watch_command=WATCH_HINT_COMMAND,
            )
        )
    except asyncio.TimeoutError:
        print(get_message("cyberagent", "suggestion_send_timed_out"))
    except Exception as exc:  # pragma: no cover - safety net for runtime errors
        if getattr(exc, "code", None) == "output_parse_failed":
            print(get_message("cyberagent", "model_output_parse_failed"))
            return
        raise
    finally:
        await _stop_runtime_with_timeout()


async def _stop_runtime_with_timeout() -> None:
    try:
        await asyncio.wait_for(stop_runtime(), timeout=SUGGEST_SHUTDOWN_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        print(get_message("cyberagent", "runtime_shutdown_timed_out"))


_HANDLERS = {
    "start": _handle_start,
    "restart": _handle_restart,
    "stop": _handle_stop,
    DASHBOARD_COMMAND: _handle_ui,
    "status": _handle_status,
    "task": _handle_task,
    "onboarding": _handle_onboarding,
    "suggest": _handle_suggest,
    "inbox": _handle_inbox,
    "watch": _handle_watch,
    "pairing": handle_pairing,
    "dev": _handle_dev,
    "logs": _handle_logs,
    "transcribe": handle_transcribe,
    "config": _handle_config,
    "login": _handle_login,
    "reset": _handle_reset,
    SERVE_COMMAND: _handle_serve,
}


if __name__ == "__main__":
    raise SystemExit(main())
