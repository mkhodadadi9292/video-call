"""Domain entities and value objects.

Pure Python — no framework imports. This is the innermost layer of the
lite-DDD architecture; nothing here may depend on SQLAlchemy, FastAPI, or HTTP.
"""

from dataclasses import dataclass, field, replace
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
