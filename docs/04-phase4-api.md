# Phase 4 — API interfaces: schemas, routers, composition root, e2e

**Status: ✅ complete** · TDD layer: **e2e** · Tests: `backend/tests/e2e/` (21 tests)

**Goal:** the outermost backend layer. Pydantic schemas, thin FastAPI routers,
the composition root (`container.py`), the app factory, and centralized
application-error → HTTP mapping. The e2e suite drives the *real* app through
HTTP on an in-memory SQLite database.

---

## 1. TDD cycle

### Step 1 — e2e fixtures

`backend/tests/e2e/conftest.py`:

```python
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
```

### Step 2 — write the failing tests

`backend/tests/e2e/test_auth_e2e.py`:

```python
"""E2E tests: auth endpoints (Phase 4)."""


class TestLoginE2E:
    def test_first_login_creates_user_and_returns_stub_token(self, client):
        response = client.post("/api/auth/login", json={"username": "bob", "password": "pw"})
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "stub-token-for-bob"
        assert body["username"] == "bob"
        assert body["role"] == "user"

    def test_second_login_with_correct_password(self, client):
        client.post("/api/auth/login", json={"username": "carol", "password": "pw"})
        response = client.post("/api/auth/login", json={"username": "carol", "password": "pw"})
        assert response.status_code == 200
        assert response.json()["access_token"] == "stub-token-for-carol"

    def test_second_login_with_wrong_password_is_401(self, client):
        client.post("/api/auth/login", json={"username": "dave", "password": "pw"})
        response = client.post("/api/auth/login", json={"username": "dave", "password": "nope"})
        assert response.status_code == 401

    def test_seeded_admin_logs_in_with_seeded_password(self, client):
        # "admin" is seeded at startup with password "12345@mn"
        response = client.post("/api/auth/login", json={"username": "admin", "password": "12345@mn"})
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    def test_seeded_admin_wrong_password_is_401(self, client):
        response = client.post("/api/auth/login", json={"username": "admin", "password": "pw"})
        assert response.status_code == 401

    def test_missing_fields_are_422(self, client):
        assert client.post("/api/auth/login", json={"username": "x"}).status_code == 422
        assert client.post("/api/auth/login", json={}).status_code == 422


class TestAuthEnforcementE2E:
    def test_create_room_requires_auth(self, client):
        response = client.post("/api/rooms", json={"name": "standup"})
        assert response.status_code == 401

    def test_garbage_token_is_401(self, client):
        client.headers["Authorization"] = "Bearer not-a-real-token"
        response = client.post("/api/rooms", json={"name": "standup"})
        assert response.status_code == 401
```

`backend/tests/e2e/test_rooms_e2e.py`:

