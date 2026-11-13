"""Shared pytest fixtures.

Every test (unit/integration/e2e) runs against a fresh in-memory SQLite
database — the real `video_call.db` is never touched by tests.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.infrastructure.db import models  # noqa: F401 — registers tables on Base
from backend.infrastructure.db.database import Base, configure_sqlite


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    configure_sqlite(engine)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    yield session
    session.close()
    engine.dispose()
