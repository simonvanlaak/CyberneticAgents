from __future__ import annotations

import logging

from src.cyberagent.channels.telegram import session_store
from src.cyberagent.channels.telegram.outbound import (
    send_message as send_telegram_message,
)
from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.onboarding_discovery import build_onboarding_interview_prompt
from src.cyberagent.cli.suggestion_queue import enqueue_suggestion
from src.cyberagent.secrets import get_secret

logger = logging.getLogger(__name__)


def start_onboarding_interview(
    *,
    user_name: str,
    repo_url: str,
    profile_links: list[str],
) -> None:
    """
    Start the onboarding interview immediately via Telegram or CLI fallback.

    Args:
        user_name: User display name.
        repo_url: Obsidian vault repo URL.
        profile_links: Profile links provided during onboarding.
    """
    first_question = get_message("onboarding", "onboarding_first_question")
    welcome_message = get_message(
        "onboarding", "telegram_onboarding_welcome", user_name=user_name
    )
    sent, session_found = send_onboarding_intro_messages(
        welcome_message=welcome_message,
        first_question=first_question,
    )
    if not sent:
        print(welcome_message)
        print(first_question)
    if get_secret("TELEGRAM_BOT_TOKEN"):
        print(get_message("onboarding", "telegram_session_required"))
    prompt = build_onboarding_interview_prompt(
        user_name=user_name,
        repo_url=repo_url,
        profile_links=profile_links,
        first_question=first_question,
    )
    enqueue_suggestion(prompt)


def select_latest_telegram_session() -> session_store.TelegramSession | None:
    sessions = session_store.list_sessions()
    if not sessions:
        return None
    return max(sessions, key=lambda session: session.last_activity)


def send_onboarding_intro_messages(
    *, welcome_message: str, first_question: str
) -> tuple[bool, bool]:
    if not get_secret("TELEGRAM_BOT_TOKEN"):
        return False, False
    session = select_latest_telegram_session()
    if session is None:
        return False, False
    try:
        send_telegram_message(session.telegram_chat_id, welcome_message)
        send_telegram_message(session.telegram_chat_id, first_question)
    except Exception as exc:
        logger.warning("Failed to send onboarding Telegram messages: %s", exc)
        return False, True
    return True, True
