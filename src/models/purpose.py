"""Compatibility shim for src.cyberagent.db.models.purpose."""

from src.cyberagent.db.models.purpose import *  # noqa: F401,F403
from src.cyberagent.db.models import purpose as _module

__all__ = [name for name in dir(_module) if not name.startswith("_")]
