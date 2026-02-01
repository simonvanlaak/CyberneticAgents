# -*- coding: utf-8 -*-
"""
Database utility functions.
"""

from src.cyberagent.db import init_db


def get_db():
    """Get a database session"""
    db = init_db.SessionLocal()
    try:
        yield db
    finally:
        db.close()
