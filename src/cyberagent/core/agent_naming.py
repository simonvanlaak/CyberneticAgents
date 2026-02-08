from __future__ import annotations

import re

_VALID_SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_INVALID_CHAR_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")


def normalize_message_source(source: str | None, fallback: str = "system") -> str:
    """
    Return a model-compatible message source identifier.

    AutoGen/OpenAI message transformers only allow letters, numbers, underscore,
    and hyphen in `source` names.
    """
    candidate = str(source or "").strip()
    if not candidate:
        return fallback
    if _VALID_SOURCE_PATTERN.fullmatch(candidate) is not None:
        return candidate
    normalized = _INVALID_CHAR_PATTERN.sub("_", candidate).strip("_")
    return normalized or fallback
