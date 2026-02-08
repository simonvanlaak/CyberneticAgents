from __future__ import annotations

import logging
import os

from src.cyberagent.channels.telegram import session_store
from src.cyberagent.channels.telegram.outbound import (
    send_message as send_telegram_message,
)
from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.onboarding_discovery import build_onboarding_interview_prompt
from src.cyberagent.cli.suggestion_queue import enqueue_suggestion
from src.cyberagent.cli import onboarding_telegram
from src.cyberagent.cli.telegram_qr import build_bot_link, render_telegram_qr
from src.cyberagent.secrets import get_secret

logger = logging.getLogger(__name__)


def start_onboarding_interview(
    *,
    user_name: str,
    pkm_source: str | None = None,
    repo_url: str,
    profile_links: list[str],
) -> None:
    """
    Start the onboarding interview immediately via Telegram or CLI fallback.

    Args:
        user_name: User display name.
        pkm_source: PKM source selection.
        repo_url: GitHub repo URL for markdown PKM (if applicable).
        profile_links: Profile links provided during onboarding.
    """
    normalized_pkm_source = str(pkm_source or "").strip().lower()
    if not normalized_pkm_source:
        normalized_pkm_source = "github" if repo_url else "skip"
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
    token = get_secret("TELEGRAM_BOT_TOKEN")
    if token:
        print(get_message("onboarding", "telegram_session_required"))
        bot_link = build_bot_link()
        if not bot_link:
            fetched = onboarding_telegram._fetch_bot_username_from_token(token)
            if fetched:
                os.environ.setdefault("TELEGRAM_BOT_USERNAME", fetched)
                bot_link = build_bot_link()
        if bot_link:
            print(f"Open: {bot_link}")
            qr = render_telegram_qr(bot_link)
            if qr:
                print(qr)
    prompt = build_onboarding_interview_prompt(
        user_name=user_name,
        pkm_source=normalized_pkm_source,
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
