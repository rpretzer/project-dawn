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

