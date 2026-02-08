from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Protocol

from autogen_core import AgentId, CancellationToken
from src.agents.messages import InitiativeAssignMessage, TaskReviewMessage, UserMessage
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
from src.cyberagent.cli.agent_message_queue import (
    ack_agent_message,
    defer_agent_message,
    read_queued_agent_messages,
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
from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.core.paths import get_logs_dir
from src.cyberagent.core.agent_naming import normalize_message_source

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


def _is_disk_io_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    if "disk i/o error" in message:
        return True
    seen: set[int] = set()
    current: BaseException | None = exc.__cause__ or exc.__context__
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if "disk i/o error" in str(current).lower():
            return True
        current = current.__cause__ or current.__context__
    return False


def _handle_disk_io_error(
    exc: BaseException, stop_event: asyncio.Event, context: str
) -> None:
    logger.exception("Database write failed during %s.", context)
    print(get_message("headless", "db_write_failed"))
    print(get_message("headless", "db_write_hint_disk_io"))
    stop_event.set()


async def run_headless_session(initial_message: str | None = None) -> None:
    """
    Run the headless CLI session that forwards user input to the runtime.
    """
    init_db()
    if os.environ.get("CYBERAGENT_ACTIVE_TEAM_ID") is None:
        team_id = get_last_team_id()
        if team_id is None:
            print(get_message("headless", "no_teams_found"))
            return
        os.environ["CYBERAGENT_ACTIVE_TEAM_ID"] = str(team_id)
    await register_systems()
    enforcer = get_enforcer()
    enforcer.clear_policy()

    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    configure_autogen_logging(str(logs_dir))

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
    agent_message_task = asyncio.create_task(
        _process_agent_message_queue(runtime, stop_event)
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
        agent_message_task.cancel()
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
            except Exception as exc:  # pragma: no cover - safety net
                if _is_disk_io_error(exc):
                    _handle_disk_io_error(exc, stop_event, "suggestion delivery")
                    break
                logger.exception("Failed to deliver suggestion %s", suggestion.path)
                break
        await asyncio.sleep(SUGGEST_QUEUE_POLL_SECONDS)


def _build_agent_message(message_type: str, payload: dict[str, object]) -> object:
    if message_type == "initiative_assign":
        initiative_id = payload.get("initiative_id")
        if not isinstance(initiative_id, int):
            raise ValueError("initiative_assign payload missing initiative_id")
        source = payload.get("source")
        content = payload.get("content")
        return InitiativeAssignMessage(
            initiative_id=initiative_id,
            source=normalize_message_source(
                str(source) if source is not None else "Onboarding"
            ),
            content=str(content) if content is not None else "Start initiative.",
        )
    if message_type == "task_review":
        task_id = payload.get("task_id")
        assignee_agent_id_str = payload.get("assignee_agent_id_str")
        if not isinstance(task_id, int):
            raise ValueError("task_review payload missing task_id")
        if not isinstance(assignee_agent_id_str, str) or not assignee_agent_id_str:
            raise ValueError("task_review payload missing assignee_agent_id_str")
        source = payload.get("source")
        content = payload.get("content")
        return TaskReviewMessage(
            task_id=task_id,
            assignee_agent_id_str=assignee_agent_id_str,
            source=normalize_message_source(
                str(source) if source is not None else assignee_agent_id_str
            ),
            content=str(content) if content is not None else "Task completed.",
        )
    raise ValueError(f"Unsupported agent message type: {message_type}")


async def _process_agent_message_queue(
    runtime: SuggestionRuntime, stop_event: asyncio.Event
) -> None:
    while not stop_event.is_set():
        messages = read_queued_agent_messages()
        for message in messages:
            if stop_event.is_set():
                break
            if message.next_attempt_at > time.time():
                continue
            try:
                payload_message = _build_agent_message(
                    message.message_type, message.payload
                )
                recipient = AgentId.from_str(message.recipient)
                sender = AgentId.from_str(message.sender) if message.sender else None
                await runtime.send_message(
                    message=payload_message,
                    recipient=recipient,
                    sender=sender,
                )
                ack_agent_message(message.path)
            except Exception as exc:  # pragma: no cover - safety net
                if _is_disk_io_error(exc):
                    _handle_disk_io_error(exc, stop_event, "agent message delivery")
                    break
                defer_agent_message(path=message.path, error=str(exc))
                logger.exception("Failed to deliver agent message %s", message.path)
                continue
        await asyncio.sleep(SUGGEST_QUEUE_POLL_SECONDS)
