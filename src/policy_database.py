# -*- coding: utf-8 -*-
"""
Policy Prompt Database Management

Manages policy prompts for Systems 1-4 in SQLite database.
"""

import os
from typing import List, Optional

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# Database setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "CyberneticAgents.db")
DATABASE_URL = os.environ.get("CYBERAGENT_DB_URL", f"sqlite:///{DEFAULT_DB_PATH}")

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class PolicyPrompt(Base):
    """Policy prompt database model."""

    __tablename__ = "policy_prompts"

    id = Column(Integer, primary_key=True)
    system_id = Column(String(100), unique=True, nullable=False)
    content = Column(String(5000), nullable=False)  # 5000 character limit


def init_database():
    """Initialize database and create tables."""
    # Ensure data directory exists
    _ensure_data_dir()
    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        if "disk i/o" in str(exc).lower():
            backup = _attempt_recover_sqlite()
            if backup:
                _configure_engine(DATABASE_URL)
                Base.metadata.create_all(bind=engine)
                return
            raise RuntimeError(
                "SQLite disk I/O error while initializing policy database."
            ) from exc
        raise


def get_session():
    """Get database session."""
    return SessionLocal()


def _configure_engine(database_url: str) -> None:
    global engine
    global SessionLocal
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _ensure_data_dir() -> None:
    if not DATABASE_URL.startswith("sqlite:///"):
        return
    data_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)


def _attempt_recover_sqlite() -> str | None:
    if not DATABASE_URL.startswith("sqlite:///"):
        return None
    db_path = DEFAULT_DB_PATH
    if not os.path.exists(db_path) or not os.path.isfile(db_path):
        return None
    backup_path = f"{db_path}.corrupt"
    try:
        os.replace(db_path, backup_path)
    except OSError:
        return None
    return backup_path


def create_policy_prompt(system_id: str, content: str):
    """Create new policy prompt."""
    session = get_session()
    try:
        # Validate content length
        if len(content) > 5000:
            raise ValueError("Policy content exceeds 5000 character limit")

        # Check if policy already exists
        existing = session.query(PolicyPrompt).filter_by(system_id=system_id).first()
        if existing:
            raise ValueError(f"Policy already exists for system_id: {system_id}")

        policy = PolicyPrompt(system_id=system_id, content=content)
        session.add(policy)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_policy_prompt(system_id: str) -> Optional[PolicyPrompt]:
    """Get policy prompt by system ID."""
    session = get_session()
    try:
        return session.query(PolicyPrompt).filter_by(system_id=system_id).first()
    finally:
        session.close()


def update_policy_prompt(system_id: str, content: str) -> PolicyPrompt | None:
    """Update existing policy prompt."""
    session = get_session()
    try:
        # Validate content length
        if len(content) > 5000:
            raise ValueError("Policy content exceeds 5000 character limit")

        # Get the existing policy
        policy = session.query(PolicyPrompt).filter_by(system_id=system_id).first()
        if not policy:
            return None

        policy.content = content  # type: ignore[assignment]
        session.commit()
        session.refresh(policy)
        return policy
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def delete_policy_prompt(system_id: str) -> bool:
    """Delete policy prompt."""
    session = get_session()
    try:
        policy = session.query(PolicyPrompt).filter_by(system_id=system_id).first()
        if not policy:
            return False

        session.delete(policy)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def list_policy_prompts() -> List[PolicyPrompt]:
    """List all policy prompts."""
    session = get_session()
    try:
        return session.query(PolicyPrompt).all()
    finally:
        session.close()


# Initialize database on import
init_database()
