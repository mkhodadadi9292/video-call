# Phase 3 — Infrastructure: ORM, repositories, JWT, auth, config

**Status: ✅ complete** · TDD layer: **integration** · Tests: `backend/tests/integration/` (19 tests)

**Goal:** the adapters. SQLAlchemy persistence that implements the domain ports,
a PyJWT token generator, stub authentication, a DB-backed Jitsi config provider,
and idempotent seeding. Everything here is replaceable — the domain/application
layers only see the ports.

---

## 1. TDD cycle

### Step 1 — shared fixture

`backend/tests/conftest.py`:

```python
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
```

### Step 2 — write the failing tests

`backend/tests/integration/test_room_repository.py`:

```python
"""Integration tests: SqlAlchemyRoomRepository against real (in-memory) SQLite."""

import pytest

from backend.domain.entities import ChatMessage, JitsiRoomId, Room, RoomName
from backend.infrastructure.db.models import User
from backend.infrastructure.db.room_repository import SqlAlchemyRoomRepository


@pytest.fixture
def repo(db_session):
    return SqlAlchemyRoomRepository(db_session)


@pytest.fixture
def users(db_session):
    alice = User(username="alice", password_hash="x", role="user")
    bob = User(username="bob", password_hash="x", role="user")
    db_session.add_all([alice, bob])
    db_session.commit()
    return {"alice": alice.id, "bob": bob.id}


def _room(created_by: int, name: str = "standup") -> Room:
    return Room(id=None, name=RoomName(name), jitsi_room_id=JitsiRoomId.generate(), created_by=created_by)


class TestRooms:
    def test_create_assigns_id_and_timestamp(self, repo, users):
        created = repo.create_room(_room(users["alice"]))
        assert created.id is not None
        assert created.created_at is not None
        assert created.name.value == "standup"

    def test_list_active_rooms_newest_first_excludes_closed(self, repo, users):
        first = repo.create_room(_room(users["alice"], "first"))
        second = repo.create_room(_room(users["alice"], "second"))
        repo.close_room(first.id)

        rooms = repo.list_active_rooms()
        assert [r.name.value for r in rooms] == ["second"]

    def test_get_room_returns_none_when_missing(self, repo):
        assert repo.get_room(999) is None

    def test_close_room_returns_none_when_missing(self, repo):
        assert repo.close_room(999) is None

    def test_close_room_persists_inactive(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        closed = repo.close_room(room.id)
        assert closed.is_active is False
        assert repo.get_room(room.id).is_active is False


class TestParticipants:
    def test_join_leave_rejoin_cycle(self, repo, users):
        room = repo.create_room(_room(users["alice"]))

        repo.add_participant(room.id, users["bob"])
        assert repo.count_participants(room.id) == 1

        repo.remove_participant(room.id, users["bob"])
        assert repo.count_participants(room.id) == 0

        repo.add_participant(room.id, users["bob"])  # rejoin
        assert repo.count_participants(room.id) == 1

    def test_remove_is_idempotent(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        repo.remove_participant(room.id, users["bob"])  # never joined — no error

    def test_list_participants_includes_usernames(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        repo.add_participant(room.id, users["alice"])
        repo.add_participant(room.id, users["bob"])

        participants = repo.list_participants(room.id)
        assert [(p.user_id, p.username) for p in participants] == [
            (users["alice"], "alice"),
            (users["bob"], "bob"),
        ]
        assert all(p.is_connected for p in participants)

    def test_left_participant_is_listed_with_left_at(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        repo.add_participant(room.id, users["bob"])
        repo.remove_participant(room.id, users["bob"])

        participants = repo.list_participants(room.id)
        assert len(participants) == 1
        assert participants[0].left_at is not None


class TestMessages:
    def test_add_message_returns_username(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        msg = repo.add_message(room.id, users["bob"], "hello")
        assert msg.username == "bob"
        assert msg.text == "hello"
        assert msg.id is not None

    def test_add_message_rejects_blank_text(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        with pytest.raises(ValueError):
            repo.add_message(room.id, users["bob"], "   ")

    def test_list_messages_oldest_first_with_pagination(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        for i in range(5):
            repo.add_message(room.id, users["alice"], f"msg{i}")

        # Pages count from the newest message; each page is oldest-first.
        page1 = repo.list_messages(room.id, page=1, size=2)
        page3 = repo.list_messages(room.id, page=3, size=2)
        assert [m.text for m in page1] == ["msg3", "msg4"]
        assert [m.text for m in page3] == ["msg0"]
```

`backend/tests/integration/test_auth_infrastructure.py`:

```python
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
```

