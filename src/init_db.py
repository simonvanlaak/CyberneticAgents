"""
Compatibility shim for src.cyberagent.db.init_db.
"""

from src.cyberagent.db import init_db as _init_db
from src.cyberagent.db.init_db import *  # noqa: F401,F403

__all__ = [name for name in dir(_init_db) if not name.startswith("_")]
