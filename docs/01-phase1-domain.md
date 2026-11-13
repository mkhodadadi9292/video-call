# Phase 1 — Domain layer: entities, value objects, ports

**Status: ✅ complete** · TDD layer: **unit** · Tests: `backend/tests/unit/test_entities.py` (15 tests)

**Goal:** the innermost layer — pure Python domain model with validation, plus the
abstract ports the rest of the system will talk to. No frameworks allowed in this layer.

---

## 1. TDD cycle

### Step 1 — write the failing test

`backend/tests/unit/test_entities.py`:

```python
"""Unit tests for domain entities and value objects (Phase 1)."""

import pytest

from backend.domain.entities import (
    ChatMessage,
    JitsiConfig,
    JitsiRoomId,
    Participant,
    Room,
    RoomName,
)


class TestRoomName:
    def test_strips_surrounding_whitespace(self):
        assert RoomName("  standup  ").value == "standup"

    def test_accepts_min_length_after_strip(self):
        assert RoomName("a").value == "a"

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            RoomName("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValueError):
            RoomName("   ")

    def test_rejects_longer_than_200(self):
        with pytest.raises(ValueError):
            RoomName("x" * 201)

    def test_accepts_exactly_200(self):
        assert RoomName("x" * 200).value == "x" * 200


class TestJitsiRoomId:
    def test_generate_returns_urlsafe_value(self):
        jitsi_id = JitsiRoomId.generate()
        assert len(jitsi_id.value) >= 16
        assert "/" not in jitsi_id.value
        assert "+" not in jitsi_id.value

    def test_generate_produces_distinct_ids(self):
        ids = {JitsiRoomId.generate().value for _ in range(50)}
        assert len(ids) == 50


class TestRoom:
    def test_new_room_is_active_by_default(self):
        room = Room(id=None, name=RoomName("demo"), jitsi_room_id=JitsiRoomId("abc123"), created_by=1)
        assert room.is_active is True

    def test_close_returns_inactive_copy(self):
        room = Room(id=1, name=RoomName("demo"), jitsi_room_id=JitsiRoomId("abc123"), created_by=1)
        closed = room.close()
        assert closed.is_active is False
        assert room.is_active is True  # original untouched (immutability)


class TestChatMessage:
    def test_strips_text(self):
        msg = ChatMessage(id=None, room_id=1, user_id=2, username="bob", text="  hi  ")
        assert msg.text == "hi"

    def test_rejects_empty_text(self):
        with pytest.raises(ValueError):
            ChatMessage(id=None, room_id=1, user_id=2, username="bob", text="")


class TestParticipant:
    def test_connected_while_left_at_is_none(self):
        assert Participant(user_id=1, username="bob").is_connected is True

    def test_not_connected_after_leaving(self):
        from datetime import datetime, timezone
        p = Participant(user_id=1, username="bob", left_at=datetime.now(timezone.utc))
        assert p.is_connected is False


class TestJitsiConfig:
    def test_holds_app_credentials(self):
        cfg = JitsiConfig(app_id="video-call-system", app_secret="s3cret")
        assert cfg.app_id == "video-call-system"
        assert cfg.app_secret == "s3cret"
```

### Step 2 — run it (red)

```bash
uv run pytest backend/tests/unit/test_entities.py -q
# ModuleNotFoundError: No module named 'backend.domain'   ← expected
```

### Step 3 — implement

`backend/domain/entities.py`:

```python
"""Domain entities and value objects.

Pure Python — no framework imports. This is the innermost layer of the
lite-DDD architecture; nothing here may depend on SQLAlchemy, FastAPI, or HTTP.
"""

from dataclasses import dataclass, replace
from datetime import datetime
import secrets


@dataclass(frozen=True)
class RoomName:
    """Value object: a room's display name, validated on construction."""

    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.strip()
        if not (1 <= len(cleaned) <= 200):
            raise ValueError("Room name must be 1-200 characters")
        object.__setattr__(self, "value", cleaned)


@dataclass(frozen=True)
class JitsiRoomId:
    """Value object: the room identifier used inside the Jitsi XMPP domain."""

    value: str

    @classmethod
    def generate(cls) -> "JitsiRoomId":
        return cls(secrets.token_urlsafe(12))


@dataclass(frozen=True)
class Room:
    """Aggregate root of the room lifecycle."""

    id: int | None
    name: RoomName
    jitsi_room_id: JitsiRoomId
    created_by: int
    is_active: bool = True
    created_at: datetime | None = None

    def close(self) -> "Room":
        """End the room — returns a new inactive snapshot (immutability)."""
        return replace(self, is_active=False)


@dataclass(frozen=True)
class Participant:
    """A user's presence record in a room."""

    user_id: int
    username: str
    joined_at: datetime | None = None
    left_at: datetime | None = None

    @property
    def is_connected(self) -> bool:
        return self.left_at is None


@dataclass(frozen=True)
class ChatMessage:
    """A text message posted to a room's chat."""

    id: int | None
    room_id: int
    user_id: int
    username: str
    text: str
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        cleaned = self.text.strip()
        if not cleaned:
            raise ValueError("Message text must not be empty")
        object.__setattr__(self, "text", cleaned)


@dataclass(frozen=True)
class JitsiConfig:
    """Shared Jitsi JWT credentials (app id + HS256 secret)."""

    app_id: str
    app_secret: str


@dataclass(frozen=True)
class UserAccount:
    """A user of the system (domain view — persistence details live in infra)."""

    id: int | None
    username: str
    role: str
    password_hash: str
```

