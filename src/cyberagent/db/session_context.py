"""Shared SQLAlchemy session context helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from src.cyberagent.db import init_db


@contextmanager
def managed_session(*, commit: bool = False) -> Iterator[Session]:
    """Yield a DB session and handle commit/rollback/close lifecycle.

    Args:
        commit: When True, commit on success and roll back on exceptions.
    """

    session = init_db.SessionLocal()
    try:
        yield session
        if commit:
            session.commit()
    except Exception:
        if commit:
            session.rollback()
        raise
    finally:
        session.close()
