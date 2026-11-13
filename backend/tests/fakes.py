"""Test doubles implementing the domain ports — used by unit tests.

Fakes live in the test package so production code never imports test code.
"""

from dataclasses import replace
from datetime import datetime, timezone

from backend.domain.entities import ChatMessage, JitsiConfig, Participant, Room, UserAccount
from backend.domain.ports.jitsi_config_provider import JitsiConfigProvider
from backend.domain.ports.password_hasher import PasswordHasher
from backend.domain.ports.room_repository import RoomRepository
from backend.domain.ports.token_generator import RoomTokenGenerator
from backend.domain.ports.user_repository import UserRepository


class InMemoryRoomRepository(RoomRepository):
    def __init__(self):
        self._rooms: dict[int, Room] = {}
        self._participants: dict[int, list[Participant]] = {}
        self._messages: dict[int, list[ChatMessage]] = {}
        self._usernames: dict[int, str] = {}
        self._next_room_id = 1
        self._next_message_id = 1
        self._now = datetime.now(timezone.utc)

    def add_user(self, user_id: int, username: str) -> None:
        self._usernames[user_id] = username

    # -- rooms ------------------------------------------------------------

    def create_room(self, room: Room) -> Room:
        stored = replace(room, id=self._next_room_id, created_at=self._now)
        self._next_room_id += 1
        self._rooms[stored.id] = stored
        return stored

    def list_active_rooms(self) -> list[Room]:
        return [r for r in self._rooms.values() if r.is_active]

    def get_room(self, room_id: int) -> Room | None:
        return self._rooms.get(room_id)

    def close_room(self, room_id: int) -> Room | None:
        room = self._rooms.get(room_id)
        if not room:
            return None
        closed = room.close()
        self._rooms[room_id] = closed
        return closed

    # -- participants -----------------------------------------------------

    def add_participant(self, room_id: int, user_id: int) -> None:
        records = self._participants.setdefault(room_id, [])
        username = self._usernames.get(user_id, f"user-{user_id}")
        for p in records:
            if p.user_id == user_id and p.left_at is not None:
                records[records.index(p)] = replace(p, left_at=None)
                return
        records.append(Participant(user_id=user_id, username=username, joined_at=self._now))

    def remove_participant(self, room_id: int, user_id: int) -> None:
        records = self._participants.get(room_id, [])
        for i, p in enumerate(records):
            if p.user_id == user_id and p.left_at is None:
                records[i] = replace(p, left_at=self._now)

    def list_participants(self, room_id: int) -> list[Participant]:
        return list(self._participants.get(room_id, []))

    def count_participants(self, room_id: int) -> int:
        return sum(1 for p in self._participants.get(room_id, []) if p.is_connected)

    # -- messages ---------------------------------------------------------

    def add_message(self, room_id: int, user_id: int, text: str) -> ChatMessage:
        username = self._usernames.get(user_id, f"user-{user_id}")
        msg = ChatMessage(
            id=self._next_message_id,
            room_id=room_id,
            user_id=user_id,
            username=username,
            text=text,
            created_at=self._now,
        )
        self._next_message_id += 1
        self._messages.setdefault(room_id, []).append(msg)
        return msg

    def list_messages(self, room_id: int, page: int, size: int) -> list[ChatMessage]:
        messages = self._messages.get(room_id, [])
        total = len(messages)
        # Same convention as the SQLAlchemy repository: pages count from the
        # newest message; each page is returned oldest-first.
        start = max(0, total - page * size)
        end = total - (page - 1) * size
        return messages[start:end]


class FakeTokenGenerator(RoomTokenGenerator):
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def generate(self, room: Room, username: str, config: JitsiConfig) -> str:
        self.calls.append((room.jitsi_room_id.value, username))
        return f"fake-jwt.{config.app_id}.{room.jitsi_room_id.value}.{username}"


class StaticJitsiConfigProvider(JitsiConfigProvider):
    def __init__(self, config: JitsiConfig | None):
        self._config = config

    def get(self) -> JitsiConfig | None:
        return self._config


class FakeUserRepository(UserRepository):
    def __init__(self):
        self._users: dict[str, UserAccount] = {}
        self._next_id = 1

    def seed(self, username: str, password_hash: str, role: str = "user") -> None:
        self._users[username] = UserAccount(
            id=self._next_id, username=username, role=role, password_hash=password_hash
        )
        self._next_id += 1

    def get_by_username(self, username: str) -> UserAccount | None:
        return self._users.get(username)

    def create(self, username: str, password_hash: str, role: str) -> UserAccount:
        account = UserAccount(id=self._next_id, username=username, role=role, password_hash=password_hash)
        self._next_id += 1
        self._users[username] = account
        return account


class FakePasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed:{password}"
