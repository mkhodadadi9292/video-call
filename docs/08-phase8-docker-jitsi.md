# Phase 8 — Docker Compose: full stack with self-hosted Jitsi

**Status: ✅ complete (config written; start it with `docker compose up -d --build`)**

**Goal:** the 6-container stack — backend, nginx, and the 4 Jitsi containers
(prosody, jicofo, jvb, web) — with BOSH-only signaling and JWT auth.

---

## 1. Container map

```
docker compose (6 containers)
├── backend         (uvicorn, internal :8000)      — FastAPI lite-DDD backend
├── nginx           (host :80 → 301, :443 HTTPS)   — SPA + /api proxy + Permissions-Policy
├── jitsi-web       (host :8443 → container :443)  — Jitsi Meet frontend (TLS)
├── jitsi-prosody   (internal)                     — XMPP signaling + JWT token verification (BOSH)
├── jitsi-jicofo    (internal)                     — room focus/manager
└── jitsi-jvb       (host :10000/udp)              — video bridge (SFU)
```

## 2. Key configuration decisions (carried over from MediaService, verified there)

- **BOSH-only signaling**: `GLOBAL_MODULES=bosh` (prosody), `ENABLE_XMPP_WEBSOCKET=0`,
  `ENABLE_COLIBRI_WEBSOCKET=1` (web). Jitsi's XMPP WebSocket mode is unreliable in
  recent images; BOSH is the stable path.
- **JWT auth**: prosody `ENABLE_AUTH=1`, `AUTH_TYPE=jwt`, `JWT_APP_ID` +
  `JWT_APP_SECRET` must match the backend's `JITSI_JWT_APP_ID` +
  `JITSI_JWT_SECRET` (`.env`).
