from __future__ import annotations

import argparse

from src.cyberagent.cli.constants import DASHBOARD_COMMAND, SERVE_COMMAND
from src.cyberagent.cli.onboarding_args import add_onboarding_args
from src.cyberagent.cli.pairing import add_pairing_parser
from src.cyberagent.cli.transcribe import add_transcribe_parser


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
    restart_parser = subparsers.add_parser("restart", help="Restart the runtime.")
    restart_parser.add_argument(
        "--message",
        "-m",
        type=str,
        default=None,
        help="Send an initial message after startup.",
    )
    subparsers.add_parser(
        DASHBOARD_COMMAND, help="Open the local read-only Streamlit dashboard."
    )
    add_onboarding_args(subparsers)
    add_pairing_parser(subparsers)

    status_parser = subparsers.add_parser(
        "status", help="Show current team/strategy/task hierarchy."
    )
    status_parser.add_argument("--team", type=int, default=None)
    status_parser.add_argument("--active-only", action="store_true")
    status_parser.add_argument("--json", action="store_true")
    status_parser.add_argument(
        "--details",
        action="store_true",
        help=(
            "Include free-form fields (purpose content + descriptions + task content). "
            "Warning: may print memory/notes."
        ),
    )

    task_parser = subparsers.add_parser(
        "task",
        help="Show detailed information for a task.",
    )
    task_parser.add_argument("task_id", type=int, help="Task id.")

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

    inbox_parser = subparsers.add_parser("inbox", help="Read inbox entries.")
    inbox_parser.add_argument(
        "--answered",
        action="store_true",
        help="Include answered system questions.",
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
        "watch", help="Watch the inbox for new entries."
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
        "--follow", "-f", action="store_true", help="Tail the logs."
    )
    logs_parser.add_argument(
        "--limit", type=int, default=200, help="Max lines to show."
    )

    add_transcribe_parser(subparsers)

    config_parser = subparsers.add_parser("config", help="Inspect VSM configuration.")
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", required=True
    )
    config_subparsers.add_parser("view", help="Read-only view of registered systems.")

    login_parser = subparsers.add_parser("login", help="Authenticate with the VSM.")
    login_parser.add_argument(
        "--token", "-t", type=str, help="Authentication token. Prompts if omitted."
    )

    reset_parser = subparsers.add_parser(
        "reset",
        help="Delete all persisted CyberneticAgents data (keeps .env).",
    )
    reset_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt.",
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
