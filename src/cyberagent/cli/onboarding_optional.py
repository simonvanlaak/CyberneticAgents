from __future__ import annotations

import os

from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli import onboarding_telegram
from src.cyberagent.cli.onboarding_secrets import (
    VAULT_NAME,
    load_secret_from_1password,
)


def _warn_optional_api_keys() -> None:
    optional = [
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGSMITH_API_KEY",
    ]
    missing: list[str] = []
    for key in optional:
        if os.environ.get(key):
            continue
        loaded = load_secret_from_1password(
            vault_name=VAULT_NAME,
            item_name=key,
            field_label="credential",
        )
        if loaded:
            continue
        missing.append(key)
    if missing:
        missing_str = ", ".join(missing)
        print(
            get_message(
                "onboarding",
                "optional_api_keys_missing",
                missing_keys=missing_str,
            )
        )


def _offer_optional_telegram_setup() -> None:
    if not onboarding_telegram.sys.stdin.isatty():
        return
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        onboarding_telegram._offer_optional_telegram_username_setup()
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            message = get_message("onboarding", "feature_telegram")
            print(get_message("onboarding", "feature_ready", message=message))
        return
    loaded = onboarding_telegram._load_secret_from_1password("TELEGRAM_BOT_TOKEN")
    if loaded:
        os.environ["TELEGRAM_BOT_TOKEN"] = loaded
        onboarding_telegram._offer_optional_telegram_username_setup()
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            message = get_message("onboarding", "feature_telegram")
            print(get_message("onboarding", "feature_ready", message=message))
        return
    print(get_message("onboarding", "telegram_botfather_instructions"))
    botfather = onboarding_telegram.botfather_link()
    print(f"Open: {botfather}")
    qr = onboarding_telegram.render_telegram_qr(botfather)
    if qr:
        print(qr)
    print(get_message("onboarding", "telegram_not_configured"))
    if not onboarding_telegram.prompt_store_secret_in_1password(
        env_name="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token",
        doc_hint=onboarding_telegram.TELEGRAM_DOC_HINT,
        vault_name=VAULT_NAME,
    ):
        return
    loaded = onboarding_telegram._load_secret_from_1password("TELEGRAM_BOT_TOKEN")
    if loaded:
        os.environ["TELEGRAM_BOT_TOKEN"] = loaded
    onboarding_telegram._offer_optional_telegram_username_setup()
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        message = get_message("onboarding", "feature_telegram")
        print(get_message("onboarding", "feature_ready", message=message))


def _offer_optional_telegram_webhook_setup() -> None:
    onboarding_telegram._offer_optional_telegram_webhook_setup()
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        message = get_message("onboarding", "feature_telegram")
        print(get_message("onboarding", "feature_ready", message=message))
