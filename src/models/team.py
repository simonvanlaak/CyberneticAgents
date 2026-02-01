"""Compatibility shim for src.cyberagent.db.models.team."""

from src.cyberagent.db.models.team import *  # noqa: F401,F403
from src.cyberagent.db.models import team as _module

__all__ = [name for name in dir(_module) if not name.startswith("_")]
