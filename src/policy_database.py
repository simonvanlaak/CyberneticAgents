# -*- coding: utf-8 -*-
"""
Policy Prompt Database Management

Manages policy prompts for Systems 1-4 in SQLite database.
"""

import os
from typing import List, Optional

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'CyberneticAgents.db')}"

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
    data_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)

    Base.metadata.create_all(bind=engine)


def get_session():
    """Get database session."""
    return SessionLocal()


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

        # Create updated policy object
        updated_policy = PolicyPrompt(system_id=system_id, content=content)

        # Delete old and add new
        session.delete(policy)
        session.add(updated_policy)
        session.commit()

        return updated_policy
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
