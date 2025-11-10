"""
Database configuration and session management.

This module handles database initialization, connection pooling,
and session management for SQLAlchemy ORM operations.
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path
from db_models import Base

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent / "manga.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db() -> None:
    """
    Initialize the database by creating all tables.
    
    This function creates all tables defined in the SQLAlchemy models.
    It's safe to call multiple times as it uses CREATE TABLE IF NOT EXISTS.
    """
    logger.info("Initializing database at %s", DB_PATH)
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")

def get_db_session() -> Session:
    """
    Get a new database session.
    
    Returns:
        Session: SQLAlchemy session for database operations
    """
    return SessionLocal()

def close_db_session(session: Session) -> None:
    """
    Close a database session.
    
    Args:
        session (Session): Session to close
    """
    if session:
        session.close()