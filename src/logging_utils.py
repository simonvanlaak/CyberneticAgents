"""Compatibility shim for src.cyberagent.core.logging."""

from src.cyberagent.core import logging as _logging
from src.cyberagent.core.logging import *  # noqa: F401,F403

__all__ = [name for name in dir(_logging) if not name.startswith("_")]
