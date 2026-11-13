# video-call-system

Self-hosted video call system: **FastAPI backend + React frontend + self-hosted Jitsi Meet** (6 Docker containers), built with **lite-DDD**, **SOLID**, and **TDD (e2e-first)**.

Derived from the Jitsi integration of the MediaService project, re-architected as a standalone system.

## Features

- Rooms: create, list (with live participant counts), join, leave, end
- Per-meeting chat with polling
- JWT-secured Jitsi meeting rooms (HS256, `aud=jitsi`, per-room claims, 24h expiry)
- Jitsi iframe embed (camera/mic/screen share) with HTTPS (self-signed TLS for LAN)
- Stub token auth (`stub-token-for-{username}` — real JWT auth is a documented TODO)

## Architecture

```
┌─────────────── Browser ───────────────┐
│  React SPA (RoomsPage / MeetingPage)  │
└──────┬──────────────────────┬─────────┘
       │ HTTP :80 (nginx)     │ HTTPS :8443 (Jitsi iframe)
┌──────▼───────┐       ┌──────▼───────────────────────────┐
│ nginx (SPA + │       │ jitsi-web → prosody → jicofo     │
│ /api proxy)  │       │              → jvb (UDP :10000)  │
└──────┬───────┘       └──────────────────────────────────┘
┌──────▼───────────────────────┐
│ FastAPI (lite-DDD backend)   │
│ domain → application → infra │
│ SQLite (video_call.db)       │
└──────────────────────────────┘
```

### Backend layering (lite-DDD)

| Layer | Path | Responsibility |
|---|---|---|
| Domain | `backend/domain/` | Entities + value objects + ports (abstract interfaces) |
| Application | `backend/application/` | Use cases (one class per use case), DTOs, app-level errors |
| Infrastructure | `backend/infrastructure/` | SQLAlchemy repository, JWT generator, stub auth, config provider |
| Interfaces | `backend/interfaces/` | FastAPI routers, Pydantic schemas, composition root |

Dependency rule: outer layers depend on inner layers; domain knows nothing about SQLAlchemy, FastAPI, or HTTP.

### Frontend (SOLID)

- `api/` — transport (`httpClient`), auth (`authApi`), rooms (`roomsApi`) — one concern per module
- `hooks/` — data-fetching logic separated from presentation (`useRooms`, `useMeetingSession`, `useChat`)
- `components/` — presentational components (props in, events out): `RoomCard`, `CreateRoomForm`, `JitsiIframe`, `ChatPanel`
- `pages/` — composition only
- `context/AuthContext.jsx` — auth state

## Quick start (dev)

```bash
# Backend (uv, from project root)
uv sync
uv run uvicorn backend.main:app --reload --port 8000

# Frontend (vite dev server, proxies /api → :8000)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 — login with any username/password (users are auto-created; `admin` becomes admin role).

## Quick start (Docker, full stack incl. Jitsi)

```bash
# 1. Generate TLS certs (LAN IP — see docs/09)
mkdir -p jitsi-certs && ./scripts/gen-certs.sh <YOUR-LAN-IP>

# 2. Build frontend
cd frontend && npm install && npm run build && cd ..

# 3. Start the stack
docker compose up -d --build
```

## Tests

```bash
# Backend: unit + integration + e2e (in-memory SQLite, no Docker needed)
uv run pytest backend/tests -v

# Frontend e2e (Playwright — dev servers on :8000/:5173, Jitsi iframe mocked)
cd frontend && node tests/phase1-auth-rooms.mjs && node tests/phase2-meeting-chat.mjs
```

## Documentation (phase by phase)

| Doc | Phase |
|---|---|
| [docs/00-overview.md](docs/00-overview.md) | Architecture, TDD/SOLID/DDD approach, roadmap |
| [docs/01-phase1-domain.md](docs/01-phase1-domain.md) | Domain entities + ports (TDD: unit) |
| [docs/02-phase2-use-cases.md](docs/02-phase2-use-cases.md) | Application use cases + DTOs (TDD: unit) |
| [docs/03-phase3-infrastructure.md](docs/03-phase3-infrastructure.md) | SQLAlchemy repo, JWT generator, auth (TDD: integration) |
| [docs/04-phase4-api.md](docs/04-phase4-api.md) | FastAPI routers + schemas (TDD: e2e) |
| [docs/05-phase5-frontend-foundation.md](docs/05-phase5-frontend-foundation.md) | Vite app, API modules, auth context |
| [docs/06-phase6-rooms-page.md](docs/06-phase6-rooms-page.md) | RoomsPage + hooks (Playwright e2e) |
| [docs/07-phase7-meeting-page.md](docs/07-phase7-meeting-page.md) | MeetingPage, JitsiIframe, chat (Playwright e2e) |
| [docs/08-phase8-docker-jitsi.md](docs/08-phase8-docker-jitsi.md) | Docker Compose, Jitsi containers, BOSH |
| [docs/09-phase9-deployment-tls.md](docs/09-phase9-deployment-tls.md) | TLS, deployment, resources, per-room keys roadmap |

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./video_call.db` | SQLite location |
| `JITSI_JWT_APP_ID` | `video-call-system` | JWT `iss` claim (must match prosody `JWT_APP_ID`) |
| `JITSI_JWT_SECRET` | (seeded in DB) | HS256 shared secret — must match prosody `JWT_APP_SECRET` |
| `JITSI_JWT_EXPIRE_MINUTES` | `1440` | Token lifetime (24h) |
