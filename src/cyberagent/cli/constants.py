from __future__ import annotations

from dataclasses import dataclass
from typing import Any

KEYRING_SERVICE = "cyberagent-cli"
SERVE_COMMAND = "serve"
DASHBOARD_COMMAND = "dashboard"
KANBAN_COMMAND = "kanban"
TEST_START_ENV = "CYBERAGENT_TEST_NO_RUNTIME"
SUGGEST_COMMAND = 'cyberagent suggest "Describe the task"'
START_COMMAND = "cyberagent start"
ONBOARDING_COMMAND = "cyberagent onboarding"
INBOX_COMMAND = "cyberagent inbox"
WATCH_COMMAND = "cyberagent watch"
STATUS_COMMAND = "cyberagent status"
INBOX_HINT_COMMAND = "cyberagent inbox"
WATCH_HINT_COMMAND = "cyberagent watch"
SUGGEST_SHUTDOWN_TIMEOUT_SECONDS = 1.0
SUGGEST_SEND_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class ParsedSuggestion:
    payload_text: str
    payload_object: Any