### Step 3 — run them (red)

```bash
uv run pytest backend/tests/integration -q
# ModuleNotFoundError: No module named 'backend.infrastructure'   ← expected
```

### Step 4 — implement

`backend/infrastructure/db/database.py`:

```python
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
```

`backend/infrastructure/db/models.py`:

```python
"""SQLAlchemy ORM models (infrastructure persistence — NOT domain entities).

Domain entities in backend/domain/entities.py are pure dataclasses; these
models only exist to persist them. Mapping happens in the repository.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    jitsi_room_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    creator = relationship("User")
    messages = relationship(
        "RoomMessage", back_populates="room",
        order_by="RoomMessage.created_at", cascade="all, delete-orphan",
    )


class RoomParticipant(Base):
    __tablename__ = "room_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    left_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RoomMessage(Base):
    __tablename__ = "room_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    room = relationship("Room", back_populates="messages")
    user = relationship("User")


class JitsiConfig(Base):
    __tablename__ = "jitsi_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[str] = mapped_column(String(100), nullable=False)
    app_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
```

`backend/infrastructure/db/room_repository.py`:

```python
"""SQLAlchemy implementation of the RoomRepository port (Phase 3).

The only place where ORM rows are mapped to domain entities and back.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.domain.entities import ChatMessage, JitsiRoomId, Participant, Room, RoomName
from backend.domain.ports.room_repository import RoomRepository
from backend.infrastructure.db.models import (
    Room as RoomModel,
    RoomMessage as RoomMessageModel,
    RoomParticipant as RoomParticipantModel,
    User,
)


def _room_to_domain(orm: RoomModel) -> Room:
    return Room(
        id=orm.id,
        name=RoomName(orm.name),
        jitsi_room_id=JitsiRoomId(orm.jitsi_room_id),
        created_by=orm.created_by,
        is_active=orm.is_active,
        created_at=orm.created_at,
    )


class SqlAlchemyRoomRepository(RoomRepository):
    def __init__(self, db: Session):
        self._db = db

    # -- rooms ------------------------------------------------------------

    def create_room(self, room: Room) -> Room:
        orm = RoomModel(
            name=room.name.value,
            jitsi_room_id=room.jitsi_room_id.value,
            created_by=room.created_by,
        )
        self._db.add(orm)
        self._db.commit()
        self._db.refresh(orm)
        return _room_to_domain(orm)

    def list_active_rooms(self) -> list[Room]:
        rows = (
            self._db.query(RoomModel)
            .filter(RoomModel.is_active.is_(True))
            .order_by(RoomModel.created_at.desc(), RoomModel.id.desc())
            .all()
        )
        return [_room_to_domain(r) for r in rows]

    def get_room(self, room_id: int) -> Room | None:
        orm = self._db.get(RoomModel, room_id)
        return _room_to_domain(orm) if orm else None

    def close_room(self, room_id: int) -> Room | None:
        orm = self._db.get(RoomModel, room_id)
        if not orm:
            return None
        orm.is_active = False
        self._db.commit()
        self._db.refresh(orm)
        return _room_to_domain(orm)

    # -- participants -----------------------------------------------------

    def add_participant(self, room_id: int, user_id: int) -> None:
        existing = (
            self._db.query(RoomParticipantModel)
            .filter(
                RoomParticipantModel.room_id == room_id,
                RoomParticipantModel.user_id == user_id,
            )
            .first()
        )
        if existing:
            existing.left_at = None  # rejoin
        else:
            self._db.add(RoomParticipantModel(room_id=room_id, user_id=user_id))
        self._db.commit()

    def remove_participant(self, room_id: int, user_id: int) -> None:
        row = (
            self._db.query(RoomParticipantModel)
            .filter(
                RoomParticipantModel.room_id == room_id,
                RoomParticipantModel.user_id == user_id,
                RoomParticipantModel.left_at.is_(None),
            )
            .first()
        )
        if row:
            row.left_at = datetime.now(timezone.utc)
            self._db.commit()

    def list_participants(self, room_id: int) -> list[Participant]:
        rows = (
            self._db.query(RoomParticipantModel, User.username)
            .join(User, RoomParticipantModel.user_id == User.id)
            .filter(RoomParticipantModel.room_id == room_id)
            .order_by(RoomParticipantModel.joined_at.asc(), RoomParticipantModel.id.asc())
            .all()
        )
        return [
            Participant(
                user_id=p.user_id,
                username=username,
                joined_at=p.joined_at,
                left_at=p.left_at,
            )
            for p, username in rows
        ]

    def count_participants(self, room_id: int) -> int:
        return (
            self._db.query(RoomParticipantModel)
            .filter(
                RoomParticipantModel.room_id == room_id,
                RoomParticipantModel.left_at.is_(None),
            )
            .count()
        )

    # -- messages ---------------------------------------------------------

    def add_message(self, room_id: int, user_id: int, text: str) -> ChatMessage:
        # Reuse the domain value object for validation (single source of truth).
        message = ChatMessage(id=None, room_id=room_id, user_id=user_id, username="", text=text)
        orm = RoomMessageModel(room_id=room_id, user_id=user_id, message=message.text)
        self._db.add(orm)
        self._db.commit()
        self._db.refresh(orm)
        return ChatMessage(
            id=orm.id,
            room_id=orm.room_id,
            user_id=orm.user_id,
            username=orm.user.username,
            text=orm.message,
            created_at=orm.created_at,
        )

    def list_messages(self, room_id: int, page: int, size: int) -> list[ChatMessage]:
        base_q = self._db.query(RoomMessageModel).filter(RoomMessageModel.room_id == room_id)
        offset = (page - 1) * size
        rows = (
            base_q.order_by(RoomMessageModel.created_at.desc(), RoomMessageModel.id.desc())
            .offset(offset)
            .limit(size)
            .all()
        )
        return [
            ChatMessage(
                id=m.id,
                room_id=m.room_id,
                user_id=m.user_id,
                username=m.user.username,
                text=m.message,
                created_at=m.created_at,
            )
            for m in reversed(rows)  # oldest first for display
        ]
```