```python
"""E2E tests: rooms API (Phase 4) — the acceptance criteria for the backend."""

import jwt

JITSI_SECRET = "test-secret"


def _create_room(client, name="standup"):
    response = client.post("/api/rooms", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


class TestRoomLifecycleE2E:
    def test_create_room(self, auth_client):
        room = _create_room(auth_client, "  standup  ")
        assert room["id"] > 0
        assert room["name"] == "standup"  # trimmed
        assert room["jitsi_room_id"]
        assert room["is_active"] is True
        assert room["participant_count"] == 0

    def test_create_room_blank_name_is_422(self, auth_client):
        response = auth_client.post("/api/rooms", json={"name": "   "})
        assert response.status_code == 422

    def test_list_rooms_is_open_and_shows_counts(self, client, auth_client):
        created = _create_room(auth_client, "team")
        response = client.get("/api/rooms")  # no auth header
        assert response.status_code == 200
        items = response.json()["items"]
        assert any(r["id"] == created["id"] for r in items)

    def test_get_room_detail_with_participants(self, client, auth_client):
        created = _create_room(auth_client)
        auth_client.post(f"/api/rooms/{created['id']}/join")
        response = client.get(f"/api/rooms/{created['id']}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["name"] == "standup"
        assert [p["username"] for p in detail["participants"]] == ["alice"]

    def test_get_missing_room_is_404(self, client):
        assert client.get("/api/rooms/9999").status_code == 404

    def test_end_room_hides_it_from_list(self, client, auth_client):
        created = _create_room(auth_client)
        assert auth_client.delete(f"/api/rooms/{created['id']}").status_code == 204
        items = client.get("/api/rooms").json()["items"]
        assert all(r["id"] != created["id"] for r in items)
        assert client.get(f"/api/rooms/{created['id']}").json()["is_active"] is False

    def test_end_missing_room_is_404(self, auth_client):
        assert auth_client.delete("/api/rooms/9999").status_code == 404


class TestParticipationE2E:
    def test_join_and_leave_cycle(self, client, auth_client):
        created = _create_room(auth_client)

        response = auth_client.post(f"/api/rooms/{created['id']}/join")
        assert response.status_code == 204
        assert auth_client.get(f"/api/rooms/{created['id']}/participants").json()[0]["username"] == "alice"

        assert auth_client.post(f"/api/rooms/{created['id']}/leave").status_code == 204
        assert auth_client.get(f"/api/rooms/{created['id']}/participants").json()[0]["left_at"] is not None
        items = client.get("/api/rooms").json()["items"]
        assert items[0]["participant_count"] == 0

    def test_join_missing_room_is_404(self, auth_client):
        assert auth_client.post("/api/rooms/9999/join").status_code == 404

    def test_join_requires_auth(self, client):
        assert client.post("/api/rooms/1/join").status_code == 401


class TestChatE2E:
    def test_send_and_list_messages(self, auth_client):
        created = _create_room(auth_client)
        sent = auth_client.post(
            f"/api/rooms/{created['id']}/messages", json={"message": "  hello  "}
        )
        assert sent.status_code == 201
        assert sent.json()["text"] == "hello"
        assert sent.json()["username"] == "alice"

        response = auth_client.get(f"/api/rooms/{created['id']}/messages")
        assert response.status_code == 200
        items = response.json()["items"]
        assert [m["text"] for m in items] == ["hello"]

    def test_blank_message_is_422(self, auth_client):
        created = _create_room(auth_client)
        response = auth_client.post(f"/api/rooms/{created['id']}/messages", json={"message": "  "})
        assert response.status_code == 422

    def test_send_to_missing_room_is_404(self, auth_client):
        response = auth_client.post("/api/rooms/9999/messages", json={"message": "hi"})
        assert response.status_code == 404

    def test_send_requires_auth(self, client):
        assert client.post("/api/rooms/1/messages", json={"message": "hi"}).status_code == 401


class TestTokenE2E:
    def test_token_is_valid_jitsi_jwt(self, auth_client):
        created = _create_room(auth_client)
        response = auth_client.post(f"/api/rooms/{created['id']}/token")
        assert response.status_code == 200

        decoded = jwt.decode(
            response.json()["token"], JITSI_SECRET, algorithms=["HS256"], audience="jitsi"
        )
        assert decoded["iss"] == "video-call-system"
        assert decoded["sub"] == "meet.jitsi"
        assert decoded["room"] == created["jitsi_room_id"]
        assert decoded["context"]["user"]["name"] == "alice"

    def test_token_for_missing_room_is_404(self, auth_client):
        assert auth_client.post("/api/rooms/9999/token").status_code == 404

    def test_token_for_ended_room_is_400(self, auth_client):
        created = _create_room(auth_client)
        auth_client.delete(f"/api/rooms/{created['id']}")
        assert auth_client.post(f"/api/rooms/{created['id']}/token").status_code == 400

    def test_token_requires_auth(self, client):
        assert client.post("/api/rooms/1/token").status_code == 401
```

### Step 3 — run them (red)

```bash
uv run pytest backend/tests/e2e -q
# ModuleNotFoundError: No module named 'backend.main'   ← expected
```

### Step 4 — implement

`backend/interfaces/schemas/auth.py`:

```python
"""Pydantic schemas for auth endpoints."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class LoginResponse(BaseModel):
    access_token: str
    username: str
    role: str
```

`backend/interfaces/schemas/rooms.py`:

