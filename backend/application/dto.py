"""DTOs crossing the application boundary.

Use cases return DTOs (never domain entities) so the interfaces layer never
leaks ORM/domain objects into HTTP responses and vice versa.
"""

from dataclasses import dataclass
from datetime import datetime

from backend.domain.entities import ChatMessage, Participant, Room


@dataclass(frozen=True)
class RoomDTO:
    id: int
    name: str
    jitsi_room_id: str
    created_by: int
    is_active: bool
    created_at: datetime | None
    participant_count: int = 0

    @classmethod
    def from_domain(cls, room: Room, participant_count: int = 0) -> "RoomDTO":
        return cls(
            id=room.id,
            name=room.name.value,
            jitsi_room_id=room.jitsi_room_id.value,
            created_by=room.created_by,
            is_active=room.is_active,
            created_at=room.created_at,
            participant_count=participant_count,
        )


@dataclass(frozen=True)
class ParticipantDTO:
    user_id: int
    username: str
    joined_at: datetime | None
    left_at: datetime | None

    @classmethod
    def from_domain(cls, p: Participant) -> "ParticipantDTO":
        return cls(user_id=p.user_id, username=p.username, joined_at=p.joined_at, left_at=p.left_at)


@dataclass(frozen=True)
class RoomDetailDTO:
    id: int
    name: str
    jitsi_room_id: str
    created_by: int
    is_active: bool
    created_at: datetime | None
    participants: list[ParticipantDTO]


@dataclass(frozen=True)
class MessageDTO:
    id: int
    room_id: int
    user_id: int
    username: str
    text: str
    created_at: datetime | None

    @classmethod
    def from_domain(cls, m: ChatMessage) -> "MessageDTO":
        return cls(
            id=m.id, room_id=m.room_id, user_id=m.user_id,
            username=m.username, text=m.text, created_at=m.created_at,
        )


@dataclass(frozen=True)
class JoinTokenDTO:
    token: str


@dataclass(frozen=True)
class LoginDTO:
    access_token: str
    username: str
    role: str
