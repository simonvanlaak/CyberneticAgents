from __future__ import annotations

import os

from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.onboarding_constants import DEFAULT_NOTION_TOKEN_ENV
from src.cyberagent.cli.onboarding_secrets import (
    VAULT_NAME,
    load_secret_from_1password_with_error,
)
from src.cyberagent.cli.onboarding_vault import prompt_store_secret_in_1password


def check_notion_token() -> bool:
    token_env = DEFAULT_NOTION_TOKEN_ENV
    if os.environ.get(token_env):
        print(get_message("onboarding", "notion_ready"))
        return True
    loaded, error = load_secret_from_1password_with_error(
        vault_name=VAULT_NAME,
        item_name=token_env,
        field_label="credential",
    )
    if loaded:
        os.environ[token_env] = loaded
        print(get_message("onboarding", "notion_ready"))
        return True
    if error:
        print(
            get_message(
                "onboarding",
                "notion_token_missing_with_error",
                token_env=token_env,
                error=error,
            )
        )
    else:
        print(
            get_message(
                "onboarding",
                "notion_token_missing",
                token_env=token_env,
                vault_name=VAULT_NAME,
            )
        )
    print(get_message("onboarding", "field_name_hint"))
    if not prompt_store_secret_in_1password(
        env_name=token_env,
        description="Notion API key",
        doc_hint=None,
        vault_name=VAULT_NAME,
    ):
        return False
    loaded, _error = load_secret_from_1password_with_error(
        vault_name=VAULT_NAME,
        item_name=token_env,
        field_label="credential",
    )
    if not loaded:
        return False
    os.environ[token_env] = loaded
    print(get_message("onboarding", "notion_ready"))
    return True
