# Phase 2 — Application layer: use cases, DTOs, errors, fakes

**Status: ✅ complete** · TDD layer: **unit** · Tests: `backend/tests/unit/test_use_cases.py` + `test_auth_use_case.py` (41 tests total in unit layer)

**Goal:** the orchestration layer. Every use case is one class with one public
`execute()` method (SRP), depends only on domain ports (DIP), and returns DTOs —
never domain entities, never ORM objects.

---

## 1. TDD cycle

### Step 1 — fakes (test doubles implementing the ports)

Because use cases depend on *ports*, not on SQLAlchemy, unit tests run against
in-memory fakes. This is Liskov substitution in action: the use case cannot tell
the difference between `InMemoryRoomRepository` and `SqlAlchemyRoomRepository`.

`backend/tests/fakes.py`:

```python
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
```

### Step 2 — write the failing tests

`backend/tests/unit/test_use_cases.py`:

```python
"""Unit tests for application use cases (Phase 2) — run against fakes."""

import pytest

from backend.application.errors import (
    JitsiConfigMissingError,
    RoomInactiveError,
    RoomNotFoundError,
)
from backend.application.use_cases.chat import ListMessagesUseCase, SendMessageUseCase
from backend.application.use_cases.participation import (
    JoinRoomUseCase,
    LeaveRoomUseCase,
    ListParticipantsUseCase,
)
from backend.application.use_cases.room_lifecycle import (
    CreateRoomUseCase,
    EndRoomUseCase,
    GetRoomUseCase,
    ListRoomsUseCase,
)
from backend.application.use_cases.token import GenerateJoinTokenUseCase
from backend.domain.entities import JitsiConfig
from backend.tests.fakes import (
    FakeTokenGenerator,
    InMemoryRoomRepository,
    StaticJitsiConfigProvider,
)


@pytest.fixture
def repo():
    r = InMemoryRoomRepository()
    r.add_user(1, "alice")
    r.add_user(2, "bob")
    return r


@pytest.fixture
def created_room(repo):
    return CreateRoomUseCase(repo).execute("Standup", user_id=1)


class TestCreateRoomUseCase:
    def test_creates_room_with_generated_jitsi_id(self, repo):
        dto = CreateRoomUseCase(repo).execute("  Standup  ", user_id=1)
        assert dto.name == "Standup"  # trimmed by RoomName
        assert dto.jitsi_room_id
        assert dto.created_by == 1
        assert dto.is_active is True
        assert dto.id is not None

    def test_rejects_invalid_name(self, repo):
        with pytest.raises(ValueError):
            CreateRoomUseCase(repo).execute("   ", user_id=1)


class TestListRoomsUseCase:
    def test_lists_only_active_rooms_with_participant_counts(self, repo):
        a = CreateRoomUseCase(repo).execute("A", 1)
        b = CreateRoomUseCase(repo).execute("B", 1)
        JoinRoomUseCase(repo).execute(a.id, 2)
        JoinRoomUseCase(repo).execute(a.id, 1)
        EndRoomUseCase(repo).execute(b.id)

        rooms = ListRoomsUseCase(repo).execute()
        assert [r.name for r in rooms] == ["A"]
        assert rooms[0].participant_count == 2


class TestGetRoomUseCase:
    def test_returns_detail_with_participants(self, repo, created_room):
        JoinRoomUseCase(repo).execute(created_room.id, 2)
        detail = GetRoomUseCase(repo).execute(created_room.id)
        assert detail.name == "Standup"
        assert [p.username for p in detail.participants] == ["bob"]

    def test_raises_when_missing(self, repo):
        with pytest.raises(RoomNotFoundError):
            GetRoomUseCase(repo).execute(999)


class TestEndRoomUseCase:
    def test_closes_room(self, repo, created_room):
        EndRoomUseCase(repo).execute(created_room.id)
        assert repo.get_room(created_room.id).is_active is False

    def test_raises_when_missing(self, repo):
        with pytest.raises(RoomNotFoundError):
            EndRoomUseCase(repo).execute(999)


class TestJoinLeaveUseCases:
    def test_join_and_leave_cycle(self, repo, created_room):
        JoinRoomUseCase(repo).execute(created_room.id, 2)
        assert repo.count_participants(created_room.id) == 1

        LeaveRoomUseCase(repo).execute(created_room.id, 2)
        assert repo.count_participants(created_room.id) == 0

    def test_rejoin_restores_connection(self, repo, created_room):
        JoinRoomUseCase(repo).execute(created_room.id, 2)
        LeaveRoomUseCase(repo).execute(created_room.id, 2)
        JoinRoomUseCase(repo).execute(created_room.id, 2)
        assert repo.count_participants(created_room.id) == 1

    def test_join_missing_room_raises(self, repo):
        with pytest.raises(RoomNotFoundError):
            JoinRoomUseCase(repo).execute(999, 2)

    def test_leave_is_idempotent(self, repo, created_room):
        LeaveRoomUseCase(repo).execute(created_room.id, 2)  # never joined
        LeaveRoomUseCase(repo).execute(created_room.id, 2)


class TestListParticipantsUseCase:
    def test_lists_participants(self, repo, created_room):
        JoinRoomUseCase(repo).execute(created_room.id, 1)
        JoinRoomUseCase(repo).execute(created_room.id, 2)
        participants = ListParticipantsUseCase(repo).execute(created_room.id)
        assert [p.username for p in participants] == ["alice", "bob"]

    def test_raises_when_room_missing(self, repo):
        with pytest.raises(RoomNotFoundError):
            ListParticipantsUseCase(repo).execute(999)


class TestChatUseCases:
    def test_send_and_list_messages(self, repo, created_room):
        SendMessageUseCase(repo).execute(created_room.id, 1, "  hello  ")
        SendMessageUseCase(repo).execute(created_room.id, 2, "hi")

        messages = ListMessagesUseCase(repo).execute(created_room.id)
        assert [(m.username, m.text) for m in messages] == [("alice", "hello"), ("bob", "hi")]

    def test_send_rejects_blank_text(self, repo, created_room):
        with pytest.raises(ValueError):
            SendMessageUseCase(repo).execute(created_room.id, 1, "   ")

    def test_send_to_missing_room_raises(self, repo):
        with pytest.raises(RoomNotFoundError):
            SendMessageUseCase(repo).execute(999, 1, "hi")

    def test_list_messages_paginates(self, repo, created_room):
        for i in range(5):
            SendMessageUseCase(repo).execute(created_room.id, 1, f"msg{i}")
        page2 = ListMessagesUseCase(repo).execute(created_room.id, page=2, size=2)
        assert [m.text for m in page2] == ["msg1", "msg2"]

    def test_list_messages_missing_room_raises(self, repo):
        with pytest.raises(RoomNotFoundError):
            ListMessagesUseCase(repo).execute(999)


class TestGenerateJoinTokenUseCase:
    @pytest.fixture
    def token_generator(self):
        return FakeTokenGenerator()

    @pytest.fixture
    def config(self):
        return StaticJitsiConfigProvider(JitsiConfig(app_id="vcs", app_secret="s3cret"))

    def test_generates_token_for_active_room(self, repo, created_room, token_generator, config):
        dto = GenerateJoinTokenUseCase(repo, token_generator, config).execute(
            created_room.id, username="alice"
        )
        assert dto.token.startswith("fake-jwt.")
        assert token_generator.calls == [(created_room.jitsi_room_id, "alice")]

    def test_raises_when_room_missing(self, repo, token_generator, config):
        with pytest.raises(RoomNotFoundError):
            GenerateJoinTokenUseCase(repo, token_generator, config).execute(999, "alice")

    def test_raises_when_room_inactive(self, repo, created_room, token_generator, config):
        EndRoomUseCase(repo).execute(created_room.id)
        with pytest.raises(RoomInactiveError):
            GenerateJoinTokenUseCase(repo, token_generator, config).execute(
                created_room.id, "alice"
            )

    def test_raises_when_config_missing(self, repo, created_room, token_generator):
        use_case = GenerateJoinTokenUseCase(repo, token_generator, StaticJitsiConfigProvider(None))
        with pytest.raises(JitsiConfigMissingError):
            use_case.execute(created_room.id, "alice")
```