`backend/infrastructure/db/user_repository.py`:

```python
"""SQLAlchemy implementation of the UserRepository port."""

from sqlalchemy.orm import Session

from backend.domain.entities import UserAccount
from backend.domain.ports.user_repository import UserRepository
from backend.infrastructure.db.models import User


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, db: Session):
        self._db = db

    @staticmethod
    def _to_domain(user: User) -> UserAccount:
        return UserAccount(
            id=user.id, username=user.username, role=user.role, password_hash=user.password_hash
        )

    def get_by_username(self, username: str) -> UserAccount | None:
        user = self._db.query(User).filter(User.username == username).first()
        return self._to_domain(user) if user else None

    def create(self, username: str, password_hash: str, role: str) -> UserAccount:
        user = User(username=username, password_hash=password_hash, role=role)
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return self._to_domain(user)
```

`backend/infrastructure/auth/passwords.py`:

```python
"""PBKDF2-HMAC-SHA256 password hashing (implements the PasswordHasher port)."""

import hashlib
import secrets

from backend.domain.ports.password_hasher import PasswordHasher

_ITERATIONS = 100_000


class Pbkdf2PasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()
        return f"{salt}${digest}"

    def verify(self, password: str, hashed: str) -> bool:
        try:
            salt, expected = hashed.split("$", 1)
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()
        return secrets.compare_digest(digest, expected)


hash_password = Pbkdf2PasswordHasher().hash
verify_password = Pbkdf2PasswordHasher().verify
```

`backend/infrastructure/auth/stub_authenticator.py`:

```python
"""Stub bearer-token authentication.

Token format: `stub-token-for-{username}`. Real JWT auth for the app's own
users is a documented TODO (the Jitsi meeting tokens ARE real JWTs — this
stub only covers our API).
"""

from backend.domain.entities import UserAccount
from backend.domain.ports.user_repository import UserRepository

TOKEN_PREFIX = "stub-token-for-"


class StubAuthenticator:
    def __init__(self, users: UserRepository):
        self._users = users

    def authenticate(self, authorization: str | None) -> UserAccount | None:
        """Resolve a UserAccount from an Authorization header, or None if invalid."""
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization.removeprefix("Bearer ").strip()
        if not token.startswith(TOKEN_PREFIX):
            return None
        username = token.removeprefix(TOKEN_PREFIX)
        if not username:
            return None
        return self._users.get_by_username(username)
```

`backend/infrastructure/auth/jwt_token_generator.py`:

```python
"""PyJWT implementation of the RoomTokenGenerator port.

Produces the JWT that self-hosted Jitsi (prosody token_verification module)
validates at join time:
  aud=jitsi, iss=<app_id>, sub=meet.jitsi, room=<jitsi_room_id>,
  context.user.name=<username>, exp/iat.
"""

from datetime import datetime, timedelta, timezone

import jwt

from backend.domain.entities import JitsiConfig, Room
from backend.domain.ports.token_generator import RoomTokenGenerator


class JwtRoomTokenGenerator(RoomTokenGenerator):
    def __init__(self, expire_minutes: int):
        self._expire_minutes = expire_minutes

    def generate(self, room: Room, username: str, config: JitsiConfig) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "aud": "jitsi",
            "iss": config.app_id,
            "sub": "meet.jitsi",
            "room": room.jitsi_room_id.value,
            "exp": now + timedelta(minutes=self._expire_minutes),
            "iat": now,
            "context": {"user": {"name": username}},
        }
        return jwt.encode(payload, config.app_secret, algorithm="HS256")
```

