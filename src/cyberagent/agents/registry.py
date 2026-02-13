"""Canonical system registration entrypoint.

This module currently re-exports the legacy implementation while migration is
in progress.
"""

from src.registry import register_systems

__all__ = ["register_systems"]
