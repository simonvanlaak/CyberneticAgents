from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
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
from src.cli.headless import run_headless_session
from src.cli_session import get_answered_questions, get_pending_questions
from src.cli.status import main as status_main
from src.db_utils import get_db
from src.init_db import init_db
from src.models.team import Team
from src.rbac.enforcer import get_enforcer
from src.registry import register_systems
from src.runtime import get_runtime, stop_runtime

KEYRING_SERVICE = "cyberagent-cli"
SYSTEM4_AGENT_ID = AgentId(type="System4", key="root")
LOGS_DIR = Path("logs")


@dataclass(frozen=True)
class ParsedSuggestion:
    payload_text: str
    payload_object: Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cyberagent", description="CyberneticAgents CLI"
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

    watch_parser = subparsers.add_parser(
        "watch", help="Watch the inbox for new questions."
    )
    watch_parser.add_argument("--interval", type=float, default=5.0)

    logs_parser = subparsers.add_parser("logs", help="Inspect runtime logs.")
    logs_parser.add_argument(
        "--filter", "-i", type=str, help="Substring filter for log lines."
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

    help_parser = subparsers.add_parser("help", help="Show CLI help.")
    help_parser.add_argument(
        "topic",
        nargs="?",
        help="Specific command to show details for.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv or sys.argv[1:])
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
    await run_headless_session(initial_message=args.message)
    return 0


async def _handle_stop(_: argparse.Namespace) -> int:
    await stop_runtime()
    print("Runtime stopped.")
    return 0


def _handle_status(args: argparse.Namespace) -> int:
    res_args: list[str] = []
    if args.team is not None:
        res_args.extend(["--team", str(args.team)])
    if args.active_only:
        res_args.append("--active-only")
    if args.json:
        res_args.append("--json")
    return status_main(res_args)


def _handle_suggest(args: argparse.Namespace) -> int:
    try:
        parsed = _parse_suggestion_args(args)
    except ValueError as exc:
        print(f"Invalid payload: {exc}", file=sys.stderr)
        return 2
    asyncio.run(_send_suggestion(parsed))
    return 0


def _handle_inbox(args: argparse.Namespace) -> int:
    pending = get_pending_questions()
    answered = get_answered_questions() if args.answered else []
    if not pending and not answered:
        print("No messages in inbox.")
        return 0
    if pending:
        print("Pending questions:")
        for question in pending:
            print(
                f"- [{question.question_id}] {question.content} (asked by {question.asked_by or 'System4'})"
            )
    if answered:
        print("\nAnswered questions:")
        for item in answered:
            print(f"- [{item.question_id}] {item.content} -> {item.answer}")
    return 0


async def _handle_watch(args: argparse.Namespace) -> int:
    seen: set[int] = set()
    print("Watching inbox (Ctrl-C to stop)...")
    try:
        while True:
            pending = get_pending_questions()
            for question in pending:
                if question.question_id in seen:
                    continue
                print(f"[{question.question_id}] {question.content}")
                seen.add(question.question_id)
            await asyncio.sleep(max(0.1, args.interval))
    except KeyboardInterrupt:
        print("Stopped watching inbox.")
    return 0


def _handle_logs(args: argparse.Namespace) -> int:
    if not LOGS_DIR.exists():
        print("No logs directory found.")
        return 0
    log_files = sorted(LOGS_DIR.glob("*.log"), key=os.path.getmtime)
    if not log_files:
        print("No log files to inspect.")
        return 0
    target = log_files[-1]
    lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    filtered = _filter_logs(lines, args.filter, args.limit)
    for line in filtered:
        print(line)
    if args.follow:
        try:
            with target.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(0, os.SEEK_END)
                while True:
                    line = handle.readline()
                    if line:
                        if _matches_filter(line, args.filter):
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
    lines: Sequence[str], pattern: str | None, limit: int
) -> Sequence[str]:
    filtered = [line for line in lines if _matches_filter(line, pattern)]
    return filtered[-limit:]


def _matches_filter(line: str, pattern: str | None) -> bool:
    if pattern is None:
        return True
    return pattern.lower() in line.lower()


def _parse_suggestion_args(args: argparse.Namespace) -> ParsedSuggestion:
    raw = ""
    if args.payload:
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
        if not YAML_AVAILABLE:
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
    await runtime.send_message(message=message, recipient=SYSTEM4_AGENT_ID)
    print("Suggestion delivered to System4.")
    await stop_runtime()


_HANDLERS = {
    "start": _handle_start,
    "stop": _handle_stop,
    "status": _handle_status,
    "suggest": _handle_suggest,
    "inbox": _handle_inbox,
    "watch": _handle_watch,
    "logs": _handle_logs,
    "config": _handle_config,
    "login": _handle_login,
}
