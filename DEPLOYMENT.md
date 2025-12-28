## Deployment (Realtime Chat)

This project’s primary public-facing surface is the realtime chat server (`launch.py --realtime`), which uses WebSockets and HttpOnly cookie auth.

### Recommended production settings
- **`DAWN_ENV=prod`**
- **`JWT_SECRET`**: set a strong secret (sessions will break if it changes)
- **`CHAT_ALLOWED_ORIGINS`**: set to the exact browser origin(s) you will serve from
- **`CHAT_ALLOW_GUESTS=false`** (recommended for public deployments)
- **`CHAT_ADMIN_USERNAMES`**: comma-separated usernames who can moderate/apply patches
- **Patch safety**:
  - keep `DAWN_ALLOW_AGENT_PATCH_APPLY=false`
  - keep `CHAT_PATCH_APPLY_PREFIXES=artifacts/`

### Reverse proxy: Caddy (simple)

`Caddyfile`:

```caddyfile
your.domain {
  encode zstd gzip

  reverse_proxy 127.0.0.1:8000
}
```

### Reverse proxy: Nginx (WebSockets)

```nginx
server {
  listen 80;
  server_name your.domain;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

### Docker

1. Copy `.env.example` → `.env`, set required values (especially `JWT_SECRET` and `CHAT_ALLOWED_ORIGINS`).
2. Run:

```bash
docker compose up --build
```

### Notes on origins/cookies
- If you serve the UI behind a different origin than the API, you must set `CHAT_ALLOWED_ORIGINS` accordingly.
- Cookie behavior is controlled via `CHAT_COOKIE_SAMESITE` (defaults to `Strict` in prod).
- For browser clients in production, the server requires a **double-submit CSRF token** on auth-related POSTs (`/api/login`, `/api/register`, `/api/logout`) when `CHAT_REQUIRE_CSRF=true` (default in prod).
  - Fetch a token from `GET /api/csrf` and include it as `X-CSRF-Token` on those POST requests.
- Sessions use a short-lived **access JWT** (cookie) plus a rotating **refresh session** (cookie). If you set `JWT_ACCESS_TTL_SECONDS` low (recommended), clients should call `POST /api/refresh` (with CSRF header) to renew access.
- To rotate JWT secrets without immediately invalidating all sessions:
  - Set `JWT_SECRET` to the new secret.
  - Put the old secret(s) into `JWT_OLD_SECRETS` for a temporary overlap window.
  - After TTL expiry (see `JWT_TTL_SECONDS`), remove old secrets from `JWT_OLD_SECRETS`.

### Admin surface hardening (optional)
- You can restrict admin HTTP endpoints via:
  - `CHAT_ADMIN_ALLOWED_IPS` (comma-separated IPs/CIDRs)
  - `CHAT_ADMIN_REQUIRE_MTLS=true` (expects proxy-provided verification header; see `CHAT_MTLS_VERIFY_HEADER` / `CHAT_MTLS_VERIFY_VALUE`)
- For risky admin actions (patch apply, moderation commands, admin user changes), enable:
  - `CHAT_REQUIRE_ADMIN_ACTION_TOKEN=true` and set `CHAT_ADMIN_ACTION_TOKEN`
- If you are behind a reverse proxy and want correct client IPs for bans/admin allowlists, enable:
  - `CHAT_TRUST_PROXY_HEADERS=true` and set `CHAT_TRUSTED_PROXY_IPS` to your proxy CIDR(s).

