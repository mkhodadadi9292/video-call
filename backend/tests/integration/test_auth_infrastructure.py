"""Integration tests: JWT generator, Jitsi config provider, stub auth, passwords."""

from datetime import datetime, timezone

import jwt
import pytest

from backend.domain.entities import JitsiConfig, JitsiRoomId, Room, RoomName
from backend.infrastructure.auth.jwt_token_generator import JwtRoomTokenGenerator
from backend.infrastructure.auth.passwords import hash_password, verify_password
from backend.infrastructure.auth.stub_authenticator import StubAuthenticator
from backend.infrastructure.config.db_jitsi_config import DbJitsiConfigProvider
from backend.infrastructure.db.models import JitsiConfig as JitsiConfigModel
from backend.infrastructure.db.models import User
from backend.infrastructure.db.user_repository import SqlAlchemyUserRepository


def _room() -> Room:
    return Room(
        id=7, name=RoomName("demo"), jitsi_room_id=JitsiRoomId("abc123"), created_by=1
    )


class TestJwtRoomTokenGenerator:
    def test_generates_decodable_token_with_expected_claims(self):
        config = JitsiConfig(app_id="video-call-system", app_secret="s3cret")
        generator = JwtRoomTokenGenerator(expire_minutes=1440)

        token = generator.generate(_room(), "alice", config)
        decoded = jwt.decode(token, "s3cret", algorithms=["HS256"], audience="jitsi")

        assert decoded["iss"] == "video-call-system"
        assert decoded["sub"] == "meet.jitsi"
        assert decoded["room"] == "abc123"
        assert decoded["context"]["user"]["name"] == "alice"
        assert decoded["exp"] > datetime.now(timezone.utc).timestamp()

    def test_expiry_respects_configured_minutes(self):
        config = JitsiConfig(app_id="vcs", app_secret="s3cret")
        token = JwtRoomTokenGenerator(expire_minutes=5).generate(_room(), "bob", config)
        decoded = jwt.decode(token, "s3cret", algorithms=["HS256"], audience="jitsi")
        import math
        lifetime = decoded["exp"] - decoded["iat"]
        assert math.isclose(lifetime, 300, abs_tol=5)


class TestPasswords:
    def test_hash_and_verify_roundtrip(self):
        hashed = hash_password("hunter2")
        assert hashed != "hunter2"
        assert verify_password("hunter2", hashed) is True

    def test_verify_rejects_wrong_password(self):
        hashed = hash_password("hunter2")
        assert verify_password("wrong", hashed) is False


class TestDbJitsiConfigProvider:
    def test_env_secret_overrides_db(self, db_session):
        db_session.add(JitsiConfigModel(app_id="db-app", app_secret="db-secret"))
        db_session.commit()
        provider = DbJitsiConfigProvider(
            db_session_factory=lambda: db_session,
            env_app_id="video-call-system",
            env_secret="env-secret",
        )
        config = provider.get()
        assert config.app_id == "video-call-system"
        assert config.app_secret == "env-secret"

    def test_falls_back_to_db_row(self, db_session):
        db_session.add(JitsiConfigModel(app_id="db-app", app_secret="db-secret"))
        db_session.commit()
        provider = DbJitsiConfigProvider(
            db_session_factory=lambda: db_session, env_app_id=None, env_secret=None
        )
        config = provider.get()
        assert config.app_id == "db-app"
        assert config.app_secret == "db-secret"

    def test_returns_none_when_unconfigured(self, db_session):
        provider = DbJitsiConfigProvider(
            db_session_factory=lambda: db_session, env_app_id=None, env_secret=None
        )
        assert provider.get() is None


class TestStubAuthenticator:
    def test_resolves_user_from_stub_token(self, db_session):
        db_session.add(User(username="alice", password_hash="x", role="user"))
        db_session.commit()
        authenticator = StubAuthenticator(SqlAlchemyUserRepository(db_session))

        user = authenticator.authenticate("Bearer stub-token-for-alice")
        assert user is not None
        assert user.username == "alice"

    def test_returns_none_for_unknown_user(self, db_session):
        authenticator = StubAuthenticator(SqlAlchemyUserRepository(db_session))
        assert authenticator.authenticate("Bearer stub-token-for-ghost") is None

    def test_returns_none_for_malformed_tokens(self, db_session):
        authenticator = StubAuthenticator(SqlAlchemyUserRepository(db_session))
        assert authenticator.authenticate("Bearer wrong-format") is None
        assert authenticator.authenticate("NotBearer stub-token-for-alice") is None
        assert authenticator.authenticate(None) is None


class TestUserRepository:
    def test_create_and_get_by_username(self, db_session):
        repo = SqlAlchemyUserRepository(db_session)
        account = repo.create("alice", hash_password("pw"), role="user")
        assert account.username == "alice"
        assert account.role == "user"
        fetched = repo.get_by_username("alice")
        assert fetched.username == "alice"
        assert repo.get_by_username("ghost") is None
