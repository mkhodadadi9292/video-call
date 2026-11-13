# Phase 0 — Overview: Architecture, TDD, SOLID, lite-DDD

**Status: ✅ complete (this document describes the whole project)**

This project is a standalone, self-hosted **video call system**:
FastAPI backend + React frontend + self-hosted Jitsi Meet (4 Jitsi containers).
It is derived from the Jitsi integration inside MediaService, re-architected from
scratch around three disciplines:

1. **lite-DDD** — layered backend with a domain core and ports/adapters
2. **SOLID** — one responsibility per class/module, dependency inversion everywhere
3. **TDD (e2e-first)** — every phase starts with failing tests; e2e tests are the acceptance criteria

---

## 1. Architecture at a glance

```
┌───────────────── Browser ─────────────────┐
│  React SPA: /login, /rooms, /meeting/:id  │
└───────┬──────────────────────┬────────────┘
        │ HTTP (nginx :80)     │ HTTPS (jitsi-web :8443, iframe)
┌───────▼────────┐      ┌──────▼─────────────────────────────┐
│ nginx          │      │ jitsi-web → jitsi-prosody (BOSH)   │
│  ├ SPA static  │      │            → jitsi-jicofo (focus)  │
│  └ /api proxy  │      │            → jitsi-jvb (SFU, UDP)  │
└───────┬────────┘      └────────────────────────────────────┘
┌───────▼───────────────────────────────┐
│ FastAPI backend (lite-DDD)            │
│  interfaces → application → domain    │
│  infrastructure implements ports      │
│  SQLite: video_call.db                │
└───────────────────────────────────────┘
```

### Backend layers (dependency rule: outer → inner only)

| Layer | Path | Depends on | Knows nothing about |
|---|---|---|---|
| **Domain** | `backend/domain/` | stdlib only | SQLAlchemy, FastAPI, HTTP, PyJWT |
| **Application** | `backend/application/` | domain (entities + ports) | persistence details, HTTP |
| **Infrastructure** | `backend/infrastructure/` | domain ports, SQLAlchemy, PyJWT | HTTP |
| **Interfaces** | `backend/interfaces/` | application + infrastructure (composition root only) | — |

```
backend/
├── domain/
│   ├── entities.py            # Room, RoomName, JitsiRoomId, Participant,
│   │                          #   ChatMessage, JitsiConfig, UserAccount
│   └── ports/                 # abstract interfaces (ABCs) — driven ports
│       ├── room_repository.py
│       ├── token_generator.py
│       ├── jitsi_config_provider.py
│       ├── user_repository.py
│       └── password_hasher.py
├── application/
│   ├── dto.py                 # RoomDTO, MessageDTO, JoinTokenDTO, LoginDTO…
│   ├── errors.py              # RoomNotFoundError, RoomInactiveError, …
│   └── use_cases/             # one class per use case (SRP)
│       ├── room_lifecycle.py  # CreateRoom, ListRooms, GetRoom, EndRoom
│       ├── participation.py   # JoinRoom, LeaveRoom, ListParticipants
│       ├── chat.py            # SendMessage, ListMessages
│       ├── token.py           # GenerateJoinToken
│       └── auth.py            # Login
├── infrastructure/
│   ├── db/                    # database.py, models.py (ORM),
│   │   │                      #   room_repository.py, user_repository.py, seed.py
│   ├── auth/                  # passwords.py, stub_authenticator.py,
│   │   │                      #   jwt_token_generator.py
│   └── config/                # db_jitsi_config.py
├── interfaces/
│   ├── container.py           # composition root (only place infra is instantiated)
│   ├── dependencies.py        # get_db, get_current_user
│   ├── schemas/               # Pydantic (auth.py, rooms.py)
│   └── routers/               # auth.py, rooms.py — thin HTTP layer
├── config.py                  # Settings (env vars)
└── main.py                    # create_app() factory
```

### How SOLID maps onto this

| Principle | Where |
|---|---|
| **S**ingle responsibility | Each use case is one class with one `execute()`; each API module owns one resource; each frontend module owns one concern (`httpClient` vs `authApi` vs `roomsApi`) |
| **O**pen/closed | Add features = add a use case class + a route; nothing existing changes. New repository impl = new adapter class |
| **L**iskov substitution | Fakes (`backend/tests/fakes.py`) implement the same ports as SQLAlchemy adapters — use cases can't tell them apart (that's how unit tests run) |
| **I**nterface segregation | Five small ports instead of one fat repository — a use case takes only the port it needs |
| **D**ependency inversion | Use cases depend on `RoomRepository` (ABC in domain), not `SqlAlchemyRoomRepository`; the composition root (`container.py`) does the wiring |

### How lite-DDD maps onto this

- **Entities/value objects** in `domain/entities.py` — validation lives here (`RoomName`, `ChatMessage` raise `ValueError` on bad input). Frozen dataclasses = immutability (`Room.close()` returns a new snapshot).
- **Ports** = the domain's abstract contracts with the outside world (hexagonal "driven ports").
- **Use cases** = application services, one per use case.
- **Repositories** = infrastructure adapters that translate ORM rows ↔ domain objects.
- **Aggregate**: `Room` is the root of the room lifecycle; participants/messages are accessed through it.
- Deliberately **lite**: no domain events, no event bus, no CQRS — a single SQLite DB, sync SQLAlchemy, thin FastAPI routers.

