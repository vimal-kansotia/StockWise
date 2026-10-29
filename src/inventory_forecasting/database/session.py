"""Database connection and session factory management."""

import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from inventory_forecasting.config import settings
from inventory_forecasting.database.models import Base

logger = logging.getLogger(__name__)


def create_db_engine():
    """Builds database engine, with resilient fallback to SQLite for local development."""
    db_url = settings.database_url
    try:
        if db_url.startswith("sqlite"):
            engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
        # Test connection
        with engine.connect() as conn:
            pass
        return engine
    except Exception as e:
        logger.warning(
            f"Could not connect to configured database at '{db_url}': {e}. "
            "Falling back to local SQLite database."
        )
        sqlite_fallback = f"sqlite:///{settings.sqlite_db_path}"
        engine = create_engine(
            sqlite_fallback,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        return engine


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine=None):
    """Initializes tables idempotently using SQLAlchemy metadata."""
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)


def get_db() -> Generator[Session, None, None]:
    """FastAPI and context dependency providing transactional DB sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
