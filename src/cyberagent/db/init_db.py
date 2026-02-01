"""
Common database components shared across all modules
"""

import os
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Create database directory if it doesn't exist
os.makedirs("data", exist_ok=True)

# SQLite database setup
DATABASE_URL = os.environ.get("CYBERAGENT_DB_URL", "sqlite:///data/CyberneticAgents.db")
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Single Base instance for all models
Base = declarative_base()


def init_db():
    """Initialize the database and create all tables"""
    # Import models to ensure they're registered with Base
    from src.models.initiative import Initiative
    from src.models.policy import Policy
    from src.models.purpose import Purpose
    from src.models.strategy import Strategy
    from src.models.system import System
    from src.models.task import Task
    from src.models.team import Team

    # Create all tables
    Base.metadata.create_all(bind=engine)
    _ensure_team_last_active_column()


def _ensure_team_last_active_column() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.connect() as connection:
        columns = connection.execute(text("PRAGMA table_info(teams);")).fetchall()
        column_names = {column[1] for column in columns}
        if "last_active_at" in column_names:
            return
        connection.execute(text("ALTER TABLE teams ADD COLUMN last_active_at DATETIME"))
        connection.execute(
            text("UPDATE teams SET last_active_at = :now WHERE last_active_at IS NULL"),
            {"now": datetime.utcnow().isoformat()},
        )


def configure_database(database_url: str) -> None:
    """Configure the database connection (used mainly for tests)."""
    global DATABASE_URL
    global engine
    global SessionLocal
    DATABASE_URL = database_url
    engine = create_engine(DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_database_path() -> str:
    """Return the sqlite database path for the current DATABASE_URL."""
    parsed = urlparse(DATABASE_URL)
    if parsed.scheme != "sqlite":
        raise ValueError("Database path is only available for sqlite databases.")
    if parsed.path:
        if parsed.path == "/:memory:":
            return ":memory:"
        normalized = os.path.normpath(parsed.path)
        if normalized.startswith("//"):
            while normalized.startswith("//"):
                normalized = normalized[1:]
            return normalized
        if normalized.startswith("/"):
            return normalized[1:]
        return normalized
    return "data/CyberneticAgents.db"


# Note: init_db() is NOT called automatically during import to avoid circular dependencies
# It should be called explicitly when the application starts
