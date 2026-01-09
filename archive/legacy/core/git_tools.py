"""
Read-only git helpers for agents.

These are intentionally non-destructive:
- no add/commit/push/reset/checkout
- bounded output and timeouts
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class GitCmdResult:
    ok: bool
    cmd: str
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    truncated: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "ok": self.ok,
            "cmd": self.cmd,
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "truncated": self.truncated,
            "error": self.error,
        }


def _run_git(
    repo_root: Path,
    args: list[str],
    *,
    timeout_seconds: float = 3.0,
    max_bytes: int = 200_000,
) -> GitCmdResult:
    repo_root = repo_root.resolve()
    timeout_seconds = max(0.5, min(float(timeout_seconds), 10.0))
    max_bytes = max(10_000, min(int(max_bytes), 1_000_000))
    cmd = ["git", *args]
    try:
        p = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=False,
            timeout=timeout_seconds,
            check=False,
        )
        out = p.stdout or b""
        err = p.stderr or b""
        truncated = False
        if len(out) > max_bytes:
            out = out[:max_bytes]
            truncated = True
        if len(err) > max_bytes:
            err = err[:max_bytes]
            truncated = True
        return GitCmdResult(
            ok=(p.returncode == 0),
            cmd=" ".join(cmd),
            cwd=str(repo_root),
            exit_code=int(p.returncode),
            stdout=out.decode("utf-8", errors="replace"),
            stderr=err.decode("utf-8", errors="replace"),
            truncated=truncated,
            error=None,
        )
    except Exception as e:
        return GitCmdResult(
            ok=False,
            cmd=" ".join(cmd),
            cwd=str(repo_root),
            exit_code=255,
            stdout="",
            stderr="",
            truncated=False,
            error=str(e),
        )


def git_status(repo_root: Path, *, porcelain: bool = True) -> GitCmdResult:
    args = ["status"]
    if porcelain:
        args += ["--porcelain"]
    return _run_git(repo_root, args)


def git_diff(repo_root: Path, *, staged: bool = False, path: Optional[str] = None) -> GitCmdResult:
    args = ["diff"]
    if staged:
        args.append("--staged")
    if path:
        # Path is treated as relative; git handles it.
        args += ["--", str(path)]
    return _run_git(repo_root, args, timeout_seconds=5.0, max_bytes=400_000)

