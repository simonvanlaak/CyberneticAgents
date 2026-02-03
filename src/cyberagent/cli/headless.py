from __future__ import annotations

import asyncio
import logging
import os
from typing import Protocol

from autogen_core import AgentId, CancellationToken

from src.agents.messages import UserMessage
from src.agents.user_agent import UserAgent
from src.cli_session import forward_user_messages, read_stdin_loop
from src.cyberagent.channels.inbox import DEFAULT_CHANNEL, DEFAULT_SESSION_ID
from src.cyberagent.channels.telegram.poller import TelegramPoller
from src.cyberagent.channels.telegram.webhook import TelegramWebhookServer
from src.cyberagent.cli.suggestion_queue import (
    SUGGEST_QUEUE_POLL_SECONDS,
    ack_suggestion,
    read_queued_suggestions,
)
from src.cyberagent.db.init_db import init_db
from src.cyberagent.core.state import get_last_team_id
from src.cyberagent.core.logging import configure_autogen_logging
from src.rbac.enforcer import get_enforcer
from src.registry import register_systems
from src.cyberagent.core.runtime import (
    get_runtime,
    start_cli_executor,
    stop_runtime,
)
from src.cyberagent.secrets import get_secret

logger = logging.getLogger(__name__)


class SuggestionRuntime(Protocol):
    async def send_message(  # noqa: D401
        self,
        message: object,
        recipient: AgentId,
        *,
        sender: AgentId | None = None,
        cancellation_token: CancellationToken | None = None,
        message_id: str | None = None,
    ) -> object:
        """Send a message to the runtime."""


async def run_headless_session(initial_message: str | None = None) -> None:
    """
    Run the headless CLI session that forwards user input to the runtime.
    """
    init_db()
    if os.environ.get("CYBERAGENT_ACTIVE_TEAM_ID") is None:
        team_id = get_last_team_id()
        if team_id is None:
            print(
                "No teams found. Run 'cyberagent onboarding' to create your first team."
            )
            return
        os.environ["CYBERAGENT_ACTIVE_TEAM_ID"] = str(team_id)
    await register_systems()
    enforcer = get_enforcer()
    enforcer.clear_policy()

    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    configure_autogen_logging(logs_dir)

    runtime = get_runtime()
    await start_cli_executor()
    recipient = AgentId(type=UserAgent.__name__, key="root")
    if initial_message:
        message = UserMessage(content=initial_message, source="User")
        message.metadata = {
            "channel": DEFAULT_CHANNEL,
            "session_id": DEFAULT_SESSION_ID,
        }
        await runtime.send_message(message=message, recipient=recipient)

    queue: asyncio.Queue[str] = asyncio.Queue()
    stop_event = asyncio.Event()
    reader_task = asyncio.create_task(read_stdin_loop(queue, stop_event))
    forward_task = asyncio.create_task(
        forward_user_messages(queue, runtime, recipient, stop_event)
    )
    suggestion_task = asyncio.create_task(
        _process_suggestion_queue(runtime, stop_event)
    )
    telegram_task: asyncio.Task[None] | None = None
    webhook_server: TelegramWebhookServer | None = None
    token = get_secret("TELEGRAM_BOT_TOKEN")
    webhook_url = os.environ.get("TELEGRAM_WEBHOOK_URL")
    if token and webhook_url:
        host = os.environ.get("TELEGRAM_WEBHOOK_HOST", "0.0.0.0")
        port = int(os.environ.get("TELEGRAM_WEBHOOK_PORT", "8080"))
        secret = get_secret("TELEGRAM_WEBHOOK_SECRET")
        webhook_server = TelegramWebhookServer(
            token=token,
            runtime=runtime,
            recipient=recipient,
            loop=asyncio.get_running_loop(),
            host=host,
            port=port,
            secret=secret,
        )
        webhook_server.start(webhook_url)
    elif token:
        telegram_poller = TelegramPoller(token, runtime, recipient, stop_event)
        telegram_task = asyncio.create_task(telegram_poller.run())

    try:
        await stop_event.wait()
    finally:
        reader_task.cancel()
        forward_task.cancel()
        suggestion_task.cancel()
        if webhook_server:
            webhook_server.stop()
        if telegram_task:
            telegram_task.cancel()
        await stop_runtime()


async def _process_suggestion_queue(
    runtime: SuggestionRuntime, stop_event: asyncio.Event
) -> None:
    while not stop_event.is_set():
        suggestions = read_queued_suggestions()
        for suggestion in suggestions:
            if stop_event.is_set():
                break
            message = UserMessage(content=suggestion.payload_text, source="User")
            message.metadata = {
                "channel": DEFAULT_CHANNEL,
                "session_id": DEFAULT_SESSION_ID,
            }
            try:
                await runtime.send_message(
                    message=message,
                    recipient=AgentId(type="System4", key="root"),
                    sender=AgentId(type="UserAgent", key="root"),
                )
                ack_suggestion(suggestion.path)
            except Exception:  # pragma: no cover - safety net
                logger.exception("Failed to deliver suggestion %s", suggestion.path)
                break
        await asyncio.sleep(SUGGEST_QUEUE_POLL_SECONDS)