`backend/tests/unit/test_auth_use_case.py`:

```python
"""Unit tests for the LoginUseCase (Phase 4)."""

import pytest

from backend.application.errors import InvalidCredentialsError
from backend.application.use_cases.auth import LoginUseCase
from backend.tests.fakes import FakePasswordHasher, FakeUserRepository


@pytest.fixture
def users():
    return FakeUserRepository()


@pytest.fixture
def passwords():
    return FakePasswordHasher()


class TestLoginUseCase:
    def test_login_existing_user_with_correct_password(self, users, passwords):
        users.seed("alice", passwords.hash("pw"), role="user")
        dto = LoginUseCase(users, passwords).execute("alice", "pw")
        assert dto.access_token == "stub-token-for-alice"
        assert dto.username == "alice"
        assert dto.role == "user"

    def test_login_existing_user_with_wrong_password_raises(self, users, passwords):
        users.seed("alice", passwords.hash("pw"))
        with pytest.raises(InvalidCredentialsError):
            LoginUseCase(users, passwords).execute("alice", "wrong")

    def test_first_login_creates_user(self, users, passwords):
        dto = LoginUseCase(users, passwords).execute("bob", "pw")
        assert dto.role == "user"
        account = users.get_by_username("bob")
        assert account is not None
        assert account.password_hash == "hashed:pw"

    def test_first_login_with_admin_username_gets_admin_role(self, users, passwords):
        dto = LoginUseCase(users, passwords).execute("admin", "pw")
        assert dto.role == "admin"
```

