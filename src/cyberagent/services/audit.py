"""Shared audit logging helpers."""

from __future__ import annotations

import logging
from typing import Any


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    """
    Emit a structured audit event.

    Args:
        event: Event name.
        **fields: Structured metadata for the event.
    """
    logger = logging.getLogger(
        f"src.cyberagent.services.{fields.get('service', 'audit')}"
    )
    extra = dict(fields)
    extra.pop("service", None)
    logger.log(level, event, extra=extra)
