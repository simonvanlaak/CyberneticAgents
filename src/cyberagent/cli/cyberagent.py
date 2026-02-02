from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
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
from src.cli_session import list_inbox_answered_questions, list_inbox_pending_questions
from src.cyberagent.channels.telegram.parser import build_session_id
from src.cyberagent.cli import dev as dev_cli
from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.cli.headless import run_headless_session
from src.cyberagent.cli.status import main as status_main
from src.cyberagent.cli.suggestion_queue import enqueue_suggestion
from src.cyberagent.core.runtime import get_runtime, stop_runtime
from src.cyberagent.core.state import get_last_team_id, mark_team_active
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
from src.rbac.enforcer import get_enforcer
from src.registry import register_systems

KEYRING_SERVICE = "cyberagent-cli"
SYSTEM4_AGENT_ID = AgentId(type="System4", key="root")
LOGS_DIR = Path("logs")
RUNTIME_PID_FILE = Path("logs/cyberagent.pid")
CLI_LOG_STATE_FILE = Path("logs/cli_last_seen.json")
SERVE_COMMAND = "serve"
TEST_START_ENV = "CYBERAGENT_TEST_NO_RUNTIME"
TEST_START_ENV = "CYBERAGENT_TEST_NO_RUNTIME"
SUGGEST_COMMAND = 'cyberagent suggest "Describe the task"'
START_COMMAND = "cyberagent start"
ONBOARDING_COMMAND = "cyberagent onboarding"
INBOX_COMMAND = "cyberagent inbox"
WATCH_COMMAND = "cyberagent watch"
STATUS_COMMAND = "cyberagent status"
INBOX_HINT_COMMAND = "cyberagent inbox"
WATCH_HINT_COMMAND = "cyberagent watch"
SUGGEST_SHUTDOWN_TIMEOUT_SECONDS = 1.0
SUGGEST_SEND_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class ParsedSuggestion:
    payload_text: str
    payload_object: Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cyberagent",
        description=(
            "CyberneticAgents CLI. New runtime warnings/errors since your last "
            "command are summarized automatically; use 'cyberagent logs' for details."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser(
        "start", help="Boot the VSM runtime.", description="Boot the VSM runtime."
    )
    start_parser.add_argument(
        "--message",
        "-m",
        type=str,
        default=None,
        help="Send an initial message after startup.",
    )

    subparsers.add_parser("stop", help="Gracefully stop the runtime.")
    subparsers.add_parser("restart", help="Restart the runtime.")
    subparsers.add_parser(
        "onboarding",
        help="Initialize the default team.",
        description="Create the default root team if none exists.",
    )

    status_parser = subparsers.add_parser(
        "status", help="Show current team/strategy/task hierarchy."
    )
    status_parser.add_argument("--team", type=int, default=None)
    status_parser.add_argument("--active-only", action="store_true")
    status_parser.add_argument("--json", action="store_true")

    suggest_parser = subparsers.add_parser(
        "suggest", help="Send a suggestion payload to System4."
    )
    suggest_parser.add_argument(
        "message",
        nargs="?",
        type=str,
        help="Suggestion payload (positional).",
    )
    suggest_parser.add_argument(
        "--payload", "-p", type=str, help="Inline JSON/YAML payload."
    )
    suggest_parser.add_argument(
        "--file", "-f", type=str, help="File path or '-' for stdin."
    )
    suggest_parser.add_argument(
        "--format",
        choices=["json", "yaml"],
        default="json",
        help="Payload format (yaml requires PyYAML).",
    )

    inbox_parser = subparsers.add_parser(
        "inbox", help="Read pending CLI inbox messages."
    )
    inbox_parser.add_argument(
        "--answered", action="store_true", help="Include answered items."
    )
    inbox_parser.add_argument(
        "--channel",
        type=str,
        help="Filter inbox entries by channel (e.g. cli, telegram).",
    )
    inbox_parser.add_argument(
        "--session-id",
        type=str,
        help="Filter inbox entries by session id.",
    )
    inbox_parser.add_argument(
        "--telegram-chat-id",
        type=int,
        help="Filter inbox entries by Telegram chat id.",
    )
    inbox_parser.add_argument(
        "--telegram-user-id",
        type=int,
        help="Filter inbox entries by Telegram user id.",
    )

    watch_parser = subparsers.add_parser(
        "watch", help="Watch the inbox for new questions."
    )
    watch_parser.add_argument("--interval", type=float, default=5.0)
    watch_parser.add_argument(
        "--channel",
        type=str,
        help="Filter inbox entries by channel (e.g. cli, telegram).",
    )
    watch_parser.add_argument(
        "--session-id",
        type=str,
        help="Filter inbox entries by session id.",
    )
    watch_parser.add_argument(
        "--telegram-chat-id",
        type=int,
        help="Filter inbox entries by Telegram chat id.",
    )
    watch_parser.add_argument(
        "--telegram-user-id",
        type=int,
        help="Filter inbox entries by Telegram user id.",
    )

    logs_parser = subparsers.add_parser("logs", help="Inspect runtime logs.")
    logs_parser.add_argument(
        "--filter", "-i", type=str, help="Substring filter for log lines."
    )
    logs_parser.add_argument(
        "--level",
        "-l",
        action="append",
        help="Filter by log level (repeatable or comma-separated).",
    )
    logs_parser.add_argument(
        "--errors",
        action="store_true",
        help="Shortcut for --level ERROR,CRITICAL.",
    )
    logs_parser.add_argument(
        "--follow", "-f", action="store_true", help="Tail the logs."
    )
    logs_parser.add_argument(
        "--limit", type=int, default=200, help="Max lines to show."
    )

    config_parser = subparsers.add_parser("config", help="Inspect VSM configuration.")
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", required=True
    )
    config_subparsers.add_parser("view", help="Read-only view of registered systems.")

    login_parser = subparsers.add_parser("login", help="Authenticate with the VSM.")
    login_parser.add_argument(
        "--token", "-t", type=str, help="Authentication token. Prompts if omitted."
    )

    dev_parser = subparsers.add_parser("dev", help="Developer utilities.")
    dev_subparsers = dev_parser.add_subparsers(dest="dev_command", required=True)
    tool_test_parser = dev_subparsers.add_parser(
        "tool-test", help="Run a skill tool directly."
    )
    tool_test_parser.add_argument("tool_name", type=str, help="Skill tool name.")
    tool_test_parser.add_argument(
        "--args",
        type=str,
        default="{}",
        help="JSON object string of tool arguments.",
    )
    tool_test_parser.add_argument(
        "--agent-id",
        type=str,
        default=None,
        help="Agent id for RBAC/skill permission checks.",
    )
    system_run_parser = dev_subparsers.add_parser(
        "system-run", help="Send a one-off message to a system."
    )
    system_run_parser.add_argument("system_id", type=str)
    system_run_parser.add_argument("message", type=str)

    help_parser = subparsers.add_parser("help", help="Show CLI help.")
    help_parser.add_argument(
        "topic",
        nargs="?",
        help="Specific command to show details for.",
    )

    serve_parser = subparsers.add_parser(SERVE_COMMAND, help=argparse.SUPPRESS)
    serve_parser.add_argument(
        "--message",
        "-m",
        type=str,
        default=None,
        help=argparse.SUPPRESS,
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
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
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1
    if asyncio.iscoroutinefunction(handler):
        return asyncio.run(handler(args))
    return handler(args)


async def _handle_start(args: argparse.Namespace) -> int:
    if os.environ.get(TEST_START_ENV) == "1":
        print("Runtime start stubbed (test mode).")
        print(f"Next: run {SUGGEST_COMMAND} to give the agents a task.")
        return 0
    init_db()
    team_id = _require_existing_team()
    if team_id is None:
        return 1
    cmd = [sys.executable, "-m", "src.cyberagent.cli.cyberagent", SERVE_COMMAND]
    if args.message:
        cmd.extend(["--message", args.message])
    env = os.environ.copy()
    env["CYBERAGENT_ACTIVE_TEAM_ID"] = str(team_id)
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    RUNTIME_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    print(f"Runtime starting in background (pid {proc.pid}).")
    print(f"Next: run {SUGGEST_COMMAND} to give the agents a task.")
    return 0


def _require_existing_team() -> int | None:
    team_id = get_last_team_id()
    if team_id is None:
        print(f"No teams found. Run '{ONBOARDING_COMMAND}' to create your first team.")
        return None
    return team_id


def _ensure_background_runtime() -> int | None:
    if _runtime_pid_is_running():
        return _load_runtime_pid()
    return _start_runtime_background()


def _runtime_pid_is_running() -> bool:
    pid = _load_runtime_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _load_runtime_pid() -> int | None:
    if not RUNTIME_PID_FILE.exists():
        return None
    try:
        return int(RUNTIME_PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _start_runtime_background() -> int | None:
    if os.environ.get(TEST_START_ENV) == "1":
        return None
    init_db()
    team_id = _require_existing_team()
    if team_id is None:
        return None
    cmd = [sys.executable, "-m", "src.cyberagent.cli.cyberagent", SERVE_COMMAND]
    env = os.environ.copy()
    env["CYBERAGENT_ACTIVE_TEAM_ID"] = str(team_id)
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    RUNTIME_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


async def _handle_stop(_: argparse.Namespace) -> int:
    await stop_runtime()
    print("Runtime stopped.")
    return 0


async def _handle_restart(args: argparse.Namespace) -> int:
    await _handle_stop(args)
    return await _handle_start(args)


def _handle_status(args: argparse.Namespace) -> int:
    res_args: list[str] = []
    if args.team is not None:
        res_args.extend(["--team", str(args.team)])
    if args.active_only:
        res_args.append("--active-only")
    if args.json:
        res_args.append("--json")
    return status_main(res_args)


def _handle_onboarding(args: argparse.Namespace) -> int:
    return onboarding_cli.handle_onboarding(args, SUGGEST_COMMAND)


def _handle_suggest(args: argparse.Namespace) -> int:
    try:
        parsed = _parse_suggestion_args(args)
    except ValueError as exc:
        print(f"Invalid payload: {exc}", file=sys.stderr)
        print(
            "Format tips:",
            file=sys.stderr,
        )
        print(
            f"- Inline text or JSON: {SUGGEST_COMMAND}",
            file=sys.stderr,
        )
        print(
            "- File payload: cyberagent suggest --file payload.json",
            file=sys.stderr,
        )
        print(
            "- YAML payload: cyberagent suggest --file payload.yaml --format yaml",
            file=sys.stderr,
        )
        return 2
    if _require_existing_team() is None:
        return 1
    runtime_pid = _ensure_background_runtime()
    enqueue_suggestion(parsed.payload_text)
    if runtime_pid is not None:
        print(f"Runtime active in background (pid {runtime_pid}).")
    print("Suggestion queued for System4.")
    print(
        f"Next: run {INBOX_HINT_COMMAND} or {WATCH_HINT_COMMAND} to check for incoming messages."
    )
    return 0


def _handle_inbox(args: argparse.Namespace) -> int:
    if _require_existing_team() is None:
        return 1
    channel, session_id = _resolve_inbox_filters(args)
    pending = list_inbox_pending_questions(channel=channel, session_id=session_id)
    answered = (
        list_inbox_answered_questions(channel=channel, session_id=session_id)
        if args.answered
        else []
    )
    if not pending and not answered:
        print("No messages in inbox.")
        print(f"Next: run {WATCH_COMMAND} to wait, or {SUGGEST_COMMAND}.")
        return 0
    if pending:
        print("Pending questions:")
        for question in pending:
            print(
                f"- [{question.question_id}] {question.content} "
                f"(asked by {question.asked_by or 'System4'}, "
                f"channel={question.channel}, session={question.session_id})"
            )
    if answered:
        print("\nAnswered questions:")
        for item in answered:
            print(
                f"- [{item.question_id}] {item.content} -> {item.answer} "
                f"(channel={item.channel}, session={item.session_id})"
            )
    return 0


async def _handle_watch(args: argparse.Namespace) -> int:
    if _require_existing_team() is None:
        return 1
    seen: set[int] = set()
    print("Watching inbox (Ctrl-C to stop)...")
    channel, session_id = _resolve_inbox_filters(args)
    try:
        while True:
            pending = list_inbox_pending_questions(
                channel=channel, session_id=session_id
            )
            for question in pending:
                if question.question_id in seen:
                    continue
                print(
                    f"[{question.question_id}] {question.content} "
                    f"(channel={question.channel})"
                )
                seen.add(question.question_id)
            await asyncio.sleep(max(0.1, args.interval))
    except KeyboardInterrupt:
        print("Stopped watching inbox.")
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
        print("No logs directory found.")
        print(f"Next: run {START_COMMAND} to boot the runtime.")
        return 0
    log_files = sorted(LOGS_DIR.glob("*.log"), key=os.path.getmtime)
    if not log_files:
        print("No log files to inspect.")
        print(f"Next: run {START_COMMAND} or check status with {STATUS_COMMAND}.")
        return 0
    target = log_files[-1]
    lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    levels = _resolve_log_levels(args.level, args.errors)
    if levels is None:
        print("Invalid log level. Use: DEBUG, INFO, WARNING, ERROR, CRITICAL.")
        return 2
    filtered = _filter_logs(lines, args.filter, args.limit, levels)
    for line in filtered:
        print(line)
    if args.follow:
        try:
            with target.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(0, os.SEEK_END)
                while True:
                    line = handle.readline()
                    if line:
                        if _matches_filter(line, args.filter, levels):
                            print(line.rstrip("\n"))
                    else:
                        time.sleep(0.3)
        except KeyboardInterrupt:
            print("Stopped following logs.")
    return 0


def _handle_config(args: argparse.Namespace) -> int:
    if args.config_command != "view":
        print("Unknown config command.", file=sys.stderr)
        return 1
    init_db()
    session = next(get_db())
    try:
        teams = session.query(Team).order_by(Team.name).all()
        if not teams:
            print("No teams configured.")
            print(f"Next: run {START_COMMAND} to initialize the runtime.")
            return 0
        for team in teams:
            print(f"Team: {team.name} (id={team.id})")
            if not team.systems:
                print("  No systems registered.")
                continue
            for system in team.systems:
                print(f"  - {system.type.name} ({system.agent_id_str})")
    finally:
        session.close()
    return 0


def _handle_login(args: argparse.Namespace) -> int:
    token = args.token
    if not token:
        token = getpass.getpass("Authentication token: ")
    if KEYRING_AVAILABLE and keyring is not None:
        keyring.set_password(KEYRING_SERVICE, "cli", token)
        print("Token stored securely in the OS keyring.")
    else:
        fallback = Path.home() / ".cyberagent_token"
        fallback.write_text(token, encoding="utf-8")
        print(
            f"Keyring unavailable; token saved to {fallback} (read/write permissions only)."
        )
    return 0


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


async def _handle_serve(args: argparse.Namespace) -> int:
    team_id = os.environ.get("CYBERAGENT_ACTIVE_TEAM_ID")
    if team_id:
        try:
            mark_team_active(int(team_id))
            print(f"Starting headless runtime for team {team_id}.")
        except ValueError:
            print(f"Invalid team id '{team_id}' configured.", file=sys.stderr)
    await run_headless_session(initial_message=args.message)
    return 0


def _handle_help(args: argparse.Namespace) -> int:
    parser = build_parser()
    if not args.topic:
        parser.print_help()
        return 0
    subparser = _lookup_subparser(parser, args.topic)
    if subparser is None:
        print(f"Unknown help topic: {args.topic}", file=sys.stderr)
        return 1
    subparser.print_help()
    return 0


def _lookup_subparser(
    parser: argparse.ArgumentParser, name: str
) -> argparse.ArgumentParser | None:
    subparsers_action = next(
        (
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ),
        None,
    )
    if subparsers_action is None:
        return None
    return subparsers_action.choices.get(name)


def _filter_logs(
    lines: Sequence[str],
    pattern: str | None,
    limit: int,
    levels: set[str] | None,
) -> Sequence[str]:
    filtered = [line for line in lines if _matches_filter(line, pattern, levels)]
    return filtered[-limit:]


def _matches_filter(line: str, pattern: str | None, levels: set[str] | None) -> bool:
    if pattern is None:
        text_match = True
    else:
        text_match = pattern.lower() in line.lower()
    if not text_match:
        return False
    if levels is None:
        return True
    level = _extract_log_level(line)
    if level is None:
        return False
    return level.upper() in levels


def _normalize_log_levels(level_args: Sequence[str] | None) -> set[str] | None:
    if not level_args:
        return None
    allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    normalized: set[str] = set()
    for arg in level_args:
        for raw in arg.split(","):
            token = raw.strip().upper()
            if not token:
                continue
            if token not in allowed:
                raise ValueError(f"Unknown log level: {token}")
            normalized.add(token)
    return normalized


def _resolve_log_levels(
    level_args: Sequence[str] | None, errors_only: bool
) -> set[str] | None:
    try:
        levels = _normalize_log_levels(level_args)
    except ValueError:
        return None
    if errors_only:
        error_levels = {"ERROR", "CRITICAL"}
        if levels is None:
            return error_levels
        return levels | error_levels
    return levels


def _check_recent_runtime_errors(command: str | None) -> None:
    if not LOGS_DIR.exists():
        return
    log_files = sorted(LOGS_DIR.glob("*.log"), key=os.path.getmtime)
    if not log_files:
        return
    latest_log = log_files[-1]
    state = _load_cli_log_state()
    offset = 0
    latest_path = str(latest_log.resolve())
    if state and state.get("log_path") == latest_path:
        offset = _safe_int(state.get("byte_offset"), 0)

    warnings = 0
    errors = 0
    try:
        with latest_log.open("rb") as handle:
            handle.seek(offset)
            new_bytes = handle.read()
            new_offset = handle.tell()
        if new_bytes:
            text = new_bytes.decode("utf-8", errors="ignore")
            for line in text.splitlines():
                level = _extract_log_level(line)
                if level == "WARNING":
                    warnings += 1
                elif level == "ERROR":
                    errors += 1
        _store_cli_log_state(latest_path, new_offset)
    except OSError:
        return

    if warnings or errors:
        print(
            "New runtime logs since last command: "
            f"{errors} errors, {warnings} warnings. "
            "Run 'cyberagent logs' to view."
        )


def _extract_log_level(line: str) -> str | None:
    parts = line.split(" ", 3)
    if len(parts) < 3:
        return None
    level = parts[2].strip()
    return level if level else None


def _load_cli_log_state() -> dict[str, object] | None:
    if not CLI_LOG_STATE_FILE.exists():
        return None
    try:
        return json.loads(CLI_LOG_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _store_cli_log_state(log_path: str, byte_offset: int) -> None:
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "log_path": log_path,
            "byte_offset": byte_offset,
            "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        CLI_LOG_STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


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
        raise ValueError("payload is required")
    parsed: Any
    if args.format == "yaml":
        if not YAML_AVAILABLE or yaml is None:
            raise ValueError("YAML support requires PyYAML")
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
    enforcer = get_enforcer()
    enforcer.clear_policy()
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
        print("Suggestion delivered to System4.")
        print(
            f"Next: run {INBOX_HINT_COMMAND} or {WATCH_HINT_COMMAND} to check for incoming messages."
        )
    except asyncio.TimeoutError:
        print(
            "Suggestion send timed out; the runtime may still be working. "
            "Check logs with 'cyberagent logs'."
        )
    except Exception as exc:  # pragma: no cover - safety net for runtime errors
        if getattr(exc, "code", None) == "output_parse_failed":
            print(
                "Model output could not be parsed. Try rephrasing the request or "
                "using a more explicit payload."
            )
            return
        raise
    finally:
        await _stop_runtime_with_timeout()


async def _stop_runtime_with_timeout() -> None:
    try:
        await asyncio.wait_for(stop_runtime(), timeout=SUGGEST_SHUTDOWN_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        print("Runtime shutdown timed out; exiting anyway.")


_HANDLERS = {
    "start": _handle_start,
    "restart": _handle_restart,
    "stop": _handle_stop,
    "status": _handle_status,
    "onboarding": _handle_onboarding,
    "suggest": _handle_suggest,
    "inbox": _handle_inbox,
    "watch": _handle_watch,
    "dev": _handle_dev,
    "logs": _handle_logs,
    "config": _handle_config,
    "login": _handle_login,
    SERVE_COMMAND: _handle_serve,
}


if __name__ == "__main__":
    raise SystemExit(main())