### Step 4 — the ports

`backend/domain/ports/room_repository.py`:

```python
"""Driven port: persistence for rooms, participants, and chat messages.

The application layer depends on this abstraction; infrastructure provides
the SQLAlchemy implementation (dependency inversion — D in SOLID).
"""

from abc import ABC, abstractmethod

from backend.domain.entities import ChatMessage, Participant, Room


class RoomRepository(ABC):
    @abstractmethod
    def create_room(self, room: Room) -> Room:
        """Persist a new room and return it with id/created_at assigned."""

    @abstractmethod
    def list_active_rooms(self) -> list[Room]:
        """All active rooms, newest first."""

    @abstractmethod
    def get_room(self, room_id: int) -> Room | None:
        """Fetch one room by id, or None."""

    @abstractmethod
    def close_room(self, room_id: int) -> Room | None:
        """Mark a room inactive. Returns the updated room, or None if missing."""

    @abstractmethod
    def add_participant(self, room_id: int, user_id: int) -> None:
        """Record that a user joined (re-join resets left_at)."""

    @abstractmethod
    def remove_participant(self, room_id: int, user_id: int) -> None:
        """Record that a user left. Idempotent."""

    @abstractmethod
    def list_participants(self, room_id: int) -> list[Participant]:
        """All participant records for a room, joined first."""

    @abstractmethod
    def count_participants(self, room_id: int) -> int:
        """Number of currently connected participants."""

    @abstractmethod
    def add_message(self, room_id: int, user_id: int, text: str) -> ChatMessage:
        """Persist a chat message and return it with id/username/created_at."""

    @abstractmethod
    def list_messages(self, room_id: int, page: int, size: int) -> list[ChatMessage]:
        """Messages for a room, oldest first, paginated."""
```

`backend/domain/ports/token_generator.py`:

```python
"""Driven port: Jitsi join-token signing (JWT)."""

from abc import ABC, abstractmethod

from backend.domain.entities import JitsiConfig, Room


class RoomTokenGenerator(ABC):
    @abstractmethod
    def generate(self, room: Room, username: str, config: JitsiConfig) -> str:
        """Sign a JWT (using `config`) authorizing `username` to join `room`'s Jitsi room."""
```

`backend/domain/ports/jitsi_config_provider.py`:

```python
"""Driven port: access to Jitsi JWT configuration (app id + secret)."""

from abc import ABC, abstractmethod

from backend.domain.entities import JitsiConfig


class JitsiConfigProvider(ABC):
    @abstractmethod
    def get(self) -> JitsiConfig | None:
        """Return the active Jitsi credentials, or None if not configured."""
```

`backend/domain/ports/user_repository.py`:

```python
"""Driven port: user account persistence."""

from abc import ABC, abstractmethod

from backend.domain.entities import UserAccount


class UserRepository(ABC):
    @abstractmethod
    def get_by_username(self, username: str) -> UserAccount | None:
        """Fetch a user account by username, or None."""

    @abstractmethod
    def create(self, username: str, password_hash: str, role: str) -> UserAccount:
        """Persist a new user account."""
```

`backend/domain/ports/password_hasher.py`:

```python
"""Driven port: password hashing/verification."""

from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str:
        """Hash a plaintext password for storage."""

    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool:
        """Check a plaintext password against a stored hash."""
```

### Step 5 — run it (green)

```bash
uv run pytest backend/tests/unit/test_entities.py -q
# 15 passed
```

---

## 2. Design notes

- **Value objects validate themselves.** `RoomName` and `ChatMessage` raise
  `ValueError` at construction — invalid state cannot exist anywhere in the
  system, including at the repository level (Phase 3 reuses them for validation).
- **Immutability via frozen dataclasses.** `Room.close()` returns a *new* inactive
  snapshot instead of mutating — the original remains untouched (tested).
- **`JitsiRoomId.generate()`** uses `secrets.token_urlsafe(12)` — the same
  collision-resistant approach as MediaService's `_generate_jitsi_id()`.
- **Five small ports** (interface segregation): a use case takes only what it needs.
- **`UserAccount`** exists so the domain can talk about users without knowing
  the `users` table.

## 3. Verification

```bash
cd /home/mohammad/Desktop/my-projects/video-call-system
uv run pytest backend/tests/unit/test_entities.py -v
```
