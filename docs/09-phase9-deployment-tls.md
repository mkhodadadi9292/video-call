# Phase 9 — Deployment & TLS

**Status: ✅ complete (documentation + tooling)**

Covers: why TLS is mandatory, cert generation/trust, resource planning, firewall
ports, and the per-room JWT key roadmap (adapted from MediaService's
`TLS_SETUP.md`, `DEPLOYMENT/deployment.md`, and `REFACTORING/per-room-keys.md`).

---

## 1. Why HTTPS everywhere

Browsers block `getUserMedia` (camera/mic) on insecure contexts — any origin
that is not `https://` or `localhost`. Two origins are involved:

```
Browser
 ├── https://<LAN-IP>/            ← main app (nginx :443)  — parent page
 └── https://<LAN-IP>:8443/       ← Jitsi iframe (jitsi-web) — embedded
```

Both must be HTTPS:
- the iframe needs a secure context for `getUserMedia` itself
- the **parent page** needs it too — Chrome refuses to delegate camera
  permission to a cross-origin iframe when the parent is plain HTTP
  (MediaService bug #10)

We use one self-signed cert for both (same `jitsi-certs/` mounted into
`vcs-nginx` and `vcs-jitsi-web`).

### Certificate generation (LAN IP)

```bash
./scripts/gen-certs.sh 192.168.1.37
```

This writes `jitsi-certs/cert.crt` + `cert.key` with SANs covering
`localhost`, `127.0.0.1`, and your LAN IP (IP SANs are required — a `CN=*`
wildcard does not cover IP addresses; MediaService bug #8). Then set
`JITSI_PUBLIC_URL=https://192.168.1.37:8443` in `.env` and:

```bash
docker compose up -d --force-recreate jitsi-web nginx
```

### Browser trust (one-time, per browser profile)

Self-signed certs are silently blocked in iframes until trusted:

1. Open `https://<LAN-IP>/` → Advanced → Proceed (trusts the main app)
2. Open `https://<LAN-IP>:8443/` in a **new tab** → Advanced → Proceed (trusts Jitsi)
3. Close the tab — the meeting iframe now works

### Production options

| Option | When | How |
|---|---|---|
| **Let's Encrypt** (recommended) | public domain | point DNS → server, `certbot certonly --standalone -d meet.example.com`, copy `fullchain.pem`→`jitsi-certs/cert.crt`, `privkey.pem`→`cert.key`, cron renewal + `docker compose restart jitsi-web nginx` |
| **Internal CA** | corporate | CSR → CA-signed cert → same locations |
| **Self-signed** | LAN only | fine; 10-year validity; zero external deps |

---

## 2. Firewall ports

| Port | Proto | Purpose |
|---|---|---|
| 80 | TCP | HTTP → 301 to HTTPS |
| 443 | TCP | Main app (SPA + API) |
| 8443 | TCP | Jitsi web (iframe) |
| 10000 | UDP | JVB media traffic |

---

## 3. Resource planning

### Containers

| Container | RAM | CPU | Notes |
|---|---|---|---|
| jitsi-prosody | 128 MB | 0.1 | XMPP signaling, very lightweight |
| jitsi-jicofo | 256 MB | 0.2 | Room focus/manager |
| jitsi-jvb | 512 MB–4 GB | 1–4 | The bottleneck — scales with participants |
| jitsi-web | 128 MB | 0.2 | Nginx serving static JS/CSS |
| backend | 256 MB | 0.5 | FastAPI + SQLite |
| nginx | 128 MB | 0.2 | Reverse proxy + SPA |

### Per participant (JVB)

| Resource | Approx. |
|---|---|
| RAM | 20–40 MB |
| CPU | 0.05–0.1 core |
| Bandwidth (audio) | ~40 Kbps each way |
| Bandwidth (video 720p) | ~2.5 Mbps each way |
| Bandwidth (video 1080p) | ~5 Mbps each way |

The JVB forwards every participant's stream to all others — total server
bandwidth scales ~quadratically with participant count.

### Scenarios

| Meeting size | Server RAM | CPU | Bandwidth |
|---|---|---|---|
| 2–5 participants | 2 GB (4 GB rec.) | 2 cores | 10–25 Mbps |
| 5–15 participants | 4 GB (8 GB rec.) | 4 cores | 50–100 Mbps |
| 15–50 participants | 8 GB (16 GB rec.) | 8 cores | 200–500 Mbps |

Typical VPS (2026): any 4 GB / 2+ core box with unmetered bandwidth —
Hetzner CX22/CX32, DigitalOcean basic, AWS Lightsail 4 GB, Linode 4 GB.
LAN-only: any desktop/server with 4+ GB RAM.

### Real-server checklist

1. Static public IP (required for TLS certs and external access)
2. Firewall: 80/tcp, 443/tcp, 8443/tcp, 10000/udp
3. Docker + Docker Compose installed
4. DNS A record (if using a domain)
5. Let's Encrypt cert (recommended) or self-signed (LAN only)

---

## 4. JWT auth flow (recap)

```
User opens /meeting/:id
  → POST /api/rooms/{id}/token          (backend signs HS256 JWT)
  → iframe: https://<host>:8443/<jitsi_room_id>?jwt=<token>
  → prosody token_verification module:
      signature (shared JWT_APP_SECRET) · audience=jitsi · room claim · expiry
  → user enters the MUC room
```

Token is validated **at join time only** — participants stay in the meeting
after expiry; reconnecting requires a fresh token
(`JITSI_JWT_EXPIRE_MINUTES`, default 1440 = 24h).

---

## 5. Roadmap: per-room JWT keys (adapted from MediaService `REFACTORING/per-room-keys.md`)

Current state: one shared HMAC secret (`JITSI_JWT_SECRET` / `jitsi_config`
table). Limitation: a compromised secret breaks every room, and rotation must
touch DB + prosody simultaneously.

| Phase | Change | Reversible? |
|---|---|---|
| 1 | Add `room_keys` table (room_id, private/public PEM, `kid`, is_active) — no signing change | yes (pure additive) |
| 2 | Generate RSA-2048 key pair per new room; backfill existing rooms | yes |
| 3 | `GET /api/jitsi-keys/{kid}` public endpoint returning the public key PEM | yes (no consumer yet) |
| 4 | Dual signing: `JITSI_JWT_USE_PER_ROOM_KEYS=true` → RS256 with `kid` header; flag off → shared-secret HS256 | yes (feature flag) |
| 5 | Prosody `JWT_ASAP_KEYSERVER=http://backend:8000/api/jitsi-keys/` — validates `kid` against the key server, falls back to shared secret | yes (keep `JWT_APP_SECRET`) |
| 6 | Cleanup: always per-room keys; drop shared secret | after verification |

In this codebase the natural touch points are: `JwtRoomTokenGenerator`
(RS256 + `kid` support), `GenerateJoinTokenUseCase` (flag check), a new
`RoomKeyRepository` port + adapter, and the keyserver route in
`backend/interfaces/routers/`.

---

## 6. Operational notes

- **SQLite in Docker:** the DB file is bind-mounted (`./video_call.db`). Back it
  up by copying the file while the stack is stopped (or use
  `sqlite3 video_call.db ".backup backup.db"` — WAL-safe).
- **Logs:** `docker compose logs -f jitsi-jicofo jitsi-jvb` is where bridge
  problems show up; `docker compose logs -f backend` for API issues.
- **Debugging meetings:** if multi-party calls fail, verify
  `XMPP_INTERNAL_MUC_DOMAIN=internal-muc.meet.jitsi` is present on ALL Jitsi
  containers (MediaService bug #12) and that UDP 10000 is open.
- **Camera/mic blocked?** check the `Permissions-Policy` headers on both nginxes
  and the iframe `allow` attribute (`camera *` syntax, not `camera`).