```python
"""Pydantic schemas for room endpoints (HTTP view of application DTOs)."""

from datetime import datetime

from pydantic import BaseModel, Field

from backend.application.dto import MessageDTO, ParticipantDTO, RoomDTO, RoomDetailDTO


class RoomCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class RoomResponse(BaseModel):
    id: int
    name: str
    jitsi_room_id: str
    created_by: int
    is_active: bool
    created_at: datetime | None
    participant_count: int = 0

    @classmethod
    def from_dto(cls, dto: RoomDTO) -> "RoomResponse":
        return cls(
            id=dto.id,
            name=dto.name,
            jitsi_room_id=dto.jitsi_room_id,
            created_by=dto.created_by,
            is_active=dto.is_active,
            created_at=dto.created_at,
            participant_count=dto.participant_count,
        )


class RoomListResponse(BaseModel):
    items: list[RoomResponse]


class ParticipantResponse(BaseModel):
    user_id: int
    username: str
    joined_at: datetime | None
    left_at: datetime | None

    @classmethod
    def from_dto(cls, dto: ParticipantDTO) -> "ParticipantResponse":
        return cls(
            user_id=dto.user_id,
            username=dto.username,
            joined_at=dto.joined_at,
            left_at=dto.left_at,
        )


class RoomDetailResponse(BaseModel):
    id: int
    name: str
    jitsi_room_id: str
    created_by: int
    is_active: bool
    created_at: datetime | None
    participants: list[ParticipantResponse]

    @classmethod
    def from_dto(cls, dto: RoomDetailDTO) -> "RoomDetailResponse":
        return cls(
            id=dto.id,
            name=dto.name,
            jitsi_room_id=dto.jitsi_room_id,
            created_by=dto.created_by,
            is_active=dto.is_active,
            created_at=dto.created_at,
            participants=[ParticipantResponse.from_dto(p) for p in dto.participants],
        )


class MessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: int
    room_id: int
    user_id: int
    username: str
    text: str
    created_at: datetime | None

    @classmethod
    def from_dto(cls, dto: MessageDTO) -> "MessageResponse":
        return cls(
            id=dto.id,
            room_id=dto.room_id,
            user_id=dto.user_id,
            username=dto.username,
            text=dto.text,
            created_at=dto.created_at,
        )


class MessageListResponse(BaseModel):
    items: list[MessageResponse]


class RoomTokenResponse(BaseModel):
    token: str
```

`backend/interfaces/container.py` (composition root):

