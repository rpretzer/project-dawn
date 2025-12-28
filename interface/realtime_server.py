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
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque, defaultdict
from pathlib import Path

import jwt
from aiohttp import web, WSMsgType

from .user_database import UserDatabase
from .chat_store import ChatStore
from .moderation_store import ModerationStore
from core.orchestrator import AgentOrchestrator
from core.task_manager import TaskStore, Task
from core.agent_policy import AgentPolicy
from core.evolution_engine import EvolutionEngine
from core.evolution_manager import EvolutionManager
from core.git_tools import git_status as _git_status, git_diff as _git_diff

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


def _task_public(t: Task) -> Dict[str, Any]:
    """
    Public-safe task shape for the web UI.
    Avoids leaking full prompts by default.
    """
    return {
        "id": t.id,
        "room": t.room,
        "created_by": t.created_by,
        "requested_by_name": t.requested_by_name,
        "assigned_to": t.assigned_to,
        "title": t.title,
        "status": t.status,
        "result": (t.result[:3000] if t.result else None),
        "error": (t.error[:1000] if t.error else None),
        "created_at_ts": t.created_at_ts,
        "updated_at_ts": t.updated_at_ts,
    }


def _file_read_prefixes() -> List[str]:
    """
    Comma-separated allowed prefixes (workspace-relative) for file reads from the UI.
    Default: artifacts/ only (prevents leaking .env, keys, etc.).
    """
    raw = (os.getenv("CHAT_FILE_READ_PREFIXES") or "artifacts/").strip()
    prefs = []
    for p in raw.split(","):
        p = p.strip()
        if not p:
            continue
        if p.startswith("/"):
            p = p.lstrip("/")
        if not p.endswith("/"):
            p = p + "/"
        prefs.append(p)
    return prefs or ["artifacts/"]


def _git_diff_prefixes() -> List[str]:
    """
    Allowed path prefixes for git diff requests via the UI.
    Default: artifacts/ only (prevents leaking code/secrets to non-admins; even admin
    should intentionally scope diffs).
    """
    raw = (os.getenv("CHAT_GIT_DIFF_PREFIXES") or "artifacts/").strip()
    prefs = []
    for p in raw.split(","):
        p = p.strip()
        if not p:
            continue
        if p.startswith("/"):
            p = p.lstrip("/")
        # Allow exact files too (no trailing slash required), but normalize below.
        prefs.append(p)
    return prefs or ["artifacts/"]

def _patch_apply_prefixes() -> List[str]:
    """
    Allowed prefixes for patch artifacts that can be applied via the UI.
    Default: artifacts/ only.
    """
    raw = (os.getenv("CHAT_PATCH_APPLY_PREFIXES") or "artifacts/").strip()
    prefs = []
    for p in raw.split(","):
        p = p.strip()
        if not p:
            continue
        if p.startswith("/"):
            p = p.lstrip("/")
        if not p.endswith("/"):
            p = p + "/"
        prefs.append(p)
    return prefs or ["artifacts/"]


def _normalize_rel_path(path: str) -> str:
    p = (path or "").strip().replace("\\", "/")
    if p.startswith("/"):
        p = p.lstrip("/")
    # Remove redundant leading ./ segments.
    while p.startswith("./"):
        p = p[2:]
    return p


def _resolve_under_root(root: Path, rel_path: str) -> Path:
    rel = _normalize_rel_path(rel_path)
    if not rel:
        raise ValueError("path_required")
    cand = (root / rel).resolve()
    if root not in cand.parents and cand != root:
        raise ValueError("path_outside_workspace")
    return cand


def _is_allowed_read_path(rel_path: str, prefixes: List[str]) -> bool:
    rel = _normalize_rel_path(rel_path)
    for pref in prefixes:
        pref_n = _normalize_rel_path(pref)
        # If prefix ends with "/", treat as directory prefix; else treat as either exact file match or dir prefix.
        if pref_n.endswith("/"):
            if rel.startswith(pref_n):
                return True
        else:
            if rel == pref_n or rel.startswith(pref_n.rstrip("/") + "/"):
                return True
    return False


def _is_allowed_git_path(rel_path: str, prefixes: List[str]) -> bool:
    # Same semantics as file read allowlist, but separate env/config.
    return _is_allowed_read_path(rel_path, prefixes)

def _list_files_under(root: Path, rel_dir: str, *, limit: int = 200) -> List[str]:
    limit = max(1, min(int(limit), 500))
    d = _resolve_under_root(root, rel_dir)
    if not d.exists() or not d.is_dir():
        return []
    out: List[str] = []
    for p in d.rglob("*"):
        try:
            if p.is_dir():
                continue
            rp = p.resolve()
            if root not in rp.parents and rp != root:
                continue
            out.append(str(rp.relative_to(root)))
            if len(out) >= limit:
                break
        except Exception:
            continue
    return sorted(out)[:limit]


def _read_text_file(root: Path, rel_path: str, *, max_bytes: int = 100_000) -> Dict[str, Any]:
    max_bytes = max(1000, min(int(max_bytes), 500_000))
    p = _resolve_under_root(root, rel_path)
    if not p.exists() or not p.is_file():
        return {"ok": False, "error": "not_found"}
    data = p.read_bytes()
    truncated = False
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated = True
    text = data.decode("utf-8", errors="replace")
    return {"ok": True, "path": str(p.relative_to(root)), "content": text, "truncated": truncated}


