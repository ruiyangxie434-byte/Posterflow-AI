"""SQLAlchemy setup and transaction helpers.

The default database lives beside this module so the application keeps its data
when Streamlit restarts.  Tests and deployments can override the location with
``POSTERFLOW_DATABASE_URL``.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker


DATABASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_URL = f"sqlite:///{(DATABASE_DIR / 'posterflow.db').as_posix()}"
DATABASE_URL = os.getenv("POSTERFLOW_DATABASE_URL", DEFAULT_DATABASE_URL)

engine_kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
Base = declarative_base()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """Enable SQLite foreign-key constraints for every new connection."""

    module_name = dbapi_connection.__class__.__module__
    if not module_name.startswith("sqlite3"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    """Create all tables that do not exist yet."""

    # Importing registers the model metadata on Base.
    from . import models  # noqa: F401

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """Provide a transactional session for ``with get_session()`` callers.

    Successful blocks are committed.  Exceptions trigger a rollback and are
    re-raised so a page can display an appropriate message.
    """

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
