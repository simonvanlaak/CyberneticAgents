from __future__ import annotations

import asyncio
import os

from autogen_core import AgentId

from src.agents.messages import UserMessage
from src.agents.user_agent import UserAgent
from src.cli_session import forward_user_messages, read_stdin_loop
from src.init_db import init_db
from src.logging_utils import configure_autogen_logging
from src.rbac.enforcer import get_enforcer
from src.registry import register_systems
from src.runtime import get_runtime, stop_runtime


async def run_headless_session(initial_message: str | None = None) -> None:
    """
    Run the headless CLI session that forwards user input to the runtime.
    """
    init_db()
    await register_systems()
    enforcer = get_enforcer()
    enforcer.clear_policy()

    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    configure_autogen_logging(logs_dir)

    runtime = get_runtime()
    recipient = AgentId(type=UserAgent.__name__, key="root")
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

    try:
        await stop_event.wait()
    finally:
        reader_task.cancel()
        forward_task.cancel()
        await stop_runtime()
