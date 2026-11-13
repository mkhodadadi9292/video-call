"""E2E fixtures: full FastAPI app + TestClient on an in-memory SQLite DB."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from backend.config import Settings
from backend.infrastructure.db.database import Database, configure_sqlite
from backend.main import create_app


@pytest.fixture
def app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    configure_sqlite(engine)
    database = Database.from_engine(engine)
    settings = Settings(
        database_url="sqlite://",
        jitsi_jwt_app_id="video-call-system",
        jitsi_jwt_secret="test-secret",
        jitsi_jwt_expire_minutes=1440,
    )
    return create_app(database, settings)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(client):
    response = client.post("/api/auth/login", json={"username": "alice", "password": "pw"})
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return client