```python
"""Composition root: wires use cases to their infrastructure adapters.

The only place in the codebase where concrete infrastructure classes are
instantiated. Everything else depends on ports (domain/ports) or DTOs.
"""

from backend.application.use_cases.auth import LoginUseCase
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
from backend.config import Settings
from backend.infrastructure.auth.jwt_token_generator import JwtRoomTokenGenerator
from backend.infrastructure.auth.passwords import Pbkdf2PasswordHasher
from backend.infrastructure.auth.stub_authenticator import StubAuthenticator
from backend.infrastructure.config.db_jitsi_config import DbJitsiConfigProvider
from backend.infrastructure.db.database import Database
from backend.infrastructure.db.room_repository import SqlAlchemyRoomRepository
from backend.infrastructure.db.user_repository import SqlAlchemyUserRepository


class Container:
    def __init__(self, database: Database, settings: Settings):
        self.database = database
        self.settings = settings

    # -- driven adapters (implement domain ports) -------------------------

    def rooms_repository(self, session) -> SqlAlchemyRoomRepository:
        return SqlAlchemyRoomRepository(session)

    def users_repository(self, session) -> SqlAlchemyUserRepository:
        return SqlAlchemyUserRepository(session)

    def password_hasher(self) -> Pbkdf2PasswordHasher:
        return Pbkdf2PasswordHasher()

    def token_generator(self) -> JwtRoomTokenGenerator:
        return JwtRoomTokenGenerator(self.settings.jitsi_jwt_expire_minutes)

    def jitsi_config_provider(self) -> DbJitsiConfigProvider:
        return DbJitsiConfigProvider(
            self.database.session_factory,
            self.settings.jitsi_jwt_app_id,
            self.settings.jitsi_jwt_secret,
        )

    def authenticator(self, session) -> StubAuthenticator:
        return StubAuthenticator(self.users_repository(session))

    # -- use cases ---------------------------------------------------------

    def login(self, session) -> LoginUseCase:
        return LoginUseCase(self.users_repository(session), self.password_hasher())

    def create_room(self, session) -> CreateRoomUseCase:
        return CreateRoomUseCase(self.rooms_repository(session))

    def list_rooms(self, session) -> ListRoomsUseCase:
        return ListRoomsUseCase(self.rooms_repository(session))

    def get_room(self, session) -> GetRoomUseCase:
        return GetRoomUseCase(self.rooms_repository(session))

    def end_room(self, session) -> EndRoomUseCase:
        return EndRoomUseCase(self.rooms_repository(session))

    def join_room(self, session) -> JoinRoomUseCase:
        return JoinRoomUseCase(self.rooms_repository(session))

    def leave_room(self, session) -> LeaveRoomUseCase:
        return LeaveRoomUseCase(self.rooms_repository(session))

    def list_participants(self, session) -> ListParticipantsUseCase:
        return ListParticipantsUseCase(self.rooms_repository(session))

    def send_message(self, session) -> SendMessageUseCase:
        return SendMessageUseCase(self.rooms_repository(session))

    def list_messages(self, session) -> ListMessagesUseCase:
        return ListMessagesUseCase(self.rooms_repository(session))

    def generate_token(self, session) -> GenerateJoinTokenUseCase:
        return GenerateJoinTokenUseCase(
            self.rooms_repository(session),
            self.token_generator(),
            self.jitsi_config_provider(),
        )
```

`backend/interfaces/dependencies.py`:

```python
"""FastAPI dependencies: DB sessions, container access, stub auth."""

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.domain.entities import UserAccount
from backend.interfaces.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_db(request: Request):
    """One SQLAlchemy session per request, closed afterwards."""
    with request.app.state.database.session() as session:
        yield session


def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
) -> UserAccount:
    """Required auth — 401 unless a valid stub token is presented."""
    account = container.authenticator(db).authenticate(authorization)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return account
```

`backend/interfaces/routers/auth.py`:

```python
"""Auth endpoints (thin HTTP layer — all logic lives in use cases)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.interfaces.container import Container
from backend.interfaces.dependencies import get_container, get_db
from backend.interfaces.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    dto = container.login(db).execute(body.username, body.password)
    return LoginResponse(access_token=dto.access_token, username=dto.username, role=dto.role)
```

`backend/interfaces/routers/rooms.py`:

```python
"""Room endpoints (thin HTTP layer — all logic lives in use cases)."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.domain.entities import UserAccount
from backend.interfaces.container import Container
from backend.interfaces.dependencies import get_container, get_current_user, get_db
from backend.interfaces.schemas.rooms import (
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    ParticipantResponse,
    RoomCreate,
    RoomDetailResponse,
    RoomListResponse,
    RoomResponse,
    RoomTokenResponse,
)

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    body: RoomCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    dto = container.create_room(db).execute(body.name, current_user.id)
    return RoomResponse.from_dto(dto)


@router.get("", response_model=RoomListResponse)
def list_rooms(
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    items = container.list_rooms(db).execute()
    return RoomListResponse(items=[RoomResponse.from_dto(dto) for dto in items])


@router.get("/{room_id}", response_model=RoomDetailResponse)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    dto = container.get_room(db).execute(room_id)
    return RoomDetailResponse.from_dto(dto)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def end_room(
    room_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    container.end_room(db).execute(room_id)


@router.post("/{room_id}/join", status_code=status.HTTP_204_NO_CONTENT)
def join_room(
    room_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    container.join_room(db).execute(room_id, current_user.id)


@router.post("/{room_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_room(
    room_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    container.leave_room(db).execute(room_id, current_user.id)


@router.get("/{room_id}/participants", response_model=list[ParticipantResponse])
def get_participants(
    room_id: int,
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    items = container.list_participants(db).execute(room_id)
    return [ParticipantResponse.from_dto(dto) for dto in items]


@router.get("/{room_id}/messages", response_model=MessageListResponse)
def get_messages(
    room_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    items = container.list_messages(db).execute(room_id, page=page, size=size)
    return MessageListResponse(items=[MessageResponse.from_dto(dto) for dto in items])


@router.post("/{room_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def add_message(
    room_id: int,
    body: MessageCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    dto = container.send_message(db).execute(room_id, current_user.id, body.message)
    return MessageResponse.from_dto(dto)


@router.post("/{room_id}/token", response_model=RoomTokenResponse)
def get_room_token(
    room_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    dto = container.generate_token(db).execute(room_id, current_user.username)
    return RoomTokenResponse(token=dto.token)
```