### Step 3 — run them (red)

```bash
uv run pytest backend/tests/unit -q
# ModuleNotFoundError: No module named 'backend.application'   ← expected
```

### Step 4 — implement

`backend/application/errors.py`:

```python
"""Application-level errors.

Raised by use cases; mapped to HTTP responses by the interfaces layer.
The application layer never imports FastAPI/HTTPException — that coupling
would break the dependency rule (HTTP is an outer-layer concern).
"""


class ApplicationError(Exception):
    """Base class for all application errors."""


class RoomNotFoundError(ApplicationError):
    def __init__(self, room_id: int):
        super().__init__(f"Room {room_id} not found")
        self.room_id = room_id


class RoomInactiveError(ApplicationError):
    def __init__(self, room_id: int):
        super().__init__(f"Room {room_id} is not active")
        self.room_id = room_id


class JitsiConfigMissingError(ApplicationError):
    def __init__(self):
        super().__init__("Jitsi configuration is missing")


class InvalidCredentialsError(ApplicationError):
    def __init__(self):
        super().__init__("Invalid username or password")
```

`backend/application/dto.py`:

```python
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
```

`backend/application/use_cases/room_lifecycle.py`:

```python
"""Room lifecycle use cases: create, list, get, end.

Each use case is a single class with one public method (SRP — the S in SOLID).
Use cases depend only on domain ports (DIP), never on concrete infrastructure.
"""

from dataclasses import replace

from backend.application.dto import ParticipantDTO, RoomDTO, RoomDetailDTO
from backend.application.errors import RoomNotFoundError
from backend.domain.entities import JitsiRoomId, Room, RoomName
from backend.domain.ports.room_repository import RoomRepository


class CreateRoomUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, name: str, user_id: int) -> RoomDTO:
        room = Room(
            id=None,
            name=RoomName(name),
            jitsi_room_id=JitsiRoomId.generate(),
            created_by=user_id,
        )
        return RoomDTO.from_domain(self._rooms.create_room(room))


class ListRoomsUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self) -> list[RoomDTO]:
        result = []
        for room in self._rooms.list_active_rooms():
            dto = RoomDTO.from_domain(room)
            result.append(
                replace(dto, participant_count=self._rooms.count_participants(room.id))
            )
        return result


class GetRoomUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int) -> RoomDetailDTO:
        room = self._rooms.get_room(room_id)
        if not room:
            raise RoomNotFoundError(room_id)
        participants = [ParticipantDTO.from_domain(p) for p in self._rooms.list_participants(room_id)]
        return RoomDetailDTO(
            id=room.id,
            name=room.name.value,
            jitsi_room_id=room.jitsi_room_id.value,
            created_by=room.created_by,
            is_active=room.is_active,
            created_at=room.created_at,
            participants=participants,
        )


class EndRoomUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int) -> None:
        if not self._rooms.close_room(room_id):
            raise RoomNotFoundError(room_id)
```

`backend/application/use_cases/participation.py`:

```python
"""Participation use cases: join, leave, list participants."""

from backend.application.dto import ParticipantDTO
from backend.application.errors import RoomNotFoundError
from backend.domain.ports.room_repository import RoomRepository


class JoinRoomUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int, user_id: int) -> None:
        if not self._rooms.get_room(room_id):
            raise RoomNotFoundError(room_id)
        self._rooms.add_participant(room_id, user_id)


class LeaveRoomUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int, user_id: int) -> None:
        self._rooms.remove_participant(room_id, user_id)


class ListParticipantsUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int) -> list[ParticipantDTO]:
        if not self._rooms.get_room(room_id):
            raise RoomNotFoundError(room_id)
        return [ParticipantDTO.from_domain(p) for p in self._rooms.list_participants(room_id)]
```

