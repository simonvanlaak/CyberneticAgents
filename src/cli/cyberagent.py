"""Compatibility shim for src.cyberagent.cli.cyberagent."""

from src.cyberagent.cli.cyberagent import *  # noqa: F401,F403
from src.cyberagent.cli import cyberagent as _module

__all__ = [value for value in dir(_module) if not value.startswith("_")]