`backend/infrastructure/config/db_jitsi_config.py`:

```python
"""DB-backed JitsiConfigProvider with env-var override.

Precedence: JITSI_JWT_SECRET env var (used in Docker so backend and prosody
share one secret) → seeded jitsi_config DB row.
"""

from backend.domain.entities import JitsiConfig
from backend.domain.ports.jitsi_config_provider import JitsiConfigProvider
from backend.infrastructure.db.models import JitsiConfig as JitsiConfigModel


class DbJitsiConfigProvider(JitsiConfigProvider):
    def __init__(self, db_session_factory, env_app_id: str | None, env_secret: str | None):
        self._db_session_factory = db_session_factory
        self._env_app_id = env_app_id
        self._env_secret = env_secret

    def get(self) -> JitsiConfig | None:
        if self._env_secret:
            return JitsiConfig(
                app_id=self._env_app_id or "video-call-system",
                app_secret=self._env_secret,
            )
        with self._db_session_factory() as session:
            row = session.query(JitsiConfigModel).first()
            if not row:
                return None
            return JitsiConfig(app_id=row.app_id, app_secret=row.app_secret)
```

`backend/infrastructure/db/seed.py`:

```python
"""Startup seeding: tables, admin user, Jitsi credentials. Idempotent."""

import secrets

from backend.config import Settings
from backend.infrastructure.auth.passwords import hash_password
from backend.infrastructure.db.database import Database
from backend.infrastructure.db.models import JitsiConfig, User

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "12345@mn"


def seed_database(database: Database, settings: Settings) -> None:
    database.create_all()
    with database.session() as session:
        if not session.query(User).filter(User.username == ADMIN_USERNAME).first():
            session.add(
                User(
                    username=ADMIN_USERNAME,
                    password_hash=hash_password(ADMIN_PASSWORD),
                    role="admin",
                )
            )
        if not session.query(JitsiConfig).first():
            session.add(
                JitsiConfig(
                    app_id=settings.jitsi_jwt_app_id,
                    app_secret=settings.jitsi_jwt_secret or secrets.token_urlsafe(32),
                )
            )
        session.commit()
```

`backend/config.py`:

```python
"""Environment-driven settings (outermost configuration concern)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    jitsi_jwt_app_id: str
    jitsi_jwt_secret: str | None
    jitsi_jwt_expire_minutes: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get("DATABASE_URL", "sqlite:///./video_call.db"),
            jitsi_jwt_app_id=os.environ.get("JITSI_JWT_APP_ID", "video-call-system"),
            jitsi_jwt_secret=os.environ.get("JITSI_JWT_SECRET") or None,
            jitsi_jwt_expire_minutes=int(os.environ.get("JITSI_JWT_EXPIRE_MINUTES", "1440")),
        )
```

### Step 5 — run them (green)

```bash
uv run pytest backend/tests/integration -q
# 19 passed
```

---

## 2. Design notes

- **ORM models ≠ domain entities.** The mapping lives only in the repositories;
  domain objects stay framework-free (the domain layer doesn't even import SQLAlchemy).
- **Foreign keys + busy timeout** are enabled per SQLite connection via an event
  listener — same pragmas MediaService uses (WAL is a deployment concern; in-memory
  tests don't need it).
- **Rejoin semantics** (`add_participant` resets `left_at`) come straight from
  MediaService's `RoomRepository.join()` — a participant row is a presence log,
  not a one-shot record.
- **Validation at the adapter boundary:** `add_message` constructs a domain
  `ChatMessage` first, so the same `ValueError` rules protect the DB as protect
  the use cases (single source of truth).
- **Env secret > DB secret:** in Docker, `JITSI_JWT_SECRET` must equal prosody's
  `JWT_APP_SECRET`, so env always wins; the DB row is the standalone fallback
  (auto-generated on first start).
- **PyJWT audience:** tests decode with `audience="jitsi"` because modern PyJWT
  (≥2.10) rejects tokens carrying `aud` when no audience is supplied.

## 3. Verification

```bash
cd /home/mohammad/Desktop/my-projects/video-call-system
uv run pytest backend/tests/integration -v
```
