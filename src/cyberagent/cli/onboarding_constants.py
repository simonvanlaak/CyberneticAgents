from __future__ import annotations

from src.cyberagent.core.paths import resolve_data_path

DEFAULT_GIT_TOKEN_ENV = "GITHUB_READONLY_TOKEN"
DEFAULT_TOKEN_USERNAME = "x-access-token"
DEFAULT_NOTION_TOKEN_ENV = "NOTION_API_KEY"
ONBOARDING_SUMMARY_DIR = resolve_data_path("onboarding")
GIT_SYNC_TIMEOUT_SECONDS = 600