### TDD discipline used in every phase

1. Write the failing test (unit → integration → e2e depending on the phase)
2. Run it — watch it fail (**red**)
3. Write the minimum implementation
4. Run it — watch it pass (**green**)
5. Refactor with the safety net

The **e2e tests are the acceptance criteria**: `backend/tests/e2e/` exercises the
full HTTP API through a real app instance on an in-memory SQLite DB, and the
Playwright suites in `frontend/tests/` exercise the real UI.

---

## 2. Test strategy

| Layer | Tests | DB | What they prove |
|---|---|---|---|
| Unit | `backend/tests/unit/` | none (fakes) | domain validation + use-case logic |
| Integration | `backend/tests/integration/` | in-memory SQLite (real schema) | repositories, JWT generator, authenticator, config provider |
| E2E | `backend/tests/e2e/` | in-memory SQLite via full app | HTTP API behavior end-to-end |
| E2E (frontend) | `frontend/tests/phase*.mjs` | real backend on :8000 (temp DB) | UI flows with Playwright (Jitsi iframe mocked) |

```bash
uv run pytest backend/tests -v          # 90 tests, no Docker needed
```

The real `video_call.db` is **never** touched by tests (see `backend/tests/conftest.py` —
every test builds its own in-memory SQLite with `StaticPool`).

---

## 3. Phase roadmap

| Phase | Doc | Deliverable | TDD layer |
|---|---|---|---|
| 1 | [01-phase1-domain.md](01-phase1-domain.md) | Entities, value objects, ports | unit |
| 2 | [02-phase2-use-cases.md](02-phase2-use-cases.md) | Use cases, DTOs, errors, fakes | unit |
| 3 | [03-phase3-infrastructure.md](03-phase3-infrastructure.md) | ORM models, repositories, JWT generator, stub auth, config provider, seeding | integration |
| 4 | [04-phase4-api.md](04-phase4-api.md) | Schemas, routers, composition root, app factory, error mapping | e2e |
| 5 | [05-phase5-frontend-foundation.md](05-phase5-frontend-foundation.md) | Vite+React app, API modules, AuthContext | build + manual |
| 6 | [06-phase6-rooms-page.md](06-phase6-rooms-page.md) | RoomsPage + hooks (list/create/end) | Playwright e2e |
| 7 | [07-phase7-meeting-page.md](07-phase7-meeting-page.md) | MeetingPage, JitsiIframe, ChatPanel | Playwright e2e |
| 8 | [08-phase8-docker-jitsi.md](08-phase8-docker-jitsi.md) | Docker Compose (6 containers), Jitsi env, meet.conf | manual compose |
| 9 | [09-phase9-deployment-tls.md](09-phase9-deployment-tls.md) | TLS certs, deployment, resources, per-room keys roadmap | ops checklist |

---

## 4. API surface (final)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/auth/login` | none | Login (self-registers on first login) → `stub-token-for-{username}` |
| `POST` | `/api/rooms` | required | Create room (random `jitsi_room_id`) |
| `GET` | `/api/rooms` | optional | List active rooms + participant counts |
| `GET` | `/api/rooms/{id}` | optional | Room detail + participants |
| `DELETE` | `/api/rooms/{id}` | required | End room |
| `POST` | `/api/rooms/{id}/join` | required | Mark joined |
| `POST` | `/api/rooms/{id}/leave` | required | Mark left |
| `GET` | `/api/rooms/{id}/participants` | optional | Participant list |
| `GET` | `/api/rooms/{id}/messages?page=&size=` | optional | Chat history (oldest-first pages, newest page = 1) |
| `POST` | `/api/rooms/{id}/messages` | required | Send message |
| `POST` | `/api/rooms/{id}/token` | required | Jitsi join JWT (HS256) |
| `GET` | `/health` | none | Liveness |

### Error mapping (interfaces → HTTP)

| Application error | HTTP |
|---|---|
| `RoomNotFoundError` | 404 |
| `RoomInactiveError` | 400 |
| `InvalidCredentialsError` | 401 |
| `JitsiConfigMissingError` | 500 |
| `ValueError` (domain validation) | 422 |
| missing/invalid auth token | 401 |

### Jitsi JWT payload

```json
{
  "aud": "jitsi",
  "iss": "video-call-system",
  "sub": "meet.jitsi",
  "room": "<jitsi_room_id>",
  "exp": 1760112000,
  "iat": 1760025600,
  "context": { "user": { "name": "alice" } }
}
```

Prosody's `token_verification` module validates signature (shared `app_secret`),
audience, room claim, and expiry **at join time only** — users stay in the meeting
after expiry; reconnecting requires a fresh token.

---

## 5. Conventions

- Python 3.12+, `uv` for dependencies (`uv sync`, `uv run pytest`).
- No git commits are created by the build process — history is up to you.
- Env vars: `DATABASE_URL`, `JITSI_JWT_APP_ID`, `JITSI_JWT_SECRET`, `JITSI_JWT_EXPIRE_MINUTES`.
- Auth is deliberately stubbed (`stub-token-for-{username}`) — same convention as MediaService; real app-level JWT auth is a documented TODO. The **meeting** tokens are real JWTs.
- Chat is text-only in this standalone system (MediaService's media-sharing panel was intentionally dropped — there is no media library here).
