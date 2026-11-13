# Auth & Authorization Across Two Microservices

Goal: **video-call-system** and **messenger** as separate services, with **one login** for the user.

## Current state

| Service | Auth today |
|---|---|
| messenger | Has its own auth (login, users, roles) |
| video-call | Stub auth (`stub-token-for-{username}`) — must be replaced |

## The three common approaches

### A. Central Identity Provider (industry standard)

A dedicated auth service (Keycloak, Auth0, Ory) issues tokens. Both services verify the same token.

- Best long-term; zero auth code in each service
- Extra service to run and maintain; overkill for 2 services

### B. Messenger is the auth issuer (pragmatic)

Keep messenger's auth. Messenger signs a JWT; video-call only **verifies** it.

- No new service, minimal change
- video-call depends on messenger only for the public key (fetch once, cache)

### C. Gateway does auth (transparent)

nginx/Kong/Traefik validates the token before forwarding, passes user info as headers. Services trust the gateway.

- Services get simpler; gateway becomes a critical piece
- Pairs well with A or B

## Recommendation

**Start with B, move to A when a third service appears.**

- Messenger keeps login/registration as-is.
- Switch its JWT signing from HS256 (shared secret) to **RS256** (private/public key pair). video-call verifies with the **public key only** — no secret sharing between services.
- (Jitsi keeps its own HS256 JWT — prosody requires it; that is internal to video-call and unrelated.)

```
Browser ──login──▶ messenger ──issues RS256 JWT──▶ Browser
Browser ──JWT──▶ video-call API ──verify with public key──▶ allow
```

## What changes in video-call

1. **Delete the stub auth.** Replace with a JWT verifier middleware (PyJWT is already a dependency):
   - verify signature with messenger's public key
   - check `exp` and `iss`
2. **Keep the auto-create-user behavior**: first valid token → create local user row (id, username, role). Good pattern, keep it.
3. **Roles**: read role from the token claim (or map local role on first login, like `admin` today). Room-level authorization stays local: room owner, participants, join/end rules — all in video-call's domain.
4. **Token refresh**: short-lived access token (e.g. 15 min) + refresh via messenger; or just accept longer expiry for now (current system already uses 24h for Jitsi).

## What stays local to each service

| Concern | Owner |
|---|---|
| Identity (login, password, profile) | messenger |
| Token issuing | messenger |
| Token verification | both (public key) |
| Roles / permissions per feature | each service, locally |
| Rooms, meetings, chat state | video-call only |

## Migration steps (simple order)

1. messenger: add RS256 key pair, sign tokens with it
2. video-call: add public-key verification middleware, remove stub
3. test: login in messenger → use same token against video-call API
4. later (optional): extract to Keycloak when service count grows
