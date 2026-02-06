"""
Common database components shared across all modules
"""

import os
from datetime import datetime
from datetime import timezone
from pathlib import Path
from urllib.parse import urlparse

from src.cyberagent.core.paths import get_data_dir

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker


def _default_database_url() -> str:
    db_path = (get_data_dir() / "CyberneticAgents.db").resolve()
    return f"sqlite:///{db_path}"


def _resolve_database_url() -> str:
    return os.environ.get("CYBERAGENT_DB_URL") or _default_database_url()


def _ensure_database_url_current() -> None:
    if not _DATABASE_URL_FROM_ENV:
        return
    resolved = _resolve_database_url()
    if DATABASE_URL != resolved:
        configure_database(resolved, from_env=True)


# SQLite database setup
# Create database directory if it doesn't exist
get_data_dir().mkdir(parents=True, exist_ok=True)

# SQLite database setup
DATABASE_URL = _resolve_database_url()
_DATABASE_URL_FROM_ENV = True
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Single Base instance for all models
Base = declarative_base()


def init_db():
    """Initialize the database and create all tables"""
    _ensure_database_url_current()
    _ensure_db_writable()
    # Import models to ensure they're registered with Base
    from src.cyberagent.db.models.initiative import Initiative
    from src.cyberagent.db.models.policy import Policy
    from src.cyberagent.db.models.procedure import Procedure
    from src.cyberagent.db.models.procedure_run import ProcedureRun
    from src.cyberagent.db.models.procedure_task import ProcedureTask
    from src.cyberagent.db.models.purpose import Purpose
    from src.cyberagent.db.models.routing_rule import RoutingRule
    from src.cyberagent.db.models.dead_letter_message import DeadLetterMessage
    from src.cyberagent.db.models.recursion import Recursion
    from src.cyberagent.db.models.strategy import Strategy
    from src.cyberagent.db.models.system import System
    from src.cyberagent.db.models.task import Task
    from src.cyberagent.db.models.telegram_pairing import TelegramPairing
    from src.cyberagent.db.models.team import Team

    _ = (
        Initiative,
        Policy,
        Procedure,
        ProcedureRun,
        ProcedureTask,
        Purpose,
        RoutingRule,
        DeadLetterMessage,
        Recursion,
        Strategy,
        System,
        Task,
        TelegramPairing,
        Team,
    )

    # Create all tables
    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        if "disk i/o error" in str(exc).lower():
            db_path = get_database_path()
            backup_path = _attempt_recover_sqlite(db_path)
            if backup_path is not None:
                configure_database(DATABASE_URL)
            try:
                Base.metadata.create_all(bind=engine)
            except OperationalError as retry_exc:
                hint = (
                    f" Backup saved to {backup_path}."
                    if backup_path is not None
                    else ""
                )
                raise RuntimeError(
                    f"SQLite disk I/O error while initializing database at {db_path}."
                    f"{hint} Check permissions and available disk space."
                ) from retry_exc
            else:
                _ensure_team_last_active_column()
                return
        raise
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


def configure_database(database_url: str, *, from_env: bool = False) -> None:
    """Configure the database connection (used mainly for tests)."""
    global DATABASE_URL
    global engine
    global SessionLocal
    global _DATABASE_URL_FROM_ENV
    DATABASE_URL = database_url
    _DATABASE_URL_FROM_ENV = from_env
    engine = create_engine(DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_database_path() -> str:
    """Return the sqlite database path for the current DATABASE_URL."""
    _ensure_database_url_current()
    parsed = urlparse(DATABASE_URL)
    if parsed.scheme != "sqlite":
        raise ValueError("Database path is only available for sqlite databases.")
    raw_path = parsed.path or ""
    if raw_path:
        if raw_path == "/:memory:":
            return ":memory:"
        if raw_path.startswith("//"):
            normalized = os.path.normpath(raw_path)
            if normalized.startswith("//"):
                return "/" + normalized.lstrip("/")
            return normalized
        normalized = os.path.normpath(raw_path)
        if normalized.startswith("/"):
            return normalized.lstrip("/")
        return normalized
    return str((get_data_dir() / "CyberneticAgents.db").resolve())


def _ensure_db_writable() -> None:
    _ensure_database_url_current()
    db_path = get_database_path()
    if db_path == ":memory:":
        return
    db_file = Path(db_path)
    db_dir = db_file.parent
    try:
        db_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PermissionError(f"Database directory not writable: {db_dir}") from exc
    if not os.access(db_dir, os.W_OK):
        raise PermissionError(f"Database directory not writable: {db_dir}")
    if db_file.exists():
        if db_file.is_dir():
            raise ValueError(
                f"Expected file path for database, found directory: {db_file}"
            )
        if not os.access(db_file, os.W_OK):
            raise PermissionError(f"Database file is not writable: {db_file}")


def _attempt_recover_sqlite(db_path: str) -> str | None:
    if db_path == ":memory:":
        return None
    db_file = Path(db_path)
    if not db_file.exists() or not db_file.is_file():
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = db_file.with_suffix(f".corrupt.{timestamp}.db")
    try:
        db_file.rename(backup_path)
    except OSError:
        return None
    return str(backup_path)


def recover_sqlite_database() -> str | None:
    """
    Attempt to recover the configured SQLite database after a disk I/O error.

    Returns:
        Path to the backup file if recovery succeeded, otherwise None.
    """
    db_path = get_database_path()
    if db_path == ":memory:":
        return None
    backup_path = _attempt_recover_sqlite(db_path)
    if backup_path is None:
        return None
    configure_database(DATABASE_URL)
    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError:
        return None
    _ensure_team_last_active_column()
    return backup_path


# Note: init_db() is NOT called automatically during import to avoid circular dependencies
# It should be called explicitly when the application starts