`backend/main.py`:

```python
"""Application factory.

`create_app(database, settings)` builds the FastAPI app, seeds the database
(idempotent), wires the composition root, and maps application errors to
HTTP responses. The module-level `app` is the uvicorn entry point
(`uvicorn backend.main:app`).
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.application.errors import (
    ApplicationError,
    InvalidCredentialsError,
    JitsiConfigMissingError,
    RoomInactiveError,
    RoomNotFoundError,
)
from backend.config import Settings
from backend.infrastructure.db.database import Database
from backend.infrastructure.db.seed import seed_database
from backend.interfaces.container import Container
from backend.interfaces.routers.auth import router as auth_router
from backend.interfaces.routers.rooms import router as rooms_router


def create_app(database: Database, settings: Settings) -> FastAPI:
    seed_database(database, settings)

    app = FastAPI(
        title="video-call-system",
        description="Self-hosted video call system (lite-DDD, SOLID, TDD)",
    )
    app.state.database = database
    app.state.container = Container(database, settings)

    app.include_router(auth_router)
    app.include_router(rooms_router)

    # Application errors → HTTP. Keeps routers free of try/except blocks.
    @app.exception_handler(RoomNotFoundError)
    def _room_not_found(_request, exc: RoomNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RoomInactiveError)
    def _room_inactive(_request, exc: RoomInactiveError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(InvalidCredentialsError)
    def _invalid_credentials(_request, exc: InvalidCredentialsError):
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(JitsiConfigMissingError)
    def _config_missing(_request, exc: JitsiConfigMissingError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(ApplicationError)
    def _application_error(_request, exc: ApplicationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    def _validation_error(_request, exc: ValueError):
        # Domain value-object validation (RoomName, ChatMessage)
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok"}

    return app


settings = Settings.from_env()
app = create_app(Database(settings.database_url), settings)
```

### Step 5 — run them (green)

```bash
uv run pytest backend/tests/e2e -q
# 21 passed
```

---

## 2. Design notes

- **Routers stay thin.** Every endpoint is: parse input (Pydantic) → call one
  use case → map DTO to response schema. Zero business logic, zero try/except —
  the exception handlers in `main.py` map `ApplicationError`/`ValueError` types
  to status codes in one place (open/closed: adding a new error type = one new
  handler, no router changes).
- **Composition root owns the wiring.** `container.py` is the only file that
  imports concrete infrastructure classes; routers only ever see the `Container`.
  Swapping SQLite for Postgres means: new repository class + one line in the
  container.
- **App factory enables e2e.** `create_app(database, settings)` takes its
  dependencies as arguments — tests pass an in-memory SQLite engine; production
  passes the env-configured one. The real `video_call.db` is never opened by tests.
- **Pydantic catches shape errors (422), domain catches value errors (422 via
  `ValueError` handler).** Whitespace-only names pass Pydantic's `min_length`
  but fail `RoomName` — the layering stays honest: validation lives in the domain.

## 3. Verification

```bash
cd /home/mohammad/Desktop/my-projects/video-call-system
uv run pytest backend/tests -v            # full backend: 90 tests
uv run uvicorn backend.main:app --reload --port 8000   # manual smoke test
curl http://localhost:8000/health
```