- **Internal MUC domain**: `XMPP_INTERNAL_MUC_DOMAIN=internal-muc.meet.jitsi` on
  every container — without it jicofo can't find JVB bridges and multi-party
  meetings fail (MediaService bug #12).
- **TLS on 8443**: jitsi-web serves HTTPS on container port 443, mapped to host
  8443. Certs mounted from `./jitsi-certs/` (see phase 9).
- **Permissions-Policy headers**: both nginxes add
  `camera=*, microphone=*, display-capture=*` — required for cross-origin
  iframe `getUserMedia` delegation.
- **Main app over HTTPS too**: nginx redirects :80 → :443 because Chrome blocks
  camera delegation to a cross-origin iframe when the *parent* page is plain
  HTTP (MediaService bug #10).

## 3. Files

### `docker-compose.yml` (full)

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    container_name: vcs-backend
    volumes:
      - ./video_call.db:/app/video_call.db
    environment:
      - DATABASE_URL=sqlite:////app/video_call.db
      - JITSI_JWT_APP_ID=${JITSI_JWT_APP_ID:-video-call-system}
      - JITSI_JWT_SECRET=${JITSI_JWT_SECRET:-change-me-in-production-use-a-long-random-string}
      - JITSI_JWT_EXPIRE_MINUTES=${JITSI_JWT_EXPIRE_MINUTES:-1440}
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: vcs-nginx
    ports:
      - "${HTTP_PORT:-80}:80"
      - "${HTTPS_PORT:-443}:443"
    volumes:
      - ./frontend/dist:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./jitsi-certs:/etc/nginx/certs:ro
    depends_on:
      - backend
    restart: unless-stopped

  # ── Jitsi Meet ──────────────────────────────────────────────────────────
  jitsi-prosody:
    image: jitsi/prosody:latest
    container_name: vcs-jitsi-prosody
    environment:
      - XMPP_DOMAIN=meet.jitsi
      - XMPP_AUTH_DOMAIN=auth.meet.jitsi
      - XMPP_MUC_DOMAIN=muc.meet.jitsi
      - XMPP_INTERNAL_MUC_DOMAIN=internal-muc.meet.jitsi
      - JICOFO_AUTH_USER=focus
      - JICOFO_AUTH_PASSWORD=jitsi
      - JVB_AUTH_USER=jvb
      - JVB_AUTH_PASSWORD=jitsi
      - ENABLE_AUTH=1
      - AUTH_TYPE=jwt
      - JWT_APP_ID=${JITSI_JWT_APP_ID:-video-call-system}
      - JWT_APP_SECRET=${JITSI_JWT_SECRET:-change-me-in-production-use-a-long-random-string}
      - GLOBAL_MODULES=bosh
    restart: unless-stopped

  jitsi-jicofo:
    image: jitsi/jicofo:latest
    container_name: vcs-jitsi-jicofo
    environment:
      - XMPP_SERVER=jitsi-prosody
      - XMPP_DOMAIN=meet.jitsi
      - XMPP_AUTH_DOMAIN=auth.meet.jitsi
      - XMPP_MUC_DOMAIN=muc.meet.jitsi
      - XMPP_INTERNAL_MUC_DOMAIN=internal-muc.meet.jitsi
      - JICOFO_AUTH_USER=focus
      - JICOFO_AUTH_PASSWORD=jitsi
      - JICOFO_AUTH_DOMAIN=auth.meet.jitsi
      - JVB_BREWERY_MUC=jvbbrewery
    depends_on:
      - jitsi-prosody
    restart: unless-stopped

  jitsi-jvb:
    image: jitsi/jvb:latest
    container_name: vcs-jitsi-jvb
    ports:
      - "${JVB_PORT:-10000}:10000/udp"
    environment:
      - XMPP_SERVER=jitsi-prosody
      - XMPP_DOMAIN=meet.jitsi
      - XMPP_AUTH_DOMAIN=auth.meet.jitsi
      - XMPP_INTERNAL_MUC_DOMAIN=internal-muc.meet.jitsi
      - JVB_AUTH_USER=jvb
      - JVB_AUTH_PASSWORD=jitsi
      - JVB_AUTH_DOMAIN=auth.meet.jitsi
      - JVB_BREWERY_MUC=jvbbrewery
    depends_on:
      - jitsi-prosody
    restart: unless-stopped

  jitsi-web:
    image: jitsi/web:latest
    container_name: vcs-jitsi-web
    ports:
      - "${JITSI_WEB_PORT:-8443}:443"
    volumes:
      - ./jitsi-certs:/config/keys:ro
      - ./jitsi-config/meet.conf:/defaults/meet.conf:ro
    environment:
      - PUBLIC_URL=${JITSI_PUBLIC_URL:-https://192.168.1.37:8443}
      - XMPP_SERVER=jitsi-prosody
      - XMPP_DOMAIN=meet.jitsi
      - XMPP_AUTH_DOMAIN=auth.meet.jitsi
      - XMPP_MUC_DOMAIN=muc.meet.jitsi
      - XMPP_BOSH_URL_BASE=http://jitsi-prosody:5280
      - ENABLE_COLIBRI_WEBSOCKET=1
      - ENABLE_XMPP_WEBSOCKET=0
      - ENABLE_SUBDOMAINS=false
    depends_on:
      - jitsi-prosody
      - jitsi-jicofo
      - jitsi-jvb
    restart: unless-stopped
```

### `nginx.conf` (full)

```nginx
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on;

    # HTTP → HTTPS redirect (camera/mic in the Jitsi iframe require the parent
    # page to be a secure context; see docs/09-phase9-deployment-tls.md)
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        http2 on;
        server_name _;

        ssl_certificate     /etc/nginx/certs/cert.crt;
        ssl_certificate_key /etc/nginx/certs/cert.key;

        # Permissions Policy: allow the Jitsi iframe to use camera/mic/display
        add_header Permissions-Policy "camera=*, microphone=*, display-capture=*" always;

        root /usr/share/nginx/html;
        index index.html;

        # SPA fallback
        location / {
            try_files $uri $uri/ /index.html;
        }

        # API proxy
        location /api/ {
            proxy_pass http://backend:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY backend /app/backend

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### `jitsi-config/meet.conf`

Full template in the repo — a copy of MediaService's verified template:
`Permissions-Policy` header, BOSH `/http-bind` proxy to
`{{ .Env.XMPP_BOSH_URL_BASE }}`, colibri websocket location, optional
subdomain routing (disabled via `ENABLE_SUBDOMAINS=false`).

### `.env` (copy from `.env.example`)

```bash
JITSI_JWT_APP_ID=video-call-system
JITSI_JWT_SECRET=change-me-in-production-use-a-long-random-string
JITSI_JWT_EXPIRE_MINUTES=1440
HTTP_PORT=80
HTTPS_PORT=443
JITSI_WEB_PORT=8443
JVB_PORT=10000
JITSI_PUBLIC_URL=https://192.168.1.37:8443
```

Ports are env-overridable — if MediaService's stack occupies 80/443/8443/10000
on the same host, pick free ports here; only one stack can own the defaults.

---

## 4. Startup checklist

```bash
# 1. TLS certs (needs your LAN IP)
./scripts/gen-certs.sh 192.168.1.37     # updates jitsi-certs/

# 2. .env with the same IP + a strong secret
cp .env.example .env && $EDITOR .env

# 3. Frontend build (nginx serves dist/)
cd frontend && npm install && npm run build && cd ..

# 4. Stack
docker compose up -d --build
docker compose ps                        # 6 containers running

# 5. Smoke test — nginx proxies /api/* to the backend without prefix rewrite
#    (all API routes live under /api), so test the API through nginx:
curl -sk https://localhost/api/rooms -o /dev/null -w "%{http_code}\n"   # 200
#    and the backend's own liveness probe inside the network:
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
```

## 5. Verification (full-stack)

1. Open `https://<LAN-IP>/login` in a browser → accept the self-signed warning
2. **First**, trust Jitsi's origin: open `https://<LAN-IP>:8443/` in a NEW TAB,
   accept the warning, close the tab (one-time per browser — see phase 9)
3. Login → create a room → you land in the meeting; the Jitsi iframe loads
4. Second browser/user joins the same room → video + audio connect
5. Chat messages appear for both users within 3s
6. Leave → room count updates; End → room disappears from the list

**Resource estimate:** ~1 GB RAM for the Jitsi containers on top of the
backend/nginx (see phase 9 for the full table).
