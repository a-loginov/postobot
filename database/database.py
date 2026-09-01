import logging
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

import config
from database.models import Base

logger = logging.getLogger(__name__)


def _ensure_local_db_dir(url: str) -> None:
    """Create the local_db directory automatically if it does not exist."""
    prefix = "sqlite:///"
    if url.startswith(prefix):
        db_path = Path(url[len(prefix):])
        db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_local_db_dir(config.DATABASE_URL)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """Enable foreign keys for SQLite so relationships behave correctly."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = create_engine(config.DATABASE_URL, echo=False, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("Database connected: %s", config.DATABASE_URL)


def drop_db() -> None:
    """Drop all tables. Used in tests and for cleaning the test database."""
    Base.metadata.drop_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()
