"""
Real-time chat server for Project Dawn.

Goals:
- Multi-human and multi-agent chat in real-time (WebSocket).
- Persist room history to SQLite.
- Basic auth with JWT (UserDatabase).

This intentionally avoids the legacy polling BBS dashboard and provides
an async-first, production-oriented baseline using aiohttp.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque, defaultdict

import jwt
from aiohttp import web, WSMsgType

from .user_database import UserDatabase
from .chat_store import ChatStore
from .moderation_store import ModerationStore
from core.orchestrator import AgentOrchestrator
from core.task_manager import TaskStore

logger = logging.getLogger(__name__)


DEFAULT_ROOM = "lobby"
TOKEN_COOKIE_NAME = os.getenv("CHAT_TOKEN_COOKIE", "dawn_token")
ENV = (os.getenv("DAWN_ENV") or os.getenv("APP_ENV") or "dev").strip().lower()


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if secret:
        return secret
    if ENV == "prod":
        raise RuntimeError("JWT_SECRET must be set in production mode (DAWN_ENV=prod).")
    # Dev fallback. For public deployments, JWT_SECRET should be set.
    logger.warning("JWT_SECRET not set; using ephemeral secret (sessions will not survive restart).")
    return secrets.token_urlsafe(48)


JWT_SECRET = _jwt_secret()
JWT_ALG = "HS256"


@dataclass
class ClientSession:
    ws: web.WebSocketResponse
    room: str
    sender_type: str  # "human" | "guest"
    sender_id: Optional[str]  # user_id as str
    sender_name: str  # nickname / guest name
    ip: str
    is_admin: bool = False


def _json_response(payload: Dict[str, Any], *, status: int = 200) -> web.Response:
    return web.json_response(payload, status=status, dumps=lambda o: json.dumps(o, ensure_ascii=False))


def _issue_token(*, user_id: int, username: str, nickname: str) -> str:
    now = int(time.time())
    exp = now + int(os.getenv("JWT_TTL_SECONDS", "86400"))  # 24h default
    return jwt.encode(
        {"sub": str(user_id), "username": username, "nickname": nickname, "iat": now, "exp": exp},
        JWT_SECRET,
        algorithm=JWT_ALG,
    )


def _decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        return None


def _allowed_origins() -> Optional[Set[str]]:
    raw = (os.getenv("CHAT_ALLOWED_ORIGINS") or "").strip()
    if not raw:
        return None
    return {o.strip() for o in raw.split(",") if o.strip()}


def _sanitize_room(room: Optional[str]) -> str:
    room = (room or DEFAULT_ROOM).strip().lower()
    if not room:
        return DEFAULT_ROOM
    # Basic allowlist
    room = "".join(ch for ch in room if ch.isalnum() or ch in ("-", "_"))[:48]
    return room or DEFAULT_ROOM


def _truncate_message(text: str, limit: int = 4000) -> str:
    text = (text or "").strip()
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def _is_command(text: str) -> bool:
    return text.strip().startswith("/")


class RealtimeChatServer:
    def __init__(self, *, consciousnesses: List[Any], swarm: Any = None):
        self.consciousnesses = consciousnesses
        self.swarm = swarm

        self.user_db = UserDatabase()
        self.chat_store = ChatStore()
        self.task_store = TaskStore()
        self.orchestrator = AgentOrchestrator(agents=self.consciousnesses, swarm=self.swarm, task_store=self.task_store)
        self.moderation = ModerationStore()

        self._clients: Set[web.WebSocketResponse] = set()
        self._sessions: Dict[web.WebSocketResponse, ClientSession] = {}
        self._rooms: Dict[str, Set[web.WebSocketResponse]] = {}

        # Throttle LLM fanout
        self.max_agent_responses_per_message = int(os.getenv("MAX_AGENT_RESPONSES_PER_MESSAGE", "3"))
        self.agent_reply_timeout_seconds = float(os.getenv("AGENT_REPLY_TIMEOUT_SECONDS", "25"))

        # Rate limits (public-safe defaults)
        self.max_msgs_per_10s_human = int(os.getenv("CHAT_MAX_MSGS_PER_10S_HUMAN", "12"))
        self.max_msgs_per_10s_guest = int(os.getenv("CHAT_MAX_MSGS_PER_10S_GUEST", "6"))
        self._msg_rate: Dict[str, deque] = defaultdict(lambda: deque(maxlen=64))  # key -> timestamps

        # Simple IP rate limit for auth endpoints (best-effort)
        self.max_auth_per_minute = int(os.getenv("CHAT_MAX_AUTH_PER_MINUTE", "10"))
        self._auth_rate: Dict[str, deque] = defaultdict(lambda: deque(maxlen=64))  # ip -> timestamps

        # Policy defaults
        self.allow_guests_default = os.getenv("CHAT_ALLOW_GUESTS", "true" if ENV != "prod" else "false").lower() == "true"
        self.admin_usernames = {u.strip().lower() for u in (os.getenv("CHAT_ADMIN_USERNAMES") or "").split(",") if u.strip()}

        # Start orchestrator workers and wire event sink to broadcast to rooms
        asyncio.create_task(self.orchestrator.start())
        self.orchestrator.set_event_sink(self._orchestrator_event_sink)
        self._origins = _allowed_origins()

    def _check_origin(self, request: web.Request) -> bool:
        # In dev, allow everything.
        if ENV != "prod":
            return True
        origin = request.headers.get("Origin")
        if not origin:
            return True  # non-browser clients
        if not self._origins:
            return True  # no allowlist configured
        return origin in self._origins

    def _set_auth_cookie(self, resp: web.Response, token: str, request: web.Request) -> None:
        ttl = int(os.getenv("JWT_TTL_SECONDS", "86400"))
        secure = (ENV == "prod") or (request.scheme == "https")
        # HttpOnly cookie so it is not accessible to JS; websocket can still send it.
        resp.set_cookie(
            TOKEN_COOKIE_NAME,
            token,
            max_age=ttl,
            httponly=True,
            secure=secure,
            samesite="Lax",
            path="/",
        )

    async def _orchestrator_event_sink(self, event: Dict[str, Any]) -> None:
        """
        Convert orchestrator events into room messages and/or websocket events.

        For now we broadcast task status updates to the relevant room as system lines.
        """
        try:
            if event.get("type") != "task":
                return
            ev = str(event.get("event"))
            if ev in ("started", "completed"):
                task = event.get("task") or {}
                room = str(task.get("room") or DEFAULT_ROOM)
                task_id = str(task.get("id") or "")
                status = str(task.get("status") or ev)
                assigned_to = str(task.get("assigned_to") or "")
                title = str(task.get("title") or "")
                await self._system(room, f"[task {task_id}] {status} — {title} (agent: {assigned_to})")
                return
            if ev == "progress":
                task_id = str(event.get("task_id") or "")
                step = event.get("step")
                do = str(event.get("do") or "")
                task = self.task_store.get_task(task_id) if task_id else None
                room = task.room if task else DEFAULT_ROOM
                await self._system(room, f"[task {task_id}] step {step}: {do}")
                return
            if ev == "tool":
                task_id = str(event.get("task_id") or "")
                name = str(event.get("name") or "")
                task = self.task_store.get_task(task_id) if task_id else None
                room = task.room if task else DEFAULT_ROOM
                await self._system(room, f"[task {task_id}] tool: {name}")
                return
        except Exception:
            return

    def _room_sockets(self, room: str) -> Set[web.WebSocketResponse]:
        if room not in self._rooms:
            self._rooms[room] = set()
        return self._rooms[room]

    async def _broadcast(self, room: str, payload: Dict[str, Any]) -> None:
        room = _sanitize_room(room)
        data = json.dumps(payload, ensure_ascii=False)
        dead: List[web.WebSocketResponse] = []
        for ws in list(self._room_sockets(room)):
            try:
                await ws.send_str(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self._disconnect(ws)

    async def _send(self, ws: web.WebSocketResponse, payload: Dict[str, Any]) -> None:
        try:
            await ws.send_str(json.dumps(payload, ensure_ascii=False))
        except Exception:
            await self._disconnect(ws)

    async def _disconnect(self, ws: web.WebSocketResponse) -> None:
        if ws in self._clients:
            self._clients.discard(ws)

        sess = self._sessions.pop(ws, None)
        if sess:
            room_socks = self._room_sockets(sess.room)
            room_socks.discard(ws)
            await self._broadcast(
                sess.room,
                {
                    "type": "presence",
                    "event": "leave",
                    "room": sess.room,
                    "who": {"sender_type": sess.sender_type, "sender_id": sess.sender_id, "sender_name": sess.sender_name},
                    "ts": time.time(),
                },
            )

        try:
            if not ws.closed:
                await ws.close()
        except Exception:
            pass

    def _current_presence(self, room: str) -> List[Dict[str, Any]]:
        room = _sanitize_room(room)
        pres = []
        for ws in self._room_sockets(room):
            sess = self._sessions.get(ws)
            if not sess:
                continue
            pres.append(
                {"sender_type": sess.sender_type, "sender_id": sess.sender_id, "sender_name": sess.sender_name}
            )
        # Add agents as “present” in all rooms (simple model for now).
        for c in self.consciousnesses:
            pres.append({"sender_type": "agent", "sender_id": getattr(c, "id", "agent"), "sender_name": getattr(c, "name", getattr(c, "id", "Agent"))})
        return pres

    async def http_index(self, request: web.Request) -> web.Response:
        html = _INDEX_HTML
        return web.Response(text=html, content_type="text/html; charset=utf-8")

    async def http_health(self, request: web.Request) -> web.Response:
        return _json_response({"ok": True, "ts": time.time()})

    def _check_auth_rate_limit(self, ip: str) -> bool:
        now = time.time()
        q = self._auth_rate[ip]
        while q and q[0] < now - 60:
            q.popleft()
        if len(q) >= self.max_auth_per_minute:
            return False
        q.append(now)
        return True

    async def http_register(self, request: web.Request) -> web.Response:
        if not self._check_origin(request):
            return _json_response({"success": False, "error": "origin_not_allowed"}, status=403)
        ip = request.remote or "unknown"
        if not self._check_auth_rate_limit(ip):
            return _json_response({"success": False, "error": "rate_limited"}, status=429)
        try:
            data = await request.json()
        except Exception:
            return _json_response({"success": False, "error": "invalid_json"}, status=400)

        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        nickname = (data.get("nickname") or username).strip()

        if not username or not password:
            return _json_response({"success": False, "error": "username_and_password_required"}, status=400)
        if len(password) < 8:
            return _json_response({"success": False, "error": "password_too_short"}, status=400)
        if len(username) < 3 or len(username) > 20:
            return _json_response({"success": False, "error": "username_length_invalid"}, status=400)
        if len(nickname) < 1 or len(nickname) > 30:
            return _json_response({"success": False, "error": "nickname_length_invalid"}, status=400)

        # Hashing is handled by the caller in legacy dashboard; here we do it directly.
        import bcrypt

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        ok, user_id, err = self.user_db.create_user(
            username=username, password_hash=password_hash, nickname=nickname, email=None
        )
        if not ok or not user_id:
            return _json_response({"success": False, "error": err or "registration_failed"}, status=400)

        token = _issue_token(user_id=user_id, username=username.strip().lower(), nickname=nickname)
        resp = _json_response({"success": True, "token": token, "user": {"id": user_id, "username": username, "nickname": nickname}})
        self._set_auth_cookie(resp, token, request)
        return resp

    async def http_login(self, request: web.Request) -> web.Response:
        if not self._check_origin(request):
            return _json_response({"success": False, "error": "origin_not_allowed"}, status=403)
        ip = request.remote or "unknown"
        if not self._check_auth_rate_limit(ip):
            return _json_response({"success": False, "error": "rate_limited"}, status=429)
        try:
            data = await request.json()
        except Exception:
            return _json_response({"success": False, "error": "invalid_json"}, status=400)

        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        if not username or not password:
            return _json_response({"success": False, "error": "username_and_password_required"}, status=400)

        user = self.user_db.get_user_by_username(username)
        if not user:
            return _json_response({"success": False, "error": "invalid_credentials"}, status=401)

        import bcrypt

        try:
            ok = bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8"))
        except Exception:
            ok = False
        if not ok:
            return _json_response({"success": False, "error": "invalid_credentials"}, status=401)

        self.user_db.update_last_login(int(user["id"]))
        nickname = user.get("nickname") or user["username"]
        token = _issue_token(user_id=int(user["id"]), username=user["username"], nickname=nickname)
        resp = _json_response({"success": True, "token": token, "user": {"id": user["id"], "username": user["username"], "nickname": nickname}})
        self._set_auth_cookie(resp, token, request)
        return resp

    async def http_logout(self, request: web.Request) -> web.Response:
        if not self._check_origin(request):
            return _json_response({"success": False, "error": "origin_not_allowed"}, status=403)
        resp = _json_response({"success": True})
        resp.del_cookie(TOKEN_COOKIE_NAME, path="/")
        return resp

    async def http_me(self, request: web.Request) -> web.Response:
        if not self._check_origin(request):
            return _json_response({"success": False, "error": "origin_not_allowed"}, status=403)
        token = request.cookies.get(TOKEN_COOKIE_NAME)
        claims = _decode_token(token) if token else None
        if not claims:
            return _json_response({"success": True, "authenticated": False})
        username = str(claims.get("username") or "").lower()
        return _json_response(
            {
                "success": True,
                "authenticated": True,
                "user": {
                    "id": str(claims.get("sub")),
                    "username": username,
                    "nickname": str(claims.get("nickname") or username),
                },
                "is_admin": bool(username and username in self.admin_usernames),
            }
        )

    async def ws_handler(self, request: web.Request) -> web.StreamResponse:
        if not self._check_origin(request):
            raise web.HTTPForbidden(text="origin_not_allowed")
        ws = web.WebSocketResponse(heartbeat=20, receive_timeout=60)
        await ws.prepare(request)

        self._clients.add(ws)

        # Identify user:
        # - Prefer HttpOnly cookie (safe for public deployments)
        # - Accept query param only in non-prod for backward compatibility
        token = request.cookies.get(TOKEN_COOKIE_NAME)
        if not token and ENV != "prod":
            token = request.query.get("token")
        claims = _decode_token(token) if token else None

        ip = request.remote or "unknown"
        if claims:
            sender_type = "human"
            sender_id = str(claims.get("sub"))
            sender_name = str(claims.get("nickname") or claims.get("username") or f"User{sender_id}")
            username = str(claims.get("username") or "").lower()
            is_admin = bool(username and username in self.admin_usernames)
        else:
            sender_type = "guest"
            sender_id = None
            sender_name = f"Guest{secrets.token_hex(3)}"
            is_admin = False

        # Ban checks
        banned, reason = self.moderation.is_banned(user_id=sender_id, ip=ip)
        if banned:
            raise web.HTTPForbidden(text=f"banned:{reason or 'banned'}")

        room = _sanitize_room(request.query.get("room"))
        # Room policy
        room_settings = self.moderation.get_room_settings(room)
        allow_guests = room_settings["allow_guests"] if room_settings else self.allow_guests_default
        if sender_type == "guest" and not allow_guests:
            raise web.HTTPUnauthorized(text="login_required")

        sess = ClientSession(ws=ws, room=room, sender_type=sender_type, sender_id=sender_id, sender_name=sender_name, ip=ip, is_admin=is_admin)
        self._sessions[ws] = sess
        self._room_sockets(room).add(ws)

        # Send bootstrap: you, presence, history, agents
        await self._send(
            ws,
            {
                "type": "hello",
                "you": {"sender_type": sender_type, "sender_id": sender_id, "sender_name": sender_name},
                "room": room,
                "is_admin": is_admin,
                "agents": [
                    {"id": getattr(c, "id", "agent"), "name": getattr(c, "name", getattr(c, "id", "Agent"))}
                    for c in self.consciousnesses
                ],
                "presence": self._current_presence(room),
                "history": [m.to_dict() for m in self.chat_store.get_recent(room=room, limit=200)],
                "ts": time.time(),
            },
        )

        await self._broadcast(
            room,
            {
                "type": "presence",
                "event": "join",
                "room": room,
                "who": {"sender_type": sender_type, "sender_id": sender_id, "sender_name": sender_name},
                "ts": time.time(),
            },
        )

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_ws_text(ws, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    break
        except Exception:
            pass
        finally:
            await self._disconnect(ws)
        return ws

    async def _handle_ws_text(self, ws: web.WebSocketResponse, data: str) -> None:
        sess = self._sessions.get(ws)
        if not sess:
            return

        try:
            payload = json.loads(data)
        except Exception:
            await self._send(ws, {"type": "error", "error": "invalid_json"})
            return

        msg_type = payload.get("type")
        if msg_type == "chat":
            content = _truncate_message(str(payload.get("content", "")))
            room = _sanitize_room(payload.get("room") or sess.room)
            await self._handle_chat(sess, room, content)
            return

        if msg_type == "set_room":
            room = _sanitize_room(payload.get("room"))
            await self._move_room(sess, room)
            return

        await self._send(ws, {"type": "error", "error": "unknown_message_type"})

    async def _move_room(self, sess: ClientSession, room: str) -> None:
        old = sess.room
        if old == room:
            return
        room_settings = self.moderation.get_room_settings(room)
        allow_guests = room_settings["allow_guests"] if room_settings else self.allow_guests_default
        if sess.sender_type == "guest" and not allow_guests:
            await self._send(sess.ws, {"type": "error", "error": "login_required_for_room"})
            return
        self._room_sockets(old).discard(sess.ws)
        self._room_sockets(room).add(sess.ws)
        sess.room = room
        await self._send(sess.ws, {"type": "room", "room": room, "presence": self._current_presence(room)})

    async def _handle_chat(self, sess: ClientSession, room: str, content: str) -> None:
        if not content:
            return

        # Per-sender rate limit
        key = sess.sender_id if sess.sender_id else f"guest:{sess.sender_name}"
        now = time.time()
        q = self._msg_rate[key]
        while q and q[0] < now - 10:
            q.popleft()
        limit = self.max_msgs_per_10s_human if sess.sender_type == "human" else self.max_msgs_per_10s_guest
        if len(q) >= limit:
            await self._send(sess.ws, {"type": "error", "error": "rate_limited"})
            return
        q.append(now)

        ts = time.time()
        if _is_command(content):
            await self._handle_command(sess, room, content)
            return

        # Room read-only
        room_settings = self.moderation.get_room_settings(room)
        if room_settings.get("read_only") and not sess.is_admin:
            await self._send(sess.ws, {"type": "error", "error": "room_read_only"})
            return

        # Muted
        muted, _ = self.moderation.is_muted(user_id=sess.sender_id, room=room)
        if muted and not sess.is_admin:
            await self._send(sess.ws, {"type": "error", "error": "muted"})
            return

        # Store + broadcast human message
        msg = self.chat_store.append_message(
            room=room,
            sender_type=sess.sender_type,
            sender_id=sess.sender_id,
            sender_name=sess.sender_name,
            content=content,
            created_at_ts=ts,
        )
        await self._broadcast(room, {"type": "message", "message": msg.to_dict()})

    async def _handle_command(self, sess: ClientSession, room: str, content: str) -> None:
        parts = content.strip().split()
        cmd = parts[0].lower()

        if cmd in ("/help", "/?"):
            await self._system(
                room,
                "Commands: /help, /who, /join <room>, /agents, /ask <agent|all> <msg>, /spawn [n], /task <agent|all> <work>, /tasks"
                + (" | Admin: /kick, /mute, /ban, /room" if sess.is_admin else ""),
            )
            return

        if cmd == "/who":
            pres = self._current_presence(room)
            await self._send(sess.ws, {"type": "who", "room": room, "presence": pres})
            return

        if cmd == "/join":
            if len(parts) < 2:
                await self._system(room, "Usage: /join <room>")
                return
            new_room = _sanitize_room(parts[1])
            await self._move_room(sess, new_room)
            await self._system(new_room, f"{sess.sender_name} joined {new_room}")
            return

        # Admin moderation commands
        if cmd == "/kick":
            if not sess.is_admin:
                await self._system(room, "Permission denied.")
                return
            if len(parts) < 2:
                await self._system(room, "Usage: /kick <nickname>")
                return
            target = parts[1].strip().lower()
            self.moderation.audit(
                action="kick",
                actor_user_id=sess.sender_id,
                actor_name=sess.sender_name,
                actor_ip=sess.ip,
                room=room,
                target=target,
                reason=None,
            )
            await self._kick_by_nick(room, target)
            return

        if cmd == "/mute":
            if not sess.is_admin:
                await self._system(room, "Permission denied.")
                return
            if len(parts) < 2:
                await self._system(room, "Usage: /mute <nickname> [seconds] [reason...]")
                return
            target = parts[1].strip().lower()
            seconds = None
            reason = "muted"
            if len(parts) >= 3:
                try:
                    seconds = int(parts[2])
                except Exception:
                    seconds = None
            if len(parts) >= 4:
                reason = " ".join(parts[3:])
            ok = await self._mute_by_nick(room, target, seconds, reason)
            if ok:
                self.moderation.audit(
                    action="mute",
                    actor_user_id=sess.sender_id,
                    actor_name=sess.sender_name,
                    actor_ip=sess.ip,
                    room=room,
                    target=target,
                    reason=reason,
                )
                await self._system(room, f"Muted {target}.")
            else:
                await self._system(room, f"Could not mute {target}.")
            return

        if cmd == "/ban":
            if not sess.is_admin:
                await self._system(room, "Permission denied.")
                return
            if len(parts) < 3:
                await self._system(room, "Usage: /ban <user|ip> <value> [seconds] [reason...]")
                return
            kind = parts[1].strip().lower()
            value = parts[2].strip()
            seconds = None
            reason = "banned"
            if len(parts) >= 4:
                try:
                    seconds = int(parts[3])
                except Exception:
                    seconds = None
            if len(parts) >= 5:
                reason = " ".join(parts[4:])
            if kind not in ("user", "ip"):
                await self._system(room, "kind must be 'user' or 'ip'")
                return
            self.moderation.set_ban(kind=kind, value=value, reason=reason, duration_seconds=seconds)
            self.moderation.audit(
                action="ban",
                actor_user_id=sess.sender_id,
                actor_name=sess.sender_name,
                actor_ip=sess.ip,
                room=room,
                target=f"{kind}:{value}",
                reason=reason,
            )
            await self._system(room, f"Banned {kind}:{value}.")
            return

        if cmd == "/room":
            if not sess.is_admin:
                await self._system(room, "Permission denied.")
                return
            # /room read_only on|off ; /room allow_guests on|off
            if len(parts) < 3:
                await self._system(room, "Usage: /room <read_only|allow_guests> <on|off>")
                return
            key = parts[1].strip().lower()
            val = parts[2].strip().lower()
            on = val in ("on", "true", "1", "yes")
            if key == "read_only":
                self.moderation.set_room_settings(room, read_only=on)
            elif key == "allow_guests":
                self.moderation.set_room_settings(room, allow_guests=on)
            else:
                await self._system(room, "Unknown room setting.")
                return
            self.moderation.audit(
                action="room_setting",
                actor_user_id=sess.sender_id,
                actor_name=sess.sender_name,
                actor_ip=sess.ip,
                room=room,
                target=f"{key}={on}",
                reason=None,
            )
            await self._system(room, f"Room setting updated: {key}={on}")
            return

        if cmd == "/agents":
            await self._send(
                sess.ws,
                {
                    "type": "agents",
                    "agents": [
                        {"id": getattr(c, "id", "agent"), "name": getattr(c, "name", getattr(c, "id", "Agent")), "active": getattr(c, "active", True)}
                        for c in self.consciousnesses
                    ],
                },
            )
            return

        if cmd == "/spawn":
            if not self.swarm:
                await self._system(room, "Spawn unavailable (no swarm attached).")
                return
            n = 1
            if len(parts) >= 2:
                try:
                    n = max(1, min(int(parts[1]), 10))
                except Exception:
                    n = 1
            await self._system(room, f"Spawning {n} agent(s)…")
            for _ in range(n):
                await self._spawn_agent(room)
            return

        if cmd == "/tasks":
            tasks = [t for t in self.orchestrator.task_store.list_recent(room=room, limit=20) if t]
            if not tasks:
                await self._system(room, "No tasks yet.")
                return
            lines = []
            for t in tasks:
                lines.append(f"{t.id} [{t.status}] {t.title} (agent: {t.assigned_to})")
            await self._system(room, "Recent tasks:\n" + "\n".join(lines))
            return

        if cmd == "/task":
            if len(parts) < 3:
                await self._system(room, "Usage: /task <agent|all> <work description>")
                return
            target = parts[1]
            work = _truncate_message(" ".join(parts[2:]), limit=8000)
            await self._create_tasks(room, sess, target, work)
            return

        if cmd == "/ask":
            if len(parts) < 3:
                await self._system(room, "Usage: /ask <agent|all> <message>")
                return
            target = parts[1]
            question = _truncate_message(" ".join(parts[2:]), limit=6000)
            await self._fanout_to_agents(room, sess, target, question)
            return

        await self._system(room, f"Unknown command: {cmd}. Try /help.")

    async def _kick_by_nick(self, room: str, nick_lower: str) -> None:
        kicked = 0
        for ws, sess in list(self._sessions.items()):
            if sess.room != room:
                continue
            if sess.sender_name.lower() == nick_lower:
                await self._send(ws, {"type": "error", "error": "kicked"})
                await self._disconnect(ws)
                kicked += 1
        await self._system(room, f"Kicked {nick_lower} ({kicked}).")

    async def _mute_by_nick(self, room: str, nick_lower: str, seconds: Optional[int], reason: str) -> bool:
        for sess in list(self._sessions.values()):
            if sess.room != room:
                continue
            if sess.sender_name.lower() == nick_lower and sess.sender_id:
                self.moderation.set_mute(user_id=sess.sender_id, room=room, reason=reason, duration_seconds=seconds)
                return True
        return False

    async def _create_tasks(self, room: str, sess: ClientSession, target: str, work: str) -> None:
        agents = self._select_agents(target)
        if not agents:
            await self._system(room, f"No matching agent for '{target}'. Try /agents.")
            return

        created: List[str] = []
        # If target is "all", create tasks for each agent but cap to avoid stampede.
        if target.lower() == "all":
            agents = agents[: max(1, self.max_agent_responses_per_message)]

        for agent in agents:
            agent_id = str(getattr(agent, "id", "agent"))
            title = work.splitlines()[0][:80]
            t = await self.orchestrator.submit_task(
                room=room,
                created_by=str(sess.sender_id or "guest"),
                requested_by_name=str(sess.sender_name),
                assigned_to=agent_id,
                title=title,
                prompt=work,
                parent_task_id=None,
            )
            created.append(t.id)

        await self._system(room, f"Queued task(s): {', '.join(created)}")

    async def _system(self, room: str, text: str) -> None:
        ts = time.time()
        msg = self.chat_store.append_message(
            room=room,
            sender_type="system",
            sender_id=None,
            sender_name="system",
            content=_truncate_message(text, limit=2000),
            created_at_ts=ts,
        )
        await self._broadcast(room, {"type": "message", "message": msg.to_dict()})

    async def _spawn_agent(self, room: str) -> None:
        try:
            # Use swarm’s create_consciousness API (existing).
            from core.real_consciousness import ConsciousnessConfig
            from systems.intelligence.llm_integration import LLMConfig

            llm_config = LLMConfig.from_env()
            new_id = f"consciousness_{len(self.consciousnesses):03d}"
            config = ConsciousnessConfig(
                id=new_id,
                personality_seed=len(self.consciousnesses),
                llm_config=llm_config,
                enable_blockchain=os.getenv("ENABLE_BLOCKCHAIN", "false").lower() == "true",
                enable_p2p=os.getenv("ENABLE_P2P", "false").lower() == "true",
                enable_revenue=os.getenv("ENABLE_REVENUE", "false").lower() == "true",
            )
            new_agent = await self.swarm.create_consciousness(config)
            self.consciousnesses.append(new_agent)
            await self._system(room, f"Spawned agent: {getattr(new_agent, 'name', new_id)} ({new_id})")
        except Exception as e:
            await self._system(room, f"Spawn failed: {e}")

    def _select_agents(self, target: str) -> List[Any]:
        target = target.strip()
        if target.lower() == "all":
            return list(self.consciousnesses)

        # Match by id or name prefix
        matches = []
        t = target.lower()
        for c in self.consciousnesses:
            cid = str(getattr(c, "id", "")).lower()
            name = str(getattr(c, "name", "")).lower()
            if cid == t or name == t or cid.startswith(t) or name.startswith(t):
                matches.append(c)
        return matches

    async def _fanout_to_agents(self, room: str, sess: ClientSession, target: str, question: str) -> None:
        agents = self._select_agents(target)
        if not agents:
            await self._system(room, f"No matching agent for '{target}'. Try /agents.")
            return

        # Safety: cap responses unless explicitly asking all (and even then cap).
        if target.lower() == "all":
            agents = agents[: max(1, self.max_agent_responses_per_message)]

        # Store the /ask as a regular message (human intent) for shared context.
        ts = time.time()
        ask_line = f"[ask {target}] {question}"
        msg = self.chat_store.append_message(
            room=room,
            sender_type=sess.sender_type,
            sender_id=sess.sender_id,
            sender_name=sess.sender_name,
            content=ask_line,
            created_at_ts=ts,
        )
        await self._broadcast(room, {"type": "message", "message": msg.to_dict()})

        async def ask_one(agent: Any) -> None:
            agent_id = getattr(agent, "id", "agent")
            agent_name = getattr(agent, "name", str(agent_id))
            try:
                reply = await asyncio.wait_for(agent.chat(question, user_id=str(sess.sender_id or "guest")), timeout=self.agent_reply_timeout_seconds)
            except asyncio.TimeoutError:
                reply = "Timed out while thinking (LLM slow/unreachable)."
            except Exception as e:
                reply = f"Error while responding: {e}"

            m = self.chat_store.append_message(
                room=room,
                sender_type="agent",
                sender_id=str(agent_id),
                sender_name=str(agent_name),
                content=_truncate_message(str(reply), limit=8000),
                created_at_ts=time.time(),
            )
            await self._broadcast(room, {"type": "message", "message": m.to_dict()})

        # Run in parallel, but bounded
        await asyncio.gather(*(ask_one(a) for a in agents))


def create_app(*, consciousnesses: List[Any], swarm: Any = None) -> web.Application:
    server = RealtimeChatServer(consciousnesses=consciousnesses, swarm=swarm)
    app = web.Application(client_max_size=2 * 1024 * 1024)
    app["server"] = server

    app.router.add_get("/", server.http_index)
    app.router.add_get("/healthz", server.http_health)

    app.router.add_post("/api/register", server.http_register)
    app.router.add_post("/api/login", server.http_login)
    app.router.add_post("/api/logout", server.http_logout)
    app.router.add_get("/api/me", server.http_me)
    app.router.add_get("/ws", server.ws_handler)

    async def _on_cleanup(app_: web.Application) -> None:
        # Stop orchestrator workers cleanly
        srv: RealtimeChatServer = app_["server"]
        try:
            await srv.orchestrator.stop()
        except Exception:
            pass

    app.on_cleanup.append(_on_cleanup)

    return app


async def run_realtime_server(consciousnesses: List[Any], port: int = 8000, swarm: Any = None) -> web.AppRunner:
    """Start the aiohttp server and return its runner."""
    host = os.getenv("CHAT_HOST", "0.0.0.0")
    app = create_app(consciousnesses=consciousnesses, swarm=swarm)
    runner = web.AppRunner(app, access_log=logger)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=int(port))
    await site.start()
    logger.info(f"Realtime chat server listening on http://{host}:{port} (WS: /ws)")
    if ENV == "prod":
        logger.info("Realtime chat running in PROD mode (DAWN_ENV=prod)")
    return runner


_INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Project Dawn — Realtime Chat</title>
  <style>
    :root { color-scheme: dark; }
    body { margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; background:#000; color:#0f0; }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 12px; display:flex; flex-direction:column; height: 100vh; box-sizing:border-box; }
    header { display:flex; justify-content:space-between; align-items:center; gap:12px; border:1px solid #0f0; padding:10px; background:#001100; }
    header .title { font-weight:700; letter-spacing:0.08em; text-transform:uppercase; }
    header .meta { font-size: 12px; color:#9f9; display:flex; gap:12px; flex-wrap:wrap; justify-content:flex-end; }
    main { display:grid; grid-template-columns: 1fr 260px; gap: 12px; flex:1; min-height:0; margin-top: 12px; }
    .panel { border:1px solid #0f0; background:#000; min-height:0; }
    #log { padding:10px; overflow:auto; height:100%; }
    #side { padding:10px; overflow:auto; }
    .line { margin: 0 0 6px 0; white-space: pre-wrap; word-break: break-word; }
    .ts { color:#666; font-size:11px; }
    .who { color:#fff; }
    .system { color:#ff0; }
    .guest { color:#0ff; }
    .agent { color:#0f0; }
    .input { margin-top: 12px; display:flex; gap:10px; }
    input, button { font: inherit; }
    #msg { flex:1; padding:10px; border:1px solid #0f0; background:#000; color:#0f0; }
    button { padding:10px 12px; border:1px solid #0f0; background:#001100; color:#0f0; cursor:pointer; }
    button:hover { border-color:#0ff; color:#0ff; }
    .auth { display:flex; gap:8px; }
    .auth input { width: 140px; padding:6px; border:1px solid #0f0; background:#000; color:#0f0; }
    .hint { color:#6f6; font-size: 12px; margin-top: 6px; }
    .sep { border-top:1px solid #0f0; margin: 10px 0; }
    a { color:#0ff; }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="title">Project Dawn — Realtime Chat</div>
      <div class="meta">
        <div>room: <span id="room">lobby</span></div>
        <div>you: <span id="you">guest</span></div>
      </div>
    </header>

    <main>
      <div class="panel"><div id="log"></div></div>
      <div class="panel"><div id="side">
        <div><strong>Presence</strong></div>
        <div id="presence" class="hint">Connecting…</div>
        <div class="sep"></div>
        <div><strong>Agents</strong></div>
        <div id="agents" class="hint">—</div>
        <div class="sep"></div>
        <div><strong>Auth</strong></div>
        <div class="auth">
          <input id="u" placeholder="username" autocomplete="username" />
          <input id="p" placeholder="password" type="password" autocomplete="current-password" />
        </div>
        <div class="auth" style="margin-top:8px;">
          <input id="n" placeholder="nickname (optional)" autocomplete="nickname" />
        </div>
        <div style="margin-top:8px; display:flex; gap:8px;">
          <button id="login">login</button>
          <button id="register">register</button>
          <button id="logout">logout</button>
        </div>
        <div class="hint" id="auth-status" style="margin-top:8px;">auth: unknown</div>
        <div class="hint">
          Try: <code>/help</code>, <code>/agents</code>, <code>/ask all ...</code>, <code>/spawn</code>
        </div>
      </div></div>
    </main>

    <div class="input">
      <input id="msg" placeholder="Type a message… (Enter to send)" autocomplete="off" />
      <button id="send">send</button>
    </div>
  </div>

  <script>
    const roomEl = document.getElementById('room');
    const youEl = document.getElementById('you');
    const logEl = document.getElementById('log');
    const presenceEl = document.getElementById('presence');
    const agentsEl = document.getElementById('agents');

    const msgEl = document.getElementById('msg');
    const sendBtn = document.getElementById('send');

    const uEl = document.getElementById('u');
    const pEl = document.getElementById('p');
    const nEl = document.getElementById('n');
    const loginBtn = document.getElementById('login');
    const registerBtn = document.getElementById('register');
    const logoutBtn = document.getElementById('logout');
    const authStatusEl = document.getElementById('auth-status');

    // Auth uses an HttpOnly cookie (set by /api/login or /api/register).
    // We intentionally do NOT store tokens in localStorage or put them in URLs.
    let ws = null;
    let room = 'lobby';

    function fmtTs(ts) {
      try { return new Date(ts * 1000).toLocaleTimeString([], {hour12:false}); } catch { return ''; }
    }

    function addLine({sender_type, sender_name, content, created_at_ts}) {
      const div = document.createElement('div');
      div.className = 'line';
      const ts = document.createElement('span');
      ts.className = 'ts';
      ts.textContent = `[${fmtTs(created_at_ts)}] `;
      const who = document.createElement('span');
      who.className = `who ${sender_type}`;
      who.textContent = `<${sender_name}> `;
      const body = document.createElement('span');
      body.textContent = content;
      div.appendChild(ts);
      div.appendChild(who);
      div.appendChild(body);
      logEl.appendChild(div);
      logEl.scrollTop = logEl.scrollHeight;
    }

    function setPresence(pres) {
      const lines = pres.map(p => `${p.sender_type}: ${p.sender_name}`).sort();
      presenceEl.textContent = lines.length ? lines.join('\\n') : '—';
    }

    function setAgents(agents) {
      const lines = (agents || []).map(a => `${a.name} (${a.id})`).sort();
      agentsEl.textContent = lines.length ? lines.join('\\n') : '—';
    }

    async function auth(path, payload) {
      const res = await fetch(path, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'auth_failed');
      return data;
    }

    async function refreshMe() {
      try {
        const res = await fetch('/api/me');
        const data = await res.json();
        if (data.success && data.authenticated) {
          authStatusEl.textContent = `auth: ${data.user.nickname} (${data.user.username})${data.is_admin ? ' [admin]' : ''}`;
        } else {
          authStatusEl.textContent = 'auth: guest';
        }
      } catch {
        authStatusEl.textContent = 'auth: unknown';
      }
    }

    async function login() {
      await auth('/api/login', { username: uEl.value.trim(), password: pEl.value });
      connect();
      await refreshMe();
    }

    async function register() {
      await auth('/api/register', { username: uEl.value.trim(), password: pEl.value, nickname: nEl.value.trim() || undefined });
      connect();
      await refreshMe();
    }

    function logout() {
      fetch('/api/logout', { method:'POST' })
        .then(() => connect())
        .then(() => refreshMe())
        .catch(() => { connect(); refreshMe(); });
    }

    function connect() {
      if (ws) { try { ws.close(); } catch {} ws = null; }
      const url = new URL((location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/ws');
      url.searchParams.set('room', room);
      ws = new WebSocket(url.toString());

      presenceEl.textContent = 'Connecting…';
      agentsEl.textContent = '—';

      ws.onmessage = (evt) => {
        let msg;
        try { msg = JSON.parse(evt.data); } catch { return; }
        if (msg.type === 'hello') {
          room = msg.room;
          roomEl.textContent = room;
          youEl.textContent = msg.you?.sender_name || 'guest';
          logEl.innerHTML = '';
          (msg.history || []).forEach(addLine);
          setAgents(msg.agents || []);
          setPresence(msg.presence || []);
          return;
        }
        if (msg.type === 'message') {
          addLine(msg.message);
          return;
        }
        if (msg.type === 'presence') {
          // We don’t diff; server will send full presence on /who.
          return;
        }
        if (msg.type === 'who') { setPresence(msg.presence || []); return; }
        if (msg.type === 'agents') { setAgents(msg.agents || []); return; }
      };

      ws.onopen = () => { /* noop */ };
      ws.onclose = () => { presenceEl.textContent = 'Disconnected. Refresh or reconnect.'; };
    }

    function send() {
      const text = msgEl.value.trim();
      if (!text || !ws || ws.readyState !== 1) return;
      ws.send(JSON.stringify({ type:'chat', room, content: text }));
      msgEl.value = '';
    }

    sendBtn.onclick = send;
    msgEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });
    loginBtn.onclick = () => login().catch(e => alert(String(e)));
    registerBtn.onclick = () => register().catch(e => alert(String(e)));
    logoutBtn.onclick = logout;

    connect();
    refreshMe();
    // Refresh presence periodically via /who (cheap and robust).
    setInterval(() => { try { ws?.send(JSON.stringify({ type:'chat', room, content: '/who' })); } catch {} }, 8000);
  </script>
</body>
</html>
"""

