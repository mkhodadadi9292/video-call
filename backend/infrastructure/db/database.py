"""SQLAlchemy engine/session management.

The rest of the backend never imports this module directly — the composition
root (interfaces/container.py) owns a Database instance and hands sessions to
repositories. Tests build their own engines (see backend/tests/conftest.py).
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def configure_sqlite(engine) -> None:
    """Enable foreign keys + busy timeout on every SQLite connection."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def make_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    if url.startswith("sqlite"):
        configure_sqlite(engine)
    return engine


class Database:
    def __init__(self, url: str):
        self.engine = make_engine(url)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    @classmethod
    def from_engine(cls, engine) -> "Database":
        """Build a Database around a pre-configured engine (used by tests)."""
        database = cls.__new__(cls)
        database.engine = engine
        database.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        return database

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self):
        return self.session_factory()
