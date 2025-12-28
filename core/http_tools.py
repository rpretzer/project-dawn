"""
Safe HTTP fetching utilities for agents.

This is intentionally conservative to reduce SSRF risk:
- only http/https
- host allowlist (env-driven)
- block localhost and private/metadata IPs (best-effort)
"""

from __future__ import annotations

import ipaddress
import os
import socket
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


DEFAULT_ALLOWED_HOSTS = ("raw.githubusercontent.com", "api.github.com")


def _parse_allowed_hosts() -> Tuple[str, ...]:
    raw = (os.getenv("DAWN_HTTP_ALLOWED_HOSTS") or "").strip()
    if not raw:
        return DEFAULT_ALLOWED_HOSTS
    hosts = []
    for h in raw.split(","):
        h = h.strip().lower()
        if not h:
            continue
        hosts.append(h)
    return tuple(dict.fromkeys(hosts))


def _is_loopback_or_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except Exception:
        return True
    if addr.is_loopback or addr.is_private or addr.is_link_local:
        return True
    # Explicitly block common cloud metadata IPs
    if str(addr) in ("169.254.169.254",):
        return True
    return False


def _resolve_host_ips(host: str) -> Tuple[str, ...]:
    ips = []
    try:
        for info in socket.getaddrinfo(host, None):
            ip = info[4][0]
            ips.append(ip)
    except Exception:
        return tuple()
    # de-dupe
    return tuple(dict.fromkeys(ips))


def is_allowed_url(url: str, *, allowed_hosts: Optional[Tuple[str, ...]] = None) -> Tuple[bool, str]:
    allowed_hosts = allowed_hosts or _parse_allowed_hosts()
    u = (url or "").strip()
    if not u:
        return False, "url_required"
    try:
        parsed = urllib.parse.urlparse(u)
    except Exception:
        return False, "invalid_url"
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, "scheme_not_allowed"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "host_required"
    if host in ("localhost",):
        return False, "host_not_allowed"
    if host.endswith(".local"):
        return False, "host_not_allowed"
    if host not in allowed_hosts:
        return False, "host_not_in_allowlist"

    ips = _resolve_host_ips(host)
    # If DNS fails, treat as blocked.
    if not ips:
        return False, "dns_failed"
    for ip in ips:
        if _is_loopback_or_private_ip(ip):
            return False, "ip_not_allowed"
    return True, "ok"


@dataclass(frozen=True)
class HttpGetResult:
    ok: bool
    url: str
    final_url: Optional[str]
    status: Optional[int]
    content: Optional[str]
    truncated: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "ok": self.ok,
            "url": self.url,
            "final_url": self.final_url,
            "status": self.status,
            "content": self.content,
            "truncated": self.truncated,
            "error": self.error,
        }


@dataclass(frozen=True)
class HttpGetJsonResult:
    ok: bool
    url: str
    final_url: Optional[str]
    status: Optional[int]
    json: Optional[Any]
    truncated: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "ok": self.ok,
            "url": self.url,
            "final_url": self.final_url,
            "status": self.status,
            "json": self.json,
            "truncated": self.truncated,
            "error": self.error,
        }


def _parse_json_text(text: str, *, max_chars: int = 200_000) -> Tuple[Optional[Any], bool, Optional[str]]:
    """
    Parse JSON from text with a size bound.
    Returns (value, truncated, error).
    """
    if text is None:
        return None, False, "empty"
    if len(text) > max_chars:
        text = text[:max_chars]
        truncated = True
    else:
        truncated = False
    try:
        return json.loads(text), truncated, None
    except Exception as e:
        return None, truncated, f"json_parse_failed:{e}"


def http_get(
    url: str,
    *,
    max_bytes: int = 200_000,
    timeout_seconds: float = 10.0,
    user_agent: str = "ProjectDawn/1.0 (+https://local)",
) -> HttpGetResult:
    ok, reason = is_allowed_url(url)
    if not ok:
        return HttpGetResult(ok=False, url=url, final_url=None, status=None, content=None, truncated=False, error=reason)

    max_bytes = max(1000, min(int(max_bytes), 1_000_000))
    timeout_seconds = max(1.0, min(float(timeout_seconds), 30.0))

    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status = getattr(resp, "status", None)
            final_url = getattr(resp, "geturl", lambda: None)()
            data = resp.read(max_bytes + 1)
            truncated = False
            if len(data) > max_bytes:
                data = data[:max_bytes]
                truncated = True
            text = data.decode("utf-8", errors="replace")
            return HttpGetResult(ok=True, url=url, final_url=str(final_url) if final_url else None, status=int(status) if status is not None else None, content=text, truncated=truncated)
    except Exception as e:
        return HttpGetResult(ok=False, url=url, final_url=None, status=None, content=None, truncated=False, error=str(e))


def http_get_json(
    url: str,
    *,
    max_bytes: int = 300_000,
    timeout_seconds: float = 10.0,
    max_json_chars: int = 200_000,
    user_agent: str = "ProjectDawn/1.0 (+https://local)",
) -> HttpGetJsonResult:
    ok, reason = is_allowed_url(url)
    if not ok:
        return HttpGetJsonResult(ok=False, url=url, final_url=None, status=None, json=None, truncated=False, error=reason)

    max_bytes = max(1000, min(int(max_bytes), 1_000_000))
    timeout_seconds = max(1.0, min(float(timeout_seconds), 30.0))
    max_json_chars = max(1000, min(int(max_json_chars), 1_000_000))

    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status = getattr(resp, "status", None)
            final_url = getattr(resp, "geturl", lambda: None)()
            data = resp.read(max_bytes + 1)
            truncated_bytes = False
            if len(data) > max_bytes:
                data = data[:max_bytes]
                truncated_bytes = True
            text = data.decode("utf-8", errors="replace")
            val, truncated_json, err = _parse_json_text(text, max_chars=max_json_chars)
            if err:
                return HttpGetJsonResult(
                    ok=False,
                    url=url,
                    final_url=str(final_url) if final_url else None,
                    status=int(status) if status is not None else None,
                    json=None,
                    truncated=bool(truncated_bytes or truncated_json),
                    error=err,
                )
            return HttpGetJsonResult(
                ok=True,
                url=url,
                final_url=str(final_url) if final_url else None,
                status=int(status) if status is not None else None,
                json=val,
                truncated=bool(truncated_bytes or truncated_json),
                error=None,
            )
    except Exception as e:
        return HttpGetJsonResult(ok=False, url=url, final_url=None, status=None, json=None, truncated=False, error=str(e))

