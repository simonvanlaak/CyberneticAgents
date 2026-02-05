from __future__ import annotations

import logging
import os
import sys

import requests

from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.onboarding_secrets import load_secret_from_1password
from src.cyberagent.cli.onboarding_vault import (
    prompt_store_secret_in_1password,
    prompt_yes_no,
)
from src.cyberagent.cli.telegram_qr import botfather_link, render_telegram_qr

TELEGRAM_DOC_HINT = "docs/technical/telegram_setup.md"
TELEGRAM_GET_ME_URL = "https://api.telegram.org/bot{token}/getMe"
TELEGRAM_API_TIMEOUT_SECONDS = 10

logger = logging.getLogger(__name__)


def offer_optional_telegram_setup() -> None:
    if not sys.stdin.isatty():
        return
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        _offer_optional_telegram_username_setup()
        _offer_optional_telegram_webhook_setup()
        return
    loaded = _load_secret_from_1password("TELEGRAM_BOT_TOKEN")
    if loaded:
        os.environ["TELEGRAM_BOT_TOKEN"] = loaded
        _offer_optional_telegram_username_setup()
        _offer_optional_telegram_webhook_setup()
        return
    print(get_message("onboarding", "telegram_botfather_instructions"))
    botfather = botfather_link()
    print(f"Open: {botfather}")
    qr = render_telegram_qr(botfather)
    if qr:
        print(qr)
    print(get_message("onboarding", "telegram_not_configured"))
    if not prompt_store_secret_in_1password(
        env_name="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token",
        doc_hint=TELEGRAM_DOC_HINT,
        vault_name="CyberneticAgents",
    ):
        return
    loaded = _load_secret_from_1password("TELEGRAM_BOT_TOKEN")
    if loaded:
        os.environ["TELEGRAM_BOT_TOKEN"] = loaded
    _offer_optional_telegram_username_setup()
    _offer_optional_telegram_webhook_setup()


def _offer_optional_telegram_username_setup() -> None:
    if os.environ.get("TELEGRAM_BOT_USERNAME"):
        return
    loaded = _load_secret_from_1password("TELEGRAM_BOT_USERNAME")
    if loaded:
        os.environ["TELEGRAM_BOT_USERNAME"] = loaded
        return
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        fetched = _fetch_bot_username_from_token(token)
        if fetched:
            os.environ["TELEGRAM_BOT_USERNAME"] = fetched
            return
    prompt_store_secret_in_1password(
        env_name="TELEGRAM_BOT_USERNAME",
        description="Telegram bot username (without @)",
        doc_hint=TELEGRAM_DOC_HINT,
        vault_name="CyberneticAgents",
    )


def _offer_optional_telegram_webhook_setup() -> None:
    if os.environ.get("TELEGRAM_WEBHOOK_SECRET"):
        return
    print(get_message("onboarding", "webhook_mode_optional"))
    if not prompt_yes_no(get_message("onboarding", "webhook_secret_prompt")):
        print(get_message("onboarding", "setup_guide_hint", doc_hint=TELEGRAM_DOC_HINT))
        return
    prompt_store_secret_in_1password(
        env_name="TELEGRAM_WEBHOOK_SECRET",
        description="Telegram webhook secret",
        doc_hint=TELEGRAM_DOC_HINT,
        vault_name="CyberneticAgents",
    )


def _load_secret_from_1password(item_name: str) -> str | None:
    return load_secret_from_1password(
        vault_name="CyberneticAgents", item_name=item_name, field_label="credential"
    )


def _fetch_bot_username_from_token(token: str) -> str | None:
    """
    Fetch the Telegram bot username using the Bot API token.

    Args:
        token: Telegram bot token.

    Returns:
        The bot username without the leading @, or None if unavailable.
    """
    try:
        response = requests.get(
            TELEGRAM_GET_ME_URL.format(token=token),
            timeout=TELEGRAM_API_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning("Failed to fetch Telegram bot username: %s", exc)
        return None
    if response.status_code != 200:
        logger.warning("Telegram getMe failed with status %s.", response.status_code)
        return None
    try:
        payload = response.json()
    except ValueError:
        logger.warning("Telegram getMe returned invalid JSON.")
        return None
    if not payload.get("ok"):
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    username = result.get("username")
    if not isinstance(username, str):
        return None
    cleaned = username.strip().lstrip("@")
    return cleaned or None
