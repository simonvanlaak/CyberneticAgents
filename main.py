# -*- coding: utf-8 -*-
"""
Main Application Entry Point (TUI)

Textual-based interface for interacting with the multi-agent runtime.
"""

import argparse
import asyncio
import os
import sys
import time

import dotenv
from autogen_core import AgentId

from src.agents.messages import UserMessage
from src.agents.user_agent import UserAgent
from src.cli_session import forward_user_messages, read_stdin_loop
from src.init_db import init_db
from src.rbac.enforcer import get_enforcer
from src.registry import register_systems
from src.runtime import get_runtime, stop_runtime
from src.ui_state import set_log_file
from src.ui.vibe_ui.app import CyberneticTUI

dotenv.load_dotenv()


def parse_cli_args(argv: list[str]) -> tuple[bool, str | None]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", "--no-tui", action="store_true")
    parser.add_argument("--message", dest="message", type=str, default=None)
    parser.add_argument("message_parts", nargs="*")
    args = parser.parse_args(argv[1:])

    if args.message:
        initial_message = args.message.strip()
    else:
        initial_message = " ".join(args.message_parts).strip()

    return args.headless, (initial_message or None)


def should_force_headless() -> bool:
    return not (sys.stdin.isatty() and sys.stdout.isatty())


async def main() -> None:
    headless, initial_message = parse_cli_args(sys.argv)
    if not headless and should_force_headless():
        headless = True
    init_db()
    await register_systems()
    enforcer = get_enforcer()
    enforcer.clear_policy()

    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = time.strftime("chat_%Y%m%d_%H%M%S.log")
    set_log_file(os.path.join(logs_dir, log_filename))

    runtime = get_runtime()
    recipient = AgentId(type=UserAgent.__name__, key="root")
    if headless:
        if initial_message:
            await runtime.send_message(
                message=UserMessage(content=initial_message, source="User"),
                recipient=recipient,
            )
        queue: asyncio.Queue[str] = asyncio.Queue()
        stop_event = asyncio.Event()
        reader_task = asyncio.create_task(read_stdin_loop(queue, stop_event))
        forward_task = asyncio.create_task(
            forward_user_messages(queue, runtime, recipient, stop_event)
        )
        await stop_event.wait()
        reader_task.cancel()
        forward_task.cancel()
    else:
        app = CyberneticTUI(runtime, recipient, initial_message=initial_message)
        await app.run_async()
    await stop_runtime()


if __name__ == "__main__":
    asyncio.run(main())