`backend/application/use_cases/chat.py`:

```python
"""Chat use cases: send and list room messages."""

from backend.application.dto import MessageDTO
from backend.application.errors import RoomNotFoundError
from backend.domain.ports.room_repository import RoomRepository


class SendMessageUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int, user_id: int, text: str) -> MessageDTO:
        if not self._rooms.get_room(room_id):
            raise RoomNotFoundError(room_id)
        message = self._rooms.add_message(room_id, user_id, text)
        return MessageDTO.from_domain(message)


class ListMessagesUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int, page: int = 1, size: int = 50) -> list[MessageDTO]:
        if not self._rooms.get_room(room_id):
            raise RoomNotFoundError(room_id)
        return [
            MessageDTO.from_domain(m)
            for m in self._rooms.list_messages(room_id, page=page, size=size)
        ]
```

`backend/application/use_cases/token.py`:

```python
"""Token use case: issue a JWT authorizing a user to join a Jitsi room."""

from backend.application.dto import JoinTokenDTO
from backend.application.errors import JitsiConfigMissingError, RoomInactiveError, RoomNotFoundError
from backend.domain.ports.jitsi_config_provider import JitsiConfigProvider
from backend.domain.ports.room_repository import RoomRepository
from backend.domain.ports.token_generator import RoomTokenGenerator


class GenerateJoinTokenUseCase:
    def __init__(
        self,
        rooms: RoomRepository,
        tokens: RoomTokenGenerator,
        config: JitsiConfigProvider,
    ):
        self._rooms = rooms
        self._tokens = tokens
        self._config = config

    def execute(self, room_id: int, username: str) -> JoinTokenDTO:
        room = self._rooms.get_room(room_id)
        if not room:
            raise RoomNotFoundError(room_id)
        if not room.is_active:
            raise RoomInactiveError(room_id)
        config = self._config.get()
        if not config:
            raise JitsiConfigMissingError()
        return JoinTokenDTO(token=self._tokens.generate(room, username, config))
```

`backend/application/use_cases/auth.py`:

```python
"""Auth use case: login (self-registration on first login — stub auth).

Real JWT-based authentication for the app's own users is a documented TODO;
the token issued here is `stub-token-for-{username}`.
"""

from backend.application.dto import LoginDTO
from backend.application.errors import InvalidCredentialsError
from backend.domain.ports.password_hasher import PasswordHasher
from backend.domain.ports.user_repository import UserRepository

TOKEN_PREFIX = "stub-token-for-"


class LoginUseCase:
    def __init__(self, users: UserRepository, passwords: PasswordHasher):
        self._users = users
        self._passwords = passwords

    def execute(self, username: str, password: str) -> LoginDTO:
        account = self._users.get_by_username(username)
        if account:
            if not self._passwords.verify(password, account.password_hash):
                raise InvalidCredentialsError()
        else:
            role = "admin" if username == "admin" else "user"
            account = self._users.create(username, self._passwords.hash(password), role)
        return LoginDTO(
            access_token=f"{TOKEN_PREFIX}{account.username}",
            username=account.username,
            role=account.role,
        )
```

### Step 5 — run them (green)

```bash
uv run pytest backend/tests/unit -q
# 41 passed
```

---

## 2. Design notes

- **One class, one use case.** No god-service. `CreateRoomUseCase` has a single
  reason to change; wiring happens in the composition root (Phase 4).
- **Errors are typed, not stringly.** `RoomNotFoundError` carries the id; the
  interfaces layer maps types → status codes (404/400/401/500) in one place.
- **DTOs isolate the domain.** HTTP responses never serialize domain entities
  directly — if the domain shape changes, only `from_domain` mappers change.
- **Chat pagination convention** (same as MediaService): page 1 = the *newest*
  messages, each page returned oldest-first for display. The fake repository
  replicates this convention exactly so unit and integration tests agree.
- **Login self-registers on first use** (deliberate simplification for a
  standalone system, documented). `admin` username → `admin` role. The seeded
  admin (`12345@mn`) overrides this path since the account already exists.

## 3. Verification

```bash
cd /home/mohammad/Desktop/my-projects/video-call-system
uv run pytest backend/tests/unit -v
```
