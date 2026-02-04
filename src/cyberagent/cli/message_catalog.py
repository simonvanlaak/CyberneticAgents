from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MESSAGES: dict[str, dict[str, str]] | None = None


def _normalize_message(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return "\n".join(value) + "\n"
    raise ValueError("CLI message values must be strings or arrays of strings.")


def _load_messages() -> dict[str, dict[str, str]]:
    catalog_path = Path(__file__).with_name("messages.json")
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("CLI messages JSON must be an object.")
    messages: dict[str, dict[str, str]] = {}
    for group, payload in data.items():
        if not isinstance(group, str) or not isinstance(payload, dict):
            raise ValueError("CLI messages JSON must map group names to objects.")
        group_map: dict[str, str] = {}
        for key, value in payload.items():
            if not isinstance(key, str):
                raise ValueError("CLI message keys must be strings.")
            group_map[key] = _normalize_message(value)
        messages[group] = group_map
    return messages


def _get_messages() -> dict[str, dict[str, str]]:
    global _MESSAGES
    if _MESSAGES is None:
        _MESSAGES = _load_messages()
    return _MESSAGES


def get_message(group: str, key: str, **kwargs: Any) -> str:
    """
    Fetch and format a CLI message string.

    Args:
        group: Message group name (e.g., "onboarding").
        key: Message key name within the group.
        **kwargs: Optional formatting values.

    Returns:
        The formatted message string.

    Raises:
        KeyError: If the group or key is missing.
        ValueError: If the messages JSON is invalid.
    """
    messages = _get_messages()
    if group not in messages:
        raise KeyError(f"Unknown CLI message group: {group}")
    group_messages = messages[group]
    if key not in group_messages:
        raise KeyError(f"Unknown CLI message key: {group}.{key}")
    message = group_messages[key]
    return message.format(**kwargs)