def _git_apply_stat(*, repo_root: Path, patch_text: str) -> Dict[str, Any]:
    """
    Return a `git apply --stat` preview (no changes made).
    """
    try:
        proc = subprocess.run(
            ["git", "apply", "--stat", "--whitespace=nowarn"],
            cwd=str(repo_root),
            input=(patch_text or "").encode("utf-8"),
            capture_output=True,
            timeout=8.0,
            check=False,
        )
        out = (proc.stdout or b"").decode("utf-8", errors="replace")
        err = (proc.stderr or b"").decode("utf-8", errors="replace")
        return {
            "ok": proc.returncode == 0,
            "exit_code": int(proc.returncode),
            "stdout": out[:20000],
            "stderr": err[:20000],
            "truncated": (len(out) > 20000 or len(err) > 20000),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _is_command(text: str) -> bool:
    return text.strip().startswith("/")


class RealtimeChatServer:
    def __init__(self, *, consciousnesses: List[Any], swarm: Any = None):
        self.consciousnesses = consciousnesses
        self.swarm = swarm

        self.user_db = UserDatabase()
        self.chat_store = ChatStore()
        self.task_store = TaskStore()
        self.orchestrator = AgentOrchestrator(
            agents=self.consciousnesses,
            swarm=self.swarm,
            task_store=self.task_store,
            workspace_root=Path(os.getenv("DAWN_WORKSPACE_ROOT", "/workspace")),
        )
        self.moderation = ModerationStore()
        self.evolution = EvolutionEngine(task_store=self.task_store, policy_store=self.orchestrator.policy_store)
        self.evolution_manager = EvolutionManager(
            task_store=self.task_store,
            policy_store=self.orchestrator.policy_store,
            evolution_engine=self.evolution,
        )

        self._bg_tasks: List[asyncio.Task[Any]] = []

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
        self._bg_tasks.append(asyncio.create_task(self.orchestrator.start()))
        self.orchestrator.set_event_sink(self._orchestrator_event_sink)
        self._origins = _allowed_origins()
        self.workspace_root = Path(os.getenv("DAWN_WORKSPACE_ROOT", "/workspace")).resolve()
        self.file_read_prefixes = _file_read_prefixes()
        self.git_diff_prefixes = _git_diff_prefixes()
        self.patch_apply_prefixes = _patch_apply_prefixes()

        # Optional: automatic evolution loop (safe: uses experiments + rollback).
        self.auto_evolution_enabled = os.getenv("AUTO_EVOLUTION", "false").lower() == "true"
        self.auto_evolution_interval_s = float(os.getenv("AUTO_EVOLUTION_INTERVAL_SECONDS", "60"))
        self.auto_evolution_min_tasks_to_start = int(os.getenv("AUTO_EVOLUTION_MIN_TASKS_TO_START", "5"))
        self.auto_evolution_min_tasks_after = int(os.getenv("AUTO_EVOLUTION_MIN_TASKS_AFTER", "5"))
        self.auto_evolution_regression_threshold = float(os.getenv("AUTO_EVOLUTION_REGRESSION_THRESHOLD", "0.08"))
        if self.auto_evolution_enabled:
            self._bg_tasks.append(asyncio.create_task(self._auto_evolution_loop()))

    def _check_origin(self, request: web.Request) -> bool:
        # In dev, allow everything.
        if ENV != "prod":
            return True
        origin = request.headers.get("Origin")
        if not origin:
            return True  # non-browser clients

        # In prod, you generally want an explicit allowlist for browser Origins.
        require_allowlist = (os.getenv("CHAT_REQUIRE_ORIGIN_ALLOWLIST") or "true").lower() == "true"
        if not self._origins:
            return not require_allowlist
        return origin in self._origins

    def _set_auth_cookie(self, resp: web.Response, token: str, request: web.Request) -> None:
        ttl = int(os.getenv("JWT_TTL_SECONDS", "86400"))
        secure = (ENV == "prod") or (request.scheme == "https")
        samesite = (os.getenv("CHAT_COOKIE_SAMESITE") or ("Strict" if ENV == "prod" else "Lax")).strip()
        if samesite.lower() in ("strict", "lax", "none"):
            samesite = samesite.title()
        else:
            samesite = "Lax"
        # HttpOnly cookie so it is not accessible to JS; websocket can still send it.
        resp.set_cookie(
            TOKEN_COOKIE_NAME,
            token,
            max_age=ttl,
            httponly=True,
            secure=secure,
            samesite=samesite,
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
            if ev == "started":
                task = event.get("task") or {}
                room = str(task.get("room") or DEFAULT_ROOM)
                task_id = str(task.get("id") or "")
                t = self.task_store.get_task(task_id) if task_id else None
                if t:
                    await self._broadcast(room, {"type": "task", "event": "started", "task": _task_public(t), "ts": time.time()})
                status = str(task.get("status") or ev)
                assigned_to = str(task.get("assigned_to") or "")
                title = str(task.get("title") or "")
                await self._system(room, f"[task {task_id}] {status} — {title} (agent: {assigned_to})")
                return
            if ev == "completed":
                task = event.get("task") or {}
                room = str(task.get("room") or DEFAULT_ROOM)
                task_id = str(task.get("id") or "")
                t = self.task_store.get_task(task_id) if task_id else None
                if t:
                    await self._broadcast(room, {"type": "task", "event": "completed", "task": _task_public(t), "ts": time.time()})
                assigned_to = str(task.get("assigned_to") or "")
                title = str(task.get("title") or "")
                result = str(task.get("result") or "").strip()
                await self._system(room, f"[task {task_id}] completed — {title} (agent: {assigned_to})")
                if result:
                    # Also emit the actual deliverable into the chat stream as an agent message.
                    agent_name = self._agent_name(assigned_to)
                    m = self.chat_store.append_message(
                        room=room,
                        sender_type="agent",
                        sender_id=assigned_to or None,
                        sender_name=agent_name,
                        content=_truncate_message(f"[task {task_id} result]\n{result}", limit=8000),
                        created_at_ts=time.time(),
                    )
                    await self._broadcast(room, {"type": "message", "message": m.to_dict()})
                return
            if ev == "failed":
                task = event.get("task") or {}
                room = str(task.get("room") or DEFAULT_ROOM)
                task_id = str(task.get("id") or "")
                t = self.task_store.get_task(task_id) if task_id else None
                if t:
                    await self._broadcast(room, {"type": "task", "event": "failed", "task": _task_public(t), "ts": time.time()})
                assigned_to = str(task.get("assigned_to") or "")
                title = str(task.get("title") or "")
                err = str(task.get("error") or "failed")
                await self._system(room, f"[task {task_id}] failed — {title} (agent: {assigned_to})\n{err}")
                return
            if ev == "progress":
                task_id = str(event.get("task_id") or "")
                step = event.get("step")
                do = str(event.get("do") or "")
                task = self.task_store.get_task(task_id) if task_id else None
                room = task.room if task else DEFAULT_ROOM
                await self._broadcast(room, {"type": "task", "event": "progress", "task_id": task_id, "step": step, "do": do, "ts": time.time()})
                await self._system(room, f"[task {task_id}] step {step}: {do}")
                return
            if ev == "tool":
                task_id = str(event.get("task_id") or "")
                name = str(event.get("name") or "")
                task = self.task_store.get_task(task_id) if task_id else None
                room = task.room if task else DEFAULT_ROOM
                await self._broadcast(room, {"type": "task", "event": "tool", "task_id": task_id, "name": name, "ts": time.time()})
                await self._system(room, f"[task {task_id}] tool: {name}")
                return
        except Exception:
            return

    def _agent_name(self, agent_id: str) -> str:
        aid = (agent_id or "").strip()
        for c in self.consciousnesses:
            cid = str(getattr(c, "id", "") or "")
            if cid == aid:
                return str(getattr(c, "name", cid or "Agent"))
        return aid or "Agent"

    async def stop(self) -> None:
        # Cancel background tasks (auto evolution + orchestrator start task)
        for t in list(self._bg_tasks):
            try:
                t.cancel()
            except Exception:
                pass
        await asyncio.gather(*self._bg_tasks, return_exceptions=True)
        self._bg_tasks.clear()

    async def _auto_evolution_loop(self) -> None:
        # Best-effort; never raise.
        while True:
            try:
                # First, finalize experiments (may rollback).
                finalized = self.evolution_manager.check_pending_and_finalize(
                    regression_threshold=self.auto_evolution_regression_threshold
                )
                for exp in finalized:
                    # Keep the room spam-free; log only.
                    logger.info(f"Evolution experiment finalized: {exp.to_dict()}")

                # Then, start new experiments for agents with enough recent tasks and no pending.
                for a in list(self.consciousnesses):
                    aid = str(getattr(a, "id", "agent"))
                    if self.evolution_manager.has_pending(aid):
                        continue
                    recent = self.task_store.list_recent_for_agent(assigned_to=aid, limit=max(1, self.auto_evolution_min_tasks_to_start))
                    done = [t for t in recent if t.status in ("completed", "failed")]
                    if len(done) < max(1, self.auto_evolution_min_tasks_to_start):
                        continue
                    try:
                        exp = self.evolution_manager.start_experiment(agent_id=aid, min_tasks_after=self.auto_evolution_min_tasks_after)
                        logger.info(f"Started evolution experiment: {exp.to_dict()}")
                    except Exception:
                        continue
            except Exception:
                pass
            await asyncio.sleep(max(10.0, self.auto_evolution_interval_s))

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
                "tasks": [_task_public(t) for t in self.task_store.list_recent(room=room, limit=50) if t],
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

        if msg_type == "create_task":
            room = _sanitize_room(payload.get("room") or sess.room)
            target = str(payload.get("target") or "").strip() or "all"
            prompt = _truncate_message(str(payload.get("prompt") or ""), limit=8000)
            if not prompt:
                await self._send(ws, {"type": "error", "error": "prompt_required"})
                return
            await self._create_tasks(room, sess, target, prompt)
            # Nudge clients to refresh tasks.
            tasks = [_task_public(t) for t in self.task_store.list_recent(room=room, limit=50) if t]
            await self._broadcast(room, {"type": "tasks", "room": room, "tasks": tasks, "ts": time.time()})
            return

        if msg_type == "rate_task":
            task_id = str(payload.get("task_id") or "").strip()
            if not task_id:
                await self._send(ws, {"type": "error", "error": "task_id_required"})
                return
            try:
                rating = int(payload.get("rating"))
            except Exception:
                await self._send(ws, {"type": "error", "error": "rating_must_be_1_to_5"})
                return
            comment = payload.get("comment")
            if comment is not None:
                comment = _truncate_message(str(comment), limit=1000)
            t = self.task_store.get_task(task_id)
            if not t:
                await self._send(ws, {"type": "error", "error": "unknown_task"})
                return
            if t.room != sess.room and not sess.is_admin:
                await self._send(ws, {"type": "error", "error": "not_in_task_room"})
                return
            try:
                self.task_store.record_rating(
                    task_id,
                    rater_id=str(sess.sender_id or f"guest:{sess.sender_name}"),
                    rating=rating,
                    comment=comment,
                )
            except Exception as e:
                await self._send(ws, {"type": "error", "error": str(e)})
                return
            await self._send(ws, {"type": "rated", "task_id": task_id, "rating": rating, "ts": time.time()})
            await self._system(t.room, f"Recorded rating for {task_id}: {rating}/5")
            return

        if msg_type == "get_tasks":
            room = _sanitize_room(payload.get("room") or sess.room)
            tasks = [_task_public(t) for t in self.task_store.list_recent(room=room, limit=50) if t]
            await self._send(ws, {"type": "tasks", "room": room, "tasks": tasks, "ts": time.time()})
            return

        if msg_type == "get_task":
            task_id = str(payload.get("task_id") or "").strip()
            if not task_id:
                await self._send(ws, {"type": "error", "error": "task_id_required"})
                return
            t = self.task_store.get_task(task_id)
            if not t:
                await self._send(ws, {"type": "error", "error": "unknown_task"})
                return
            evs = self.task_store.get_events(task_id, after_id=0, limit=200)
            artifacts = _list_files_under(self.workspace_root, f"artifacts/{task_id}", limit=200)
            await self._send(
                ws,
                {
                    "type": "task_detail",
                    "task": _task_public(t),
                    "events": [e.to_dict() for e in evs],
                    "artifacts": artifacts,
                    "ts": time.time(),
                },
            )
            return

        if msg_type == "get_file":
            rel_path = str(payload.get("path") or "").strip()
            if not rel_path:
                await self._send(ws, {"type": "error", "error": "path_required"})
                return
            if not _is_allowed_read_path(rel_path, self.file_read_prefixes):
                await self._send(ws, {"type": "error", "error": "path_not_allowed"})
                return
            try:
                res = _read_text_file(self.workspace_root, rel_path, max_bytes=int(payload.get("max_bytes") or 100_000))
            except Exception as e:
                res = {"ok": False, "error": str(e)}
            if not res.get("ok"):
                await self._send(ws, {"type": "error", "error": res.get("error") or "read_failed"})
                return
            await self._send(
                ws,
                {
                    "type": "file",
                    "path": res["path"],
                    "content": res.get("content") or "",
                    "truncated": bool(res.get("truncated")),
                    "ts": time.time(),
                },
            )
            return

        if msg_type == "get_git_status":
            if not sess.is_admin:
                await self._send(ws, {"type": "error", "error": "permission_denied"})
                return
            porcelain = bool(payload.get("porcelain", True))
            res = _git_status(self.workspace_root, porcelain=porcelain).to_dict()
            await self._send(ws, {"type": "git_status", "result": res, "ts": time.time()})
            return

        if msg_type == "get_git_diff":
            if not sess.is_admin:
                await self._send(ws, {"type": "error", "error": "permission_denied"})
                return
            path = str(payload.get("path") or "").strip()
            if not path:
                await self._send(ws, {"type": "error", "error": "path_required"})
                return
            if not _is_allowed_git_path(path, self.git_diff_prefixes):
                await self._send(ws, {"type": "error", "error": "path_not_allowed"})
                return
            staged = bool(payload.get("staged", False))
            res = _git_diff(self.workspace_root, staged=staged, path=path).to_dict()
            await self._send(ws, {"type": "git_diff", "result": res, "ts": time.time()})
            return

        if msg_type == "check_patch":
            if not sess.is_admin:
                await self._send(ws, {"type": "error", "error": "permission_denied"})
                return
            patch_path = str(payload.get("patch_path") or "").strip()
            if not patch_path:
                await self._send(ws, {"type": "error", "error": "patch_path_required"})
                return
            if not _is_allowed_read_path(patch_path, self.patch_apply_prefixes):
                await self._send(ws, {"type": "error", "error": "path_not_allowed"})
                return
            try:
                read_res = _read_text_file(self.workspace_root, patch_path, max_bytes=500_000)
                if not read_res.get("ok"):
                    await self._send(ws, {"type": "error", "error": read_res.get("error") or "read_failed"})
                    return
                patch_text = str(read_res.get("content") or "")
                proc = subprocess.run(
                    ["git", "apply", "--check", "--whitespace=nowarn"],
                    cwd=str(self.workspace_root),
                    input=patch_text.encode("utf-8"),
                    capture_output=True,
                    timeout=8.0,
                    check=False,
                )
                out = (proc.stdout or b"").decode("utf-8", errors="replace")
                err = (proc.stderr or b"").decode("utf-8", errors="replace")
                await self._send(
                    ws,
                    {
                        "type": "patch_check",
                        "ok": proc.returncode == 0,
                        "patch_path": patch_path,
                        "exit_code": int(proc.returncode),
                        "stdout": out[:20000],
                        "stderr": err[:20000],
                        "truncated": (len(out) > 20000 or len(err) > 20000),
                        "ts": time.time(),
                    },
                )
            except Exception as e:
                await self._send(ws, {"type": "patch_check", "ok": False, "patch_path": patch_path, "error": str(e), "ts": time.time()})
            return

        if msg_type == "stat_patch":
            if not sess.is_admin:
                await self._send(ws, {"type": "error", "error": "permission_denied"})
                return
            patch_path = str(payload.get("patch_path") or "").strip()
            if not patch_path:
                await self._send(ws, {"type": "error", "error": "patch_path_required"})
                return
            if not _is_allowed_read_path(patch_path, self.patch_apply_prefixes):
                await self._send(ws, {"type": "error", "error": "path_not_allowed"})
                return
            try:
                read_res = _read_text_file(self.workspace_root, patch_path, max_bytes=500_000)
                if not read_res.get("ok"):
                    await self._send(ws, {"type": "error", "error": read_res.get("error") or "read_failed"})
                    return
                patch_text = str(read_res.get("content") or "")
                stat = _git_apply_stat(repo_root=self.workspace_root, patch_text=patch_text)
                await self._send(
                    ws,
                    {
                        "type": "patch_stat",
                        "patch_path": patch_path,
                        "ts": time.time(),
                        **stat,
                    },
                )
            except Exception as e:
                await self._send(ws, {"type": "patch_stat", "ok": False, "patch_path": patch_path, "error": str(e), "ts": time.time()})
            return

        if msg_type == "apply_patch":
            if not sess.is_admin:
                await self._send(ws, {"type": "error", "error": "permission_denied"})
                return
            patch_path = str(payload.get("patch_path") or "").strip()
            if not patch_path:
                await self._send(ws, {"type": "error", "error": "patch_path_required"})
                return
            if not _is_allowed_read_path(patch_path, self.patch_apply_prefixes):
                await self._send(ws, {"type": "error", "error": "path_not_allowed"})
                return
            try:
                read_res = _read_text_file(self.workspace_root, patch_path, max_bytes=500_000)
                if not read_res.get("ok"):
                    await self._send(ws, {"type": "error", "error": read_res.get("error") or "read_failed"})
                    return
                patch_text = str(read_res.get("content") or "")
                proc = subprocess.run(
                    ["git", "apply", "--whitespace=nowarn"],
                    cwd=str(self.workspace_root),
                    input=patch_text.encode("utf-8"),
                    capture_output=True,
                    timeout=8.0,
                    check=False,
                )
                out = (proc.stdout or b"").decode("utf-8", errors="replace")
                err = (proc.stderr or b"").decode("utf-8", errors="replace")
                await self._send(
                    ws,
                    {
                        "type": "patch_applied",
                        "ok": proc.returncode == 0,
                        "patch_path": patch_path,
                        "exit_code": int(proc.returncode),
                        "stdout": out[:20000],
                        "stderr": err[:20000],
                        "truncated": (len(out) > 20000 or len(err) > 20000),
                        "ts": time.time(),
                    },
                )
                # If applied successfully, broadcast updated tasks list (and repo status stays manual).
                if proc.returncode == 0:
                    await self._system(sess.room, f"Applied patch: {patch_path}")
            except Exception as e:
                await self._send(ws, {"type": "patch_applied", "ok": False, "patch_path": patch_path, "error": str(e), "ts": time.time()})
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
                + ", /rate <task_id> <1-5> [comment], /policy <agent_id> show|set …, /fitness [agent_id|all]"
                + (", /evolve [agent_id|all]" if sess.is_admin else "")
                + (", /evolution status [agent_id]" if sess.is_admin else "")
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

        if cmd == "/rate":
            # /rate <task_id> <1-5> [comment...]
            if len(parts) < 3:
                await self._system(room, "Usage: /rate <task_id> <1-5> [comment]")
                return
            task_id = parts[1].strip()
            try:
                rating = int(parts[2])
            except Exception:
                await self._system(room, "rating must be 1-5")
                return
            comment = " ".join(parts[3:]) if len(parts) > 3 else None
            try:
                self.orchestrator.task_store.record_rating(
                    task_id,
                    rater_id=str(sess.sender_id or f"guest:{sess.sender_name}"),
                    rating=rating,
                    comment=comment,
                )
                await self._system(room, f"Recorded rating for {task_id}: {rating}/5")
            except Exception as e:
                await self._system(room, f"Failed to record rating: {e}")
            return

        if cmd == "/policy":
            # /policy <agent_id> show
            # /policy <agent_id> set <field> <value>
            # /policy <agent_id> history [n]
            # /policy <agent_id> rollback <history_id>
            if len(parts) < 3:
                await self._system(room, "Usage: /policy <agent_id> show|set|history|rollback ...")
                return
            agent_id = parts[1].strip()
            action = parts[2].strip().lower()
            if action == "show":
                p = self.orchestrator.policy_store.get_policy(agent_id)
                await self._system(room, f"Policy {agent_id}: {p.to_dict()}")
                return
            if action == "history":
                n = 10
                if len(parts) >= 4:
                    try:
                        n = max(1, min(int(parts[3]), 50))
                    except Exception:
                        n = 10
                hist = self.orchestrator.policy_store.list_history(agent_id, limit=n)
                if not hist:
                    await self._system(room, f"No policy history for {agent_id}.")
                    return
                lines = []
                for h in hist:
                    pid = h["id"]
                    pol = h.get("policy") or {}
                    lines.append(
                        f"id={pid} steps={pol.get('max_plan_steps')} tools={pol.get('max_tool_calls')} "
                        f"timeout={pol.get('step_timeout_seconds')} delegation={pol.get('delegation_bias')} verbosity={pol.get('verbosity')}"
                    )
                await self._system(room, "Policy history:\n" + "\n".join(lines))
                return
            if action == "rollback":
                if not sess.is_admin:
                    await self._system(room, "Permission denied.")
                    return
                if len(parts) < 4:
                    await self._system(room, "Usage: /policy <agent_id> rollback <history_id>")
                    return
                try:
                    hid = int(parts[3])
                except Exception:
                    await self._system(room, "history_id must be an integer")
                    return
                try:
                    p = self.orchestrator.policy_store.rollback_to_history_id(agent_id, hid)
                    await self._system(room, f"Rolled back policy for {agent_id}: {p.to_dict()}")
                except Exception as e:
                    await self._system(room, f"Rollback failed: {e}")
                return
            if action == "set":
                if not sess.is_admin:
                    await self._system(room, "Permission denied.")
                    return
                if len(parts) < 5:
                    await self._system(room, "Usage: /policy <agent_id> set <field> <value>")
                    return
                field = parts[3].strip()
                value = " ".join(parts[4:]).strip()
                cur = self.orchestrator.policy_store.get_policy(agent_id)
                data = cur.to_dict()
                if field not in data:
                    await self._system(room, f"Unknown policy field: {field}")
                    return
                # Coerce
                if field in ("max_plan_steps", "max_tool_calls"):
                    data[field] = int(value)
                elif field in ("step_timeout_seconds", "delegation_bias"):
                    data[field] = float(value)
                else:
                    data[field] = value
                newp = AgentPolicy(
                    agent_id=cur.agent_id,
                    max_plan_steps=int(data["max_plan_steps"]),
                    max_tool_calls=int(data["max_tool_calls"]),
                    step_timeout_seconds=float(data["step_timeout_seconds"]),
                    delegation_bias=float(data["delegation_bias"]),
                    verbosity=str(data["verbosity"]),
                )
                self.orchestrator.policy_store.set_policy(newp)
                await self._system(room, f"Policy updated for {agent_id}.")
                return
            await self._system(room, "Usage: /policy <agent_id> show|set ...")
            return

        if cmd == "/fitness":
            # /fitness [agent_id|all]
            target = parts[1].strip() if len(parts) >= 2 else "all"
            agents = self._select_agents(target) if target.lower() != "all" else list(self.consciousnesses)
            if not agents:
                await self._system(room, f"No matching agent for '{target}'. Try /agents.")
                return
            lines: List[str] = []
            for a in agents:
                aid = str(getattr(a, "id", "agent"))
                rep = self.evolution.evaluate_agent(aid)
                lines.append(
                    f"{aid} score={rep.score:.3f} tasks={rep.window_tasks} ok={rep.completed} fail={rep.failed} "
                    f"avg_rating={(f'{rep.avg_rating:.2f}' if rep.avg_rating is not None else 'n/a')} "
                    f"median_s={(f'{rep.median_duration_s:.1f}' if rep.median_duration_s is not None else 'n/a')}"
                )
            await self._system(room, "Fitness:\n" + "\n".join(lines))
            return

        if cmd == "/evolve":
            # /evolve [agent_id|all] (admin)
            if not sess.is_admin:
                await self._system(room, "Permission denied.")
                return
            target = parts[1].strip() if len(parts) >= 2 else "all"
            agents = self._select_agents(target) if target.lower() != "all" else list(self.consciousnesses)
            if not agents:
                await self._system(room, f"No matching agent for '{target}'. Try /agents.")
                return
            lines: List[str] = []
            for a in agents:
                aid = str(getattr(a, "id", "agent"))
                rep, old, new = self.evolution.evolve_agent(aid)
                lines.append(
                    f"{aid} score={rep.score:.3f} "
                    f"policy: steps {old.max_plan_steps}->{new.max_plan_steps}, tools {old.max_tool_calls}->{new.max_tool_calls}, "
                    f"timeout {old.step_timeout_seconds:.0f}->{new.step_timeout_seconds:.0f}s, "
                    f"delegation {old.delegation_bias:.2f}->{new.delegation_bias:.2f}, "
                    f"verbosity {old.verbosity}->{new.verbosity}"
                )
            await self._system(room, "Evolution applied:\n" + "\n".join(lines))
            return

        if cmd == "/evolution":
            if not sess.is_admin:
                await self._system(room, "Permission denied.")
                return
            # /evolution status [agent_id]
            if len(parts) < 2 or parts[1].lower() != "status":
                await self._system(room, "Usage: /evolution status [agent_id]")
                return
            agent_id = parts[2].strip() if len(parts) >= 3 else None
            exps = self.evolution_manager.list_experiments(agent_id=agent_id, limit=10)
            if not exps:
                await self._system(room, "No experiments yet.")
                return
            lines = []
            for e in exps:
                lines.append(
                    f"id={e.id} agent={e.agent_id} status={e.status} base={e.baseline_score:.3f} new={(f'{e.new_score:.3f}' if e.new_score is not None else 'n/a')} decision={e.decision or '—'}"
                )
            await self._system(room, "Evolution experiments:\n" + "\n".join(lines))
            return

        if cmd == "/task":
            # /task show <task_id>
            if len(parts) >= 3 and parts[1].strip().lower() == "show":
                task_id = parts[2].strip()
                t = self.orchestrator.task_store.get_task(task_id)
                if not t:
                    await self._system(room, f"Unknown task: {task_id}")
                    return
                evs = self.orchestrator.task_store.get_events(task_id, after_id=0, limit=50)
                lines = [
                    f"id={t.id} room={t.room} status={t.status} agent={t.assigned_to}",
                    f"title: {t.title}",
                ]
                if t.error:
                    lines.append(f"error: {t.error}")
                if t.result:
                    lines.append("result:")
                    lines.append(str(t.result))
                if evs:
                    lines.append("events (latest 50):")
                    for e in evs[-50:]:
                        lines.append(f"- {e.id} {e.event_type} {e.payload}")
                await self._system(room, "\n".join(lines))
                return

            # /task <agent|all> <work description>
            if len(parts) < 3:
                await self._system(room, "Usage: /task <agent|all> <work description> OR /task show <task_id>")
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

    @web.middleware
    async def request_id_middleware(request: web.Request, handler):
        rid = request.headers.get("X-Request-Id") or secrets.token_hex(8)
        try:
            resp = await handler(request)
        except web.HTTPException as e:
            e.headers["X-Request-Id"] = rid
            raise
        resp.headers["X-Request-Id"] = rid
        return resp

    app.middlewares.append(request_id_middleware)

    @web.middleware
    async def security_headers_middleware(request: web.Request, handler):
        resp = await handler(request)
        # Basic hardening headers
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")

        # CSP: the built-in UI uses inline CSS/JS; keep it self-contained.
        # You can override this via CHAT_CSP if you serve your own UI.
        csp = (os.getenv("CHAT_CSP") or "").strip()
        if not csp:
            csp = (
                "default-src 'self'; "
                "connect-src 'self' ws: wss:; "
                "img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'"
            )
        resp.headers.setdefault("Content-Security-Policy", csp)

        # HSTS only when served over HTTPS (or behind a proxy that sets X-Forwarded-Proto).
        if ENV == "prod":
            proto = (request.headers.get("X-Forwarded-Proto") or request.scheme or "").lower()
            if proto == "https":
                resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        return resp

    app.middlewares.append(security_headers_middleware)

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
        try:
            await srv.stop()
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
    .taskItem { cursor:pointer; color:#9f9; font-size: 12px; margin: 6px 0; }
    .taskItem:hover { color:#0ff; }
    #task-detail { white-space: pre-wrap; word-break: break-word; font-size: 12px; color:#cfc; margin-top:6px; }
    #file-viewer { white-space: pre-wrap; word-break: break-word; font-size: 12px; color:#cfc; margin-top:6px; border:1px dashed #0f0; padding:8px; }
    textarea { width: 100%; min-height: 90px; padding: 8px; border:1px solid #0f0; background:#000; color:#0f0; box-sizing:border-box; }
    select { width: 100%; padding: 6px; border:1px solid #0f0; background:#000; color:#0f0; }
    .miniBtn { padding: 4px 6px; border:1px solid #0f0; background:#001100; color:#0f0; cursor:pointer; font-size: 11px; }
    .miniBtn:hover { border-color:#0ff; color:#0ff; }
    .dangerBtn { border-color:#f00; color:#f88; }
    .dangerBtn:hover { border-color:#f55; color:#fdd; }
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
        <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
          <div><strong>Tasks</strong></div>
          <button id="refresh-tasks" style="padding:6px 8px;">refresh</button>
        </div>
        <div id="tasks" class="hint">—</div>
        <div id="task-detail" class="hint"> </div>
        <div class="sep"></div>
        <div><strong>Artifacts</strong></div>
        <div id="artifacts" class="hint">—</div>
        <div id="file-viewer" class="hint"> </div>
        <div style="margin-top:6px; display:flex; gap:8px;">
          <button id="patch-check" class="miniBtn">check patch</button>
          <button id="patch-apply" class="miniBtn dangerBtn">apply patch</button>
        </div>
        <div id="patch-out" class="hint" style="white-space:pre-wrap; word-break:break-word; border:1px dashed #0f0; padding:8px; margin-top:6px;"> </div>
        <div class="sep"></div>
        <div><strong>Repo (admin)</strong></div>
        <div style="margin-top:6px; display:flex; gap:8px;">
          <button id="repo-status" class="miniBtn">status</button>
          <button id="repo-diff" class="miniBtn">diff</button>
        </div>
        <div class="hint" style="margin-top:6px;">Diff path (allowlisted):</div>
        <input id="repo-diff-path" placeholder="e.g. artifacts/ or core/orchestrator.py" style="width:100%; padding:6px; border:1px solid #0f0; background:#000; color:#0f0; box-sizing:border-box;" />
        <div id="repo-out" class="hint" style="white-space:pre-wrap; word-break:break-word; border:1px dashed #0f0; padding:8px; margin-top:6px;"> </div>
        <div class="sep"></div>
        <div><strong>New Task</strong></div>
        <div class="hint">Assign to:</div>
        <select id="task-target">
          <option value="all">all</option>
        </select>
        <div class="hint" style="margin-top:6px;">Prompt:</div>
        <textarea id="task-prompt" placeholder="Describe the work you want done…"></textarea>
        <div style="margin-top:6px; display:flex; gap:8px;">
          <button id="submit-task" style="padding:6px 8px;">submit</button>
          <button id="clear-task" style="padding:6px 8px;">clear</button>
        </div>
        <div class="sep"></div>
        <div><strong>Rate Task</strong></div>
        <div class="hint">Select a task (above) to rate it.</div>
        <div style="margin-top:6px; display:flex; gap:6px; flex-wrap:wrap;">
          <button class="rate-btn" data-rate="1" style="padding:6px 8px;">1</button>
          <button class="rate-btn" data-rate="2" style="padding:6px 8px;">2</button>
          <button class="rate-btn" data-rate="3" style="padding:6px 8px;">3</button>
          <button class="rate-btn" data-rate="4" style="padding:6px 8px;">4</button>
          <button class="rate-btn" data-rate="5" style="padding:6px 8px;">5</button>
        </div>
        <div class="hint" style="margin-top:6px;">Comment (optional):</div>
        <input id="rate-comment" placeholder="short feedback…" style="width:100%; padding:6px; border:1px solid #0f0; background:#000; color:#0f0; box-sizing:border-box;" />
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
    const tasksEl = document.getElementById('tasks');
    const taskDetailEl = document.getElementById('task-detail');
    const refreshTasksBtn = document.getElementById('refresh-tasks');
    const artifactsEl = document.getElementById('artifacts');
    const fileViewerEl = document.getElementById('file-viewer');
    const taskTargetEl = document.getElementById('task-target');
    const taskPromptEl = document.getElementById('task-prompt');
    const submitTaskBtn = document.getElementById('submit-task');
    const clearTaskBtn = document.getElementById('clear-task');
    const rateCommentEl = document.getElementById('rate-comment');
    const repoStatusBtn = document.getElementById('repo-status');
    const repoDiffBtn = document.getElementById('repo-diff');
    const repoDiffPathEl = document.getElementById('repo-diff-path');
    const repoOutEl = document.getElementById('repo-out');
    const patchCheckBtn = document.getElementById('patch-check');
    const patchApplyBtn = document.getElementById('patch-apply');
    const patchOutEl = document.getElementById('patch-out');

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
    let tasksById = new Map();
    let artifacts = [];
    let selectedTaskId = null;
    let selectedTaskDetail = null; // {task, events, artifacts}
    let agents = [];
    let selectedFilePath = null;

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

    function setAgentOptions(agents_) {
      agents = agents_ || [];
      taskTargetEl.innerHTML = '';
      const optAll = document.createElement('option');
      optAll.value = 'all';
      optAll.textContent = 'all';
      taskTargetEl.appendChild(optAll);
      for (const a of agents) {
        const opt = document.createElement('option');
        opt.value = a.id;
        opt.textContent = `${a.name} (${a.id})`;
        taskTargetEl.appendChild(opt);
      }
    }

    function renderTasks() {
      const list = Array.from(tasksById.values())
        .filter(t => t.room === room)
        .sort((a,b) => (b.created_at_ts||0) - (a.created_at_ts||0))
        .slice(0, 25);
      tasksEl.innerHTML = '';
      if (!list.length) {
        tasksEl.textContent = '—';
        return;
      }
      for (const t of list) {
        const div = document.createElement('div');
        div.className = 'taskItem';
        div.textContent = `${t.status} ${t.id} (${t.assigned_to}) — ${t.title}`;
        div.onclick = () => {
          selectedTaskId = t.id;
          taskDetailEl.textContent = 'Loading task…';
          artifacts = [];
          artifactsEl.textContent = '—';
          fileViewerEl.textContent = ' ';
          try { ws?.send(JSON.stringify({type:'get_task', task_id: t.id})); } catch {}
        };
        tasksEl.appendChild(div);
      }
    }

    function setTasks(tasks) {
      tasksById = new Map();
      for (const t of (tasks || [])) {
        if (t && t.id) tasksById.set(t.id, t);
      }
      renderTasks();
    }

    function upsertTask(t) {
      if (!t || !t.id) return;
      tasksById.set(t.id, t);
      renderTasks();
    }

    function renderArtifacts() {
      artifactsEl.innerHTML = '';
      if (!artifacts || !artifacts.length) {
        artifactsEl.textContent = '—';
        return;
      }
      for (const p of artifacts.slice(0, 50)) {
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.gap = '8px';
        row.style.alignItems = 'center';
        row.style.justifyContent = 'space-between';

        const pathEl = document.createElement('div');
        pathEl.className = 'taskItem';
        pathEl.style.flex = '1';
        pathEl.textContent = p;
        pathEl.onclick = () => {
          selectedFilePath = p;
          fileViewerEl.textContent = 'Loading file…';
          try { ws?.send(JSON.stringify({type:'get_file', path: p, max_bytes: 120000})); } catch {}
        };
        const copyBtn = document.createElement('button');
        copyBtn.className = 'miniBtn';
        copyBtn.textContent = 'copy';
        copyBtn.onclick = (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          try { navigator.clipboard.writeText(p); } catch {}
        };

        row.appendChild(pathEl);
        row.appendChild(copyBtn);
        artifactsEl.appendChild(row);
      }
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

    function renderSelectedTaskDetail() {
      if (!selectedTaskDetail || !selectedTaskDetail.task) {
        taskDetailEl.textContent = ' ';
        return;
      }
      const t = selectedTaskDetail.task;
      const evs = selectedTaskDetail.events || [];
      const lines = [];
      lines.push(`id=${t.id} status=${t.status} agent=${t.assigned_to}`);
      lines.push(`title: ${t.title}`);
      if (t.error) lines.push(`error: ${t.error}`);
      if (t.result) { lines.push('result:'); lines.push(String(t.result)); }
      if (evs.length) {
        lines.push('events:');
        for (const e of evs.slice(-50)) {
          // normalize between server event dicts and live events
          if (e.event_type) {
            lines.push(`- ${e.id} ${e.event_type} ${JSON.stringify(e.payload)}`);
          } else if (e.kind === 'progress') {
            lines.push(`- live progress step=${e.step}: ${e.do}`);
          } else if (e.kind === 'tool') {
            lines.push(`- live tool: ${e.name}`);
          } else {
            lines.push(`- live ${JSON.stringify(e)}`);
          }
        }
      }
      taskDetailEl.textContent = lines.join('\\n');
    }

    function connect() {
      if (ws) { try { ws.close(); } catch {} ws = null; }
      const url = new URL((location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/ws');
      url.searchParams.set('room', room);
      ws = new WebSocket(url.toString());

      presenceEl.textContent = 'Connecting…';
      agentsEl.textContent = '—';
      tasksEl.textContent = '—';
      taskDetailEl.textContent = ' ';
      artifactsEl.textContent = '—';
      fileViewerEl.textContent = ' ';
      patchOutEl.textContent = ' ';
      selectedFilePath = null;
      repoOutEl.textContent = ' ';
      selectedTaskDetail = null;

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
          setAgentOptions(msg.agents || []);
          setPresence(msg.presence || []);
          setTasks(msg.tasks || []);
          artifacts = [];
          renderArtifacts();
          fileViewerEl.textContent = ' ';
          patchOutEl.textContent = ' ';
          selectedFilePath = null;
          repoOutEl.textContent = ' ';
          selectedTaskDetail = null;
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
        if (msg.type === 'agents') { setAgents(msg.agents || []); setAgentOptions(msg.agents || []); return; }
        if (msg.type === 'tasks') { setTasks(msg.tasks || []); return; }
        if (msg.type === 'task') {
          // Live task updates (status/progress/tool) for UI streaming.
          if (msg.task) upsertTask(msg.task);
          if (selectedTaskId) {
            if (msg.task && msg.task.id === selectedTaskId) {
              selectedTaskDetail = selectedTaskDetail || {task: msg.task, events: [], artifacts: artifacts};
              selectedTaskDetail.task = msg.task;
              renderSelectedTaskDetail();
            } else if (msg.task_id && msg.task_id === selectedTaskId) {
              selectedTaskDetail = selectedTaskDetail || {task: tasksById.get(selectedTaskId), events: [], artifacts: artifacts};
              selectedTaskDetail.events = selectedTaskDetail.events || [];
              if (msg.event === 'progress') {
                selectedTaskDetail.events.push({kind:'progress', step: msg.step, do: msg.do, ts: msg.ts});
              } else if (msg.event === 'tool') {
                selectedTaskDetail.events.push({kind:'tool', name: msg.name, ts: msg.ts});
              }
              renderSelectedTaskDetail();
            }
          }
          return;
        }
        if (msg.type === 'task_detail') {
          const t = msg.task;
          if (t) upsertTask(t);
          const evs = msg.events || [];
          artifacts = msg.artifacts || [];
          renderArtifacts();
          selectedTaskDetail = {task: t, events: evs, artifacts: artifacts};
          renderSelectedTaskDetail();
          return;
        }
        if (msg.type === 'file') {
          const header = `[${msg.path}]${msg.truncated ? ' (truncated)' : ''}\\n\\n`;
          fileViewerEl.textContent = header + (msg.content || '');
          return;
        }
        if (msg.type === 'patch_check' || msg.type === 'patch_applied') {
          const head = `${msg.type} ${msg.ok ? 'OK' : 'FAIL'} (exit=${msg.exit_code ?? 'n/a'})\\n`;
          const out = (msg.stdout || '').trim();
          const err = (msg.stderr || '').trim();
          const extra = msg.error ? (`\\nerror: ${msg.error}`) : '';
          patchOutEl.textContent = head + (out ? out : '') + (err ? ('\\n\\n[stderr]\\n' + err) : '') + extra;
          return;
        }
        if (msg.type === 'patch_stat') {
          const head = `patch_stat ${msg.ok ? 'OK' : 'FAIL'} (exit=${msg.exit_code ?? 'n/a'})\\n`;
          const out = (msg.stdout || '').trim();
          const err = (msg.stderr || '').trim();
          const extra = msg.error ? (`\\nerror: ${msg.error}`) : '';
          patchOutEl.textContent = head + (out ? out : '') + (err ? ('\\n\\n[stderr]\\n' + err) : '') + extra;
          return;
        }
        if (msg.type === 'git_status' || msg.type === 'git_diff') {
          const r = msg.result || {};
          const head = `${r.cmd || 'git'} (exit=${r.exit_code})${r.truncated ? ' [truncated]' : ''}\\n`;
          const out = (r.stdout || '').trim();
          const err = (r.stderr || '').trim();
          repoOutEl.textContent = head + (out ? out : '') + (err ? ('\\n\\n[stderr]\\n' + err) : '');
          return;
        }
        if (msg.type === 'rated') {
          if (selectedTaskId) {
            try { ws?.send(JSON.stringify({type:'get_task', task_id: selectedTaskId})); } catch {}
          }
          return;
        }
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
    refreshTasksBtn.onclick = () => { try { ws?.send(JSON.stringify({type:'get_tasks', room})); } catch {} };
    submitTaskBtn.onclick = () => {
      const prompt = (taskPromptEl.value || '').trim();
      const target = (taskTargetEl.value || 'all').trim();
      if (!prompt) return;
      try { ws?.send(JSON.stringify({type:'create_task', room, target, prompt})); } catch {}
      taskPromptEl.value = '';
    };
    clearTaskBtn.onclick = () => { taskPromptEl.value = ''; };
    document.querySelectorAll('.rate-btn').forEach(btn => {
      btn.onclick = () => {
        if (!selectedTaskId) return;
        const rating = parseInt(btn.getAttribute('data-rate') || '0', 10);
        const comment = (rateCommentEl.value || '').trim();
        try { ws?.send(JSON.stringify({type:'rate_task', task_id: selectedTaskId, rating, comment: comment || undefined})); } catch {}
        rateCommentEl.value = '';
      };
    });

    repoStatusBtn.onclick = () => {
      repoOutEl.textContent = 'Loading git status…';
      try { ws?.send(JSON.stringify({type:'get_git_status', porcelain:true})); } catch {}
    };
    repoDiffBtn.onclick = () => {
      const p = (repoDiffPathEl.value || '').trim();
      if (!p) { repoOutEl.textContent = 'Provide a diff path first.'; return; }
      repoOutEl.textContent = 'Loading git diff…';
      try { ws?.send(JSON.stringify({type:'get_git_diff', path: p, staged:false})); } catch {}
    };

    patchCheckBtn.onclick = () => {
      if (!selectedFilePath || !selectedFilePath.endsWith('.patch')) {
        patchOutEl.textContent = 'Select a .patch artifact file first.';
        return;
      }
      patchOutEl.textContent = 'Checking patch…';
      try { ws?.send(JSON.stringify({type:'check_patch', patch_path: selectedFilePath})); } catch {}
    };
    // Preview summary via git apply --stat
    const patchStatBtn = document.createElement('button');
    patchStatBtn.className = 'miniBtn';
    patchStatBtn.textContent = 'stat patch';
    patchStatBtn.onclick = () => {
      if (!selectedFilePath || !selectedFilePath.endsWith('.patch')) {
        patchOutEl.textContent = 'Select a .patch artifact file first.';
        return;
      }
      patchOutEl.textContent = 'Generating patch stat…';
      try { ws?.send(JSON.stringify({type:'stat_patch', patch_path: selectedFilePath})); } catch {}
    };
    // Insert between check and apply (buttons exist in DOM already).
    try {
      patchCheckBtn.parentElement?.insertBefore(patchStatBtn, patchApplyBtn);
    } catch {}
    patchApplyBtn.onclick = () => {
      if (!selectedFilePath || !selectedFilePath.endsWith('.patch')) {
        patchOutEl.textContent = 'Select a .patch artifact file first.';
        return;
      }
      patchOutEl.textContent = 'Applying patch…';
      try { ws?.send(JSON.stringify({type:'apply_patch', patch_path: selectedFilePath})); } catch {}
    };

    connect();
    refreshMe();
    // Refresh presence periodically via /who (cheap and robust).
    setInterval(() => { try { ws?.send(JSON.stringify({ type:'chat', room, content: '/who' })); } catch {} }, 8000);
    // Refresh tasks periodically as well (cheap).
    setInterval(() => { try { ws?.send(JSON.stringify({ type:'get_tasks', room })); } catch {} }, 12000);
  </script>
</body>
</html>
"""

