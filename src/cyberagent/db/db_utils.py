# -*- coding: utf-8 -*-
"""
Database utility functions.
"""

from src.cyberagent.db.init_db import SessionLocal


def get_db():
    """Get a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
