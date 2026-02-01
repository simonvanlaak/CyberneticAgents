"""Compatibility shim for src.team_state."""

from src import team_state as _team_state
from src.team_state import *  # noqa: F401,F403

__all__ = [name for name in dir(_team_state) if not name.startswith("_")]
