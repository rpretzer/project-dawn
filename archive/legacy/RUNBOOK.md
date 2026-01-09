## Project Dawn — Production Runbook

### Day-0 checklist
- Set `DAWN_ENV=prod`
- Set `JWT_SECRET` (and optionally `SESSION_TOKEN_SECRET`)
- Set `CHAT_ALLOWED_ORIGINS` and keep `CHAT_REQUIRE_ORIGIN_ALLOWLIST=true`
- Set `CHAT_REQUIRE_CSRF=true`
- Set `JWT_ACCESS_TTL_SECONDS` (recommended 900) and `JWT_REFRESH_TTL_SECONDS` (recommended 2592000)
- Set `CHAT_REQUIRE_ADMIN_ACTION_TOKEN=true` and `CHAT_ADMIN_ACTION_TOKEN`
- (Optional) Restrict admin: `CHAT_ADMIN_ALLOWED_IPS`, and/or enable mTLS via your proxy (`CHAT_ADMIN_REQUIRE_MTLS=true`)

### Backups / restore (SQLite)
Databases live under `data/` by default:
- `data/users.db`: users + refresh sessions + password reset tokens
- `data/ops.db`: ops log (if enabled)
- other stores (tasks, chat, moderation) are also SQLite-backed

**Backup**
- Stop the service (recommended), then copy the `data/` directory.

**Restore**
- Replace `data/` from backup and restart the service.

### Rotating JWT secrets (no mass logout)
1. Pick a new `JWT_SECRET`
2. Set `JWT_SECRET=<new>` and `JWT_OLD_SECRETS=<old>`
3. Wait at least `JWT_ACCESS_TTL_SECONDS` + `JWT_REFRESH_TTL_SECONDS` overlap window you choose (common: keep old for 30 days)
4. Remove old secrets from `JWT_OLD_SECRETS`

### Revoking access quickly
- **Per-user**: `POST /admin/users/{username}/revoke_sessions` (admin + CSRF + admin action token)
- **Global**: rotate `SESSION_TOKEN_SECRET` (invalidates stored refresh tokens) and rotate `JWT_SECRET` (invalidates access JWTs)

### Common incidents
**Users suddenly appear as guests**
- Access JWT likely expired; ensure client is calling `POST /api/refresh` successfully (requires CSRF header).
- Check cookie `SameSite` and origin allowlist settings.

**Admin endpoints blocked**
- Validate `CHAT_ADMIN_ALLOWED_IPS` includes your admin IP (or your reverse proxy’s IP if you’re not passing real client IPs).
- If `CHAT_ADMIN_REQUIRE_MTLS=true`, ensure your proxy is setting `CHAT_MTLS_VERIFY_HEADER` to `CHAT_MTLS_VERIFY_VALUE`.

