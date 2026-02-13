from __future__ import annotations

import inspect
from collections.abc import Callable

from src.cyberagent.cli.onboarding_constants import DEFAULT_NOTION_TOKEN_ENV

CONDITIONAL_ONBOARDING_SECRETS = {
    DEFAULT_NOTION_TOKEN_ENV: {"notion"},
}


def normalize_pkm_source(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def run_technical_checks_with_context(
    check_fn: Callable[..., bool], *, pkm_source: str | None
) -> bool:
    params = inspect.signature(check_fn).parameters
    if "pkm_source" in params:
        return check_fn(pkm_source=pkm_source)
    return check_fn()


def should_require_tool_secret(env_name: str, pkm_source: str | None) -> bool:
    required_for_pkm = CONDITIONAL_ONBOARDING_SECRETS.get(env_name)
    if required_for_pkm is None:
        return True
    return pkm_source in required_for_pkm
