"""
Common database components shared across all modules
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Create database directory if it doesn't exist
os.makedirs("data", exist_ok=True)

# SQLite database setup
DATABASE_URL = "sqlite:///data/CyberneticAgents.db"
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


# Note: init_db() is NOT called automatically during import to avoid circular dependencies
# It should be called explicitly when the application starts
