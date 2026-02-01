"""Compatibility shim for src.cyberagent.cli.__init__."""

from src.cyberagent.cli.__init__ import *  # noqa: F401,F403
from src.cyberagent.cli import __init__ as _module

__all__ = [value for value in dir(_module) if not value.startswith("_")]
