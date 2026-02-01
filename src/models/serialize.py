"""Compatibility shim for src.cyberagent.domain.serialize."""

from src.cyberagent.domain.serialize import *  # noqa: F401,F403
from src.cyberagent.domain import serialize as _serialize

__all__ = [name for name in dir(_serialize) if not name.startswith("_")]
