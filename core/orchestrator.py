"""
Agent orchestration runtime.

Provides:
- Per-agent async work queues
- Task execution with progress streaming
- Delegation & helper-agent spawning via Swarm

This is intentionally conservative: it does not execute arbitrary code.
It uses the agent's existing `chat()` method for planning/execution and
provides a small set of safe orchestration tools.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from core.task_manager import Task, TaskStore
from core.agent_policy import PolicyStore, AgentPolicy
from core.http_tools import http_get as _http_get, http_get_json as _http_get_json
from core.git_tools import git_status as _git_status, git_diff as _git_diff

logger = logging.getLogger(__name__)


OrchestratorEventSink = Callable[[Dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    json_schema: Dict[str, Any]


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tuple[ToolSpec, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]]] = {}

    def register(self, spec: ToolSpec, handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> None:
        self._tools[spec.name] = (spec, handler)

    def specs(self) -> List[ToolSpec]:
        return [spec for spec, _ in self._tools.values()]

    def has(self, name: str) -> bool:
        return name in self._tools

    async def call(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._tools:
            raise KeyError(f"unknown_tool:{name}")
        _, handler = self._tools[name]
        return await handler(args)


class AgentOrchestrator:
    """
    Maintains task queues per agent and executes tasks in background.
    """

    def __init__(
        self,
        *,
        agents: List[Any],
        swarm: Any = None,
        task_store: Optional[TaskStore] = None,
        workspace_root: Optional[Path] = None,
    ):
        self.agents = agents
        self.swarm = swarm
        self.task_store = task_store or TaskStore()
        self.workspace_root = (workspace_root or Path(os.getenv("DAWN_WORKSPACE_ROOT", "/workspace"))).resolve()

        self._queues: Dict[str, asyncio.Queue[str]] = {}
        self._workers: Dict[str, asyncio.Task[None]] = {}
        self._sink: Optional[OrchestratorEventSink] = None

        self.tools = ToolRegistry()
        self._register_default_tools()

        # Per-agent policy store (used for real evolution; not cosmetic)
        self.policy_store = PolicyStore()

    def set_event_sink(self, sink: OrchestratorEventSink) -> None:
        self._sink = sink

    def _register_default_tools(self) -> None:
        def _resolve_safe(rel_path: str) -> Path:
            p = str(rel_path or "").strip()
            if not p:
                raise ValueError("path_required")
            # Treat absolute paths as relative to workspace (avoid escaping).
            if p.startswith("/"):
                p = p.lstrip("/")
            cand = (self.workspace_root / p).resolve()
            # Ensure it's within the workspace root.
            if self.workspace_root not in cand.parents and cand != self.workspace_root:
                raise ValueError("path_outside_workspace")
            return cand

        def _read_text(p: Path, *, max_bytes: int = 500_000) -> str:
            data = p.read_bytes()
            if len(data) > max_bytes:
                raise ValueError("file_too_large")
            return data.decode("utf-8", errors="replace")

        def _patch_prefixes() -> List[str]:
            """
            Workspace-relative prefixes allowed for fs_apply_patch.
            Defaults to code-ish paths but blocks secrets by omission.
            Override with DAWN_PATCH_PREFIXES="core/,interface/,tests/" etc.
            """
            raw = (os.getenv("DAWN_PATCH_PREFIXES") or "").strip()
            if raw:
                prefs = [p.strip() for p in raw.split(",") if p.strip()]
            else:
                prefs = [
                    "core/",
                    "interface/",
                    "systems/",
                    "plugins/",
                    "tests/",
                    "README.md",
                    "ROADMAP.md",
                    "requirements.txt",
                ]
            # Normalize (no leading slash).
            out: List[str] = []
            for p in prefs:
                p = p.strip().lstrip("/")
                if not p:
                    continue
                out.append(p)
            return out

        def _extract_patch_paths(unified_diff: str) -> List[str]:
            """
            Extract b/<path> from `diff --git a/... b/...` headers.
            This is used only for allowlist enforcement.
            """
            paths: List[str] = []
            for line in (unified_diff or "").splitlines():
                if not line.startswith("diff --git "):
                    continue
                parts = line.split()
                if len(parts) < 4:
                    continue
                b_path = parts[3]
                if b_path.startswith("b/"):
                    b_path = b_path[2:]
                b_path = b_path.lstrip("/")
                if b_path and b_path not in paths:
                    paths.append(b_path)
            return paths

        def _allowed_by_prefix(path: str, prefixes: List[str]) -> bool:
            p = (path or "").lstrip("/")
            # hard blocks
            if p in (".env",) or p.startswith(".git/"):
                return False
            for pref in prefixes:
                pref = (pref or "").lstrip("/")
                if not pref:
                    continue
                if pref.endswith("/"):
                    if p.startswith(pref):
                        return True
                else:
                    if p == pref or p.startswith(pref + "/"):
                        return True
            return False

        async def tool_spawn_agent(args: Dict[str, Any]) -> Dict[str, Any]:
            if not self.swarm:
                return {"ok": False, "error": "swarm_unavailable"}
            count = int(args.get("count", 1))
            count = max(1, min(count, 5))
            created: List[Dict[str, Any]] = []
            for _ in range(count):
                # Reuse realtime server’s spawn logic, but keep it internal.
                from core.real_consciousness import ConsciousnessConfig
                from systems.intelligence.llm_integration import LLMConfig
                import os

                llm_config = LLMConfig.from_env()
                new_id = f"consciousness_{len(self.agents):03d}"
                cfg = ConsciousnessConfig(
                    id=new_id,
                    personality_seed=len(self.agents),
                    llm_config=llm_config,
                    enable_blockchain=os.getenv("ENABLE_BLOCKCHAIN", "false").lower() == "true",
                    enable_p2p=os.getenv("ENABLE_P2P", "false").lower() == "true",
                    enable_revenue=os.getenv("ENABLE_REVENUE", "false").lower() == "true",
                )
                agent = await self.swarm.create_consciousness(cfg)
                self.agents.append(agent)
                self._ensure_worker_for_agent(agent)
                created.append({"id": getattr(agent, "id", new_id), "name": getattr(agent, "name", new_id)})
            return {"ok": True, "created": created}

        async def tool_delegate_task(args: Dict[str, Any]) -> Dict[str, Any]:
            # Create a child task assigned to another agent.
            parent_task_id = str(args.get("parent_task_id") or "")
            assigned_to = str(args.get("assigned_to") or "")
            room = str(args.get("room") or "lobby")
            title = str(args.get("title") or "Delegated task")
            prompt = str(args.get("prompt") or "")
            created_by = str(args.get("created_by") or "system")
            requested_by_name = str(args.get("requested_by_name") or "system")
            if not assigned_to or not prompt:
                return {"ok": False, "error": "assigned_to_and_prompt_required"}

            t = self.task_store.create_task(
                room=room,
                created_by=created_by,
                requested_by_name=requested_by_name,
                assigned_to=assigned_to,
                title=title,
                prompt=prompt,
                parent_task_id=parent_task_id or None,
            )
            await self.enqueue(t.id)
            return {"ok": True, "task_id": t.id}

        async def tool_fs_list(args: Dict[str, Any]) -> Dict[str, Any]:
            pattern = str(args.get("glob") or "**/*").strip()
            limit = int(args.get("limit", 200))
            limit = max(1, min(limit, 500))
            try:
                # Only allow relative globs.
                if pattern.startswith("/"):
                    pattern = pattern.lstrip("/")
                paths: List[str] = []
                for p in self.workspace_root.glob(pattern):
                    try:
                        rp = p.resolve()
                        if self.workspace_root not in rp.parents and rp != self.workspace_root:
                            continue
                        if rp.is_dir():
                            continue
                        paths.append(str(rp.relative_to(self.workspace_root)))
                    except Exception:
                        continue
                    if len(paths) >= limit:
                        break
                return {"ok": True, "paths": sorted(paths)[:limit]}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        async def tool_fs_read(args: Dict[str, Any]) -> Dict[str, Any]:
            path = str(args.get("path") or "")
            max_bytes = int(args.get("max_bytes", 50_000))
            max_bytes = max(1_000, min(max_bytes, 500_000))
            try:
                p = _resolve_safe(path)
                if not p.exists() or not p.is_file():
                    return {"ok": False, "error": "not_found"}
                data = p.read_bytes()
                if len(data) > max_bytes:
                    data = data[:max_bytes]
                    truncated = True
                else:
                    truncated = False
                # Best-effort decode.
                text = data.decode("utf-8", errors="replace")
                return {"ok": True, "path": str(p.relative_to(self.workspace_root)), "content": text, "truncated": truncated}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        async def tool_fs_write(args: Dict[str, Any]) -> Dict[str, Any]:
            path = str(args.get("path") or "")
            content = args.get("content")
            overwrite = bool(args.get("overwrite", True))
            if not isinstance(content, str):
                return {"ok": False, "error": "content_must_be_string"}
            if len(content) > 200_000:
                return {"ok": False, "error": "content_too_large"}
            try:
                p = _resolve_safe(path)
                if p.exists() and not overwrite:
                    return {"ok": False, "error": "exists"}
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                return {"ok": True, "path": str(p.relative_to(self.workspace_root)), "bytes": len(content.encode("utf-8"))}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        async def tool_fs_patch(args: Dict[str, Any]) -> Dict[str, Any]:
            """
            Safely patch an existing text file via exact string replacement.
            """
            path = str(args.get("path") or "")
            old = args.get("old")
            new = args.get("new")
            expected = int(args.get("expected_occurrences", 1))
            if not isinstance(old, str) or not isinstance(new, str):
                return {"ok": False, "error": "old_and_new_must_be_strings"}
            if expected < 0 or expected > 50:
                return {"ok": False, "error": "expected_occurrences_out_of_range"}
            if len(old) < 1:
                return {"ok": False, "error": "old_must_be_nonempty"}
            if len(old) > 200_000 or len(new) > 200_000:
                return {"ok": False, "error": "patch_too_large"}
            try:
                p = _resolve_safe(path)
                if not p.exists() or not p.is_file():
                    return {"ok": False, "error": "not_found"}
                text = _read_text(p, max_bytes=500_000)
                count = text.count(old)
                if count != expected:
                    return {"ok": False, "error": "unexpected_occurrence_count", "found": count, "expected": expected}
                patched = text.replace(old, new)
                if len(patched.encode("utf-8")) > 600_000:
                    return {"ok": False, "error": "result_too_large"}
                p.write_text(patched, encoding="utf-8")
                return {"ok": True, "path": str(p.relative_to(self.workspace_root)), "replacements": count}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        async def tool_fs_apply_patch(args: Dict[str, Any]) -> Dict[str, Any]:
            """
            Apply a unified diff to the git workspace (safe allowlist + optional dry-run).
            Uses `git apply` under the hood for correctness.
            """
            patch = args.get("patch")
            check_only = bool(args.get("check_only", False))
            max_files = int(args.get("max_files", 25))
            allow_apply = (os.getenv("DAWN_ALLOW_AGENT_PATCH_APPLY", "false").lower() == "true")
            if not isinstance(patch, str):
                return {"ok": False, "error": "patch_must_be_string"}
            if len(patch) > 500_000:
                return {"ok": False, "error": "patch_too_large"}
            max_files = max(1, min(max_files, 200))
            if not check_only and not allow_apply:
                return {"ok": False, "error": "apply_disabled", "hint": "set DAWN_ALLOW_AGENT_PATCH_APPLY=true to allow agents to apply patches directly"}

            paths = _extract_patch_paths(patch)
            if not paths:
                return {"ok": False, "error": "no_patch_paths_found"}
            if len(paths) > max_files:
                return {"ok": False, "error": "too_many_files", "count": len(paths), "max_files": max_files}

            prefixes = _patch_prefixes()
            denied = [p for p in paths if not _allowed_by_prefix(p, prefixes)]
            if denied:
                return {"ok": False, "error": "path_not_allowed", "denied": denied[:10], "allowed_prefixes": prefixes}

            cmd = ["git", "apply"]
            if check_only:
                cmd.append("--check")
            # Be tolerant of whitespace noise.
            cmd.append("--whitespace=nowarn")
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(self.workspace_root),
                    input=patch.encode("utf-8"),
                    capture_output=True,
                    timeout=8.0,
                    check=False,
                )
                out = (proc.stdout or b"").decode("utf-8", errors="replace")
                err = (proc.stderr or b"").decode("utf-8", errors="replace")
                ok = proc.returncode == 0
                return {
                    "ok": ok,
                    "check_only": check_only,
                    "applied_files": paths,
                    "exit_code": int(proc.returncode),
                    "stdout": out[:20000],
                    "stderr": err[:20000],
                    "truncated": (len(out) > 20000 or len(err) > 20000),
                }
            except Exception as e:
                return {"ok": False, "error": str(e)}

        async def tool_http_get(args: Dict[str, Any]) -> Dict[str, Any]:
            url = str(args.get("url") or "").strip()
            max_bytes = int(args.get("max_bytes", 200_000))
            timeout_seconds = float(args.get("timeout_seconds", 10.0))
            res = _http_get(url, max_bytes=max_bytes, timeout_seconds=timeout_seconds)
            return res.to_dict()

        async def tool_http_get_json(args: Dict[str, Any]) -> Dict[str, Any]:
            url = str(args.get("url") or "").strip()
            max_bytes = int(args.get("max_bytes", 300_000))
            timeout_seconds = float(args.get("timeout_seconds", 10.0))
            max_json_chars = int(args.get("max_json_chars", 200_000))
            res = _http_get_json(url, max_bytes=max_bytes, timeout_seconds=timeout_seconds, max_json_chars=max_json_chars)
            return res.to_dict()

        async def tool_git_status(args: Dict[str, Any]) -> Dict[str, Any]:
            porcelain = bool(args.get("porcelain", True))
            res = _git_status(self.workspace_root, porcelain=porcelain)
            return res.to_dict()

        async def tool_git_diff(args: Dict[str, Any]) -> Dict[str, Any]:
            staged = bool(args.get("staged", False))
            path = args.get("path")
            path_s = str(path).strip() if path is not None else None
            if path_s == "":
                path_s = None
            res = _git_diff(self.workspace_root, staged=staged, path=path_s)
            return res.to_dict()

        self.tools.register(
            ToolSpec(
                name="spawn_agent",
                description="Spawn helper agent(s) in the swarm.",
                json_schema={
                    "type": "object",
                    "properties": {"count": {"type": "integer", "minimum": 1, "maximum": 5}},
                },
            ),
            tool_spawn_agent,
        )
        self.tools.register(
            ToolSpec(
                name="delegate_task",
                description="Create and enqueue a child task assigned to another agent.",
                json_schema={
                    "type": "object",
                    "properties": {
                        "parent_task_id": {"type": "string"},
                        "room": {"type": "string"},
                        "assigned_to": {"type": "string"},
                        "title": {"type": "string"},
                        "prompt": {"type": "string"},
                        "created_by": {"type": "string"},
                        "requested_by_name": {"type": "string"},
                    },
                    "required": ["assigned_to", "prompt"],
                },
            ),
            tool_delegate_task,
        )
        self.tools.register(
            ToolSpec(
                name="fs_list",
                description="List files in the workspace by glob pattern.",
                json_schema={
                    "type": "object",
                    "properties": {
                        "glob": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                    },
                },
            ),
            tool_fs_list,
        )
        self.tools.register(
            ToolSpec(
                name="fs_read",
                description="Read a UTF-8 text file from the workspace.",
                json_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "max_bytes": {"type": "integer", "minimum": 1000, "maximum": 500000},
                    },
                    "required": ["path"],
                },
            ),
            tool_fs_read,
        )
        self.tools.register(
            ToolSpec(
                name="fs_patch",
                description="Patch an existing UTF-8 text file by exact string replacement (safe).",
                json_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old": {"type": "string"},
                        "new": {"type": "string"},
                        "expected_occurrences": {"type": "integer", "minimum": 0, "maximum": 50},
                    },
                    "required": ["path", "old", "new"],
                },
            ),
            tool_fs_patch,
        )
        self.tools.register(
            ToolSpec(
                name="fs_apply_patch",
                description="Apply a unified diff patch to the workspace (git apply, allowlisted paths).",
                json_schema={
                    "type": "object",
                    "properties": {
                        "patch": {"type": "string"},
                        "check_only": {"type": "boolean"},
                        "max_files": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                    "required": ["patch"],
                },
            ),
            tool_fs_apply_patch,
        )
        self.tools.register(
            ToolSpec(
                name="fs_write",
                description="Write a UTF-8 text file into the workspace.",
                json_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "overwrite": {"type": "boolean"},
                    },
                    "required": ["path", "content"],
                },
            ),
            tool_fs_write,
        )
        self.tools.register(
            ToolSpec(
                name="http_get",
                description="Fetch a URL (safe allowlist) and return text content.",
                json_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "max_bytes": {"type": "integer", "minimum": 1000, "maximum": 1000000},
                        "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 30},
                    },
                    "required": ["url"],
                },
            ),
            tool_http_get,
        )
        self.tools.register(
            ToolSpec(
                name="http_get_json",
                description="Fetch a URL (safe allowlist) and parse JSON.",
                json_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "max_bytes": {"type": "integer", "minimum": 1000, "maximum": 1000000},
                        "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 30},
                        "max_json_chars": {"type": "integer", "minimum": 1000, "maximum": 1000000},
                    },
                    "required": ["url"],
                },
            ),
            tool_http_get_json,
        )
        self.tools.register(
            ToolSpec(
                name="git_status",
                description="Read-only: return git status of the workspace (no changes).",
                json_schema={
                    "type": "object",
                    "properties": {"porcelain": {"type": "boolean"}},
                },
            ),
            tool_git_status,
        )
        self.tools.register(
            ToolSpec(
                name="git_diff",
                description="Read-only: return git diff (optionally staged, optionally for a path).",
                json_schema={
                    "type": "object",
                    "properties": {
                        "staged": {"type": "boolean"},
                        "path": {"type": "string"},
                    },
                },
            ),
            tool_git_diff,
        )

    def _ensure_worker_for_agent(self, agent: Any) -> None:
        agent_id = str(getattr(agent, "id", "agent"))
        if agent_id not in self._queues:
            self._queues[agent_id] = asyncio.Queue()
        if agent_id not in self._workers or self._workers[agent_id].done():
            self._workers[agent_id] = asyncio.create_task(self._agent_worker(agent))

    async def start(self) -> None:
        for agent in self.agents:
            self._ensure_worker_for_agent(agent)

    async def stop(self) -> None:
        for w in self._workers.values():
            w.cancel()
        await asyncio.gather(*self._workers.values(), return_exceptions=True)

    async def enqueue(self, task_id: str) -> None:
        task = self.task_store.get_task(task_id)
        if not task:
            raise KeyError("unknown_task")
        q = self._queues.get(task.assigned_to)
        if not q:
            # Task assigned to unknown agent; queue it nowhere (fail fast).
            self.task_store.update_status(task.id, "failed", error=f"unknown_agent:{task.assigned_to}")
            return
        await q.put(task.id)

    async def submit_task(
        self,
        *,
        room: str,
        created_by: str,
        requested_by_name: str,
        assigned_to: str,
        title: str,
        prompt: str,
        parent_task_id: Optional[str] = None,
    ) -> Task:
        t = self.task_store.create_task(
            room=room,
            created_by=created_by,
            requested_by_name=requested_by_name,
            assigned_to=assigned_to,
            title=title,
            prompt=prompt,
            parent_task_id=parent_task_id,
        )
        await self.enqueue(t.id)
        return t

    async def _emit(self, event: Dict[str, Any]) -> None:
        if self._sink:
            try:
                await self._sink(event)
            except Exception:
                # Don't break execution if UI sink fails.
                pass

    async def _agent_worker(self, agent: Any) -> None:
        agent_id = str(getattr(agent, "id", "agent"))
        q = self._queues[agent_id]
        while True:
            task_id = await q.get()
            try:
                await self._run_task(agent, task_id)
            except Exception as e:
                logger.error(f"Worker error for {agent_id} on {task_id}: {e}")
                # Ensure task is marked failed (otherwise it can remain "running" forever).
                t = self.task_store.get_task(task_id)
                if t and t.status not in ("completed", "failed", "cancelled"):
                    self.task_store.update_status(task_id, "failed", error=str(e))
                    self.task_store.append_event(task_id, "failed", {"error": str(e)})
                    try:
                        await self._emit({"type": "task", "event": "failed", "task": self.task_store.get_task(task_id).to_dict()})
                    except Exception:
                        pass
            finally:
                q.task_done()

    async def _run_task(self, agent: Any, task_id: str) -> None:
        task = self.task_store.get_task(task_id)
        if not task:
            return

        policy = self.policy_store.get_policy(task.assigned_to)

        self.task_store.update_status(task.id, "running")
        self.task_store.append_event(task.id, "started", {"agent_id": task.assigned_to, "ts": time.time()})
        await self._emit({"type": "task", "event": "started", "task": self.task_store.get_task(task.id).to_dict()})

        # Simple agentic loop:
        # - ask agent to produce a JSON plan with tool calls
        # - execute tools
        # - ask agent to summarize / finalize
        plan = await self._get_plan(agent, task, policy)
        tool_calls = 0
        tool_results: List[Dict[str, Any]] = []

        for i, step in enumerate(plan.get("steps", [])[: max(1, policy.max_plan_steps)]):
            step_desc = str(step.get("do", f"step_{i+1}"))
            self.task_store.append_event(task.id, "progress", {"step": i + 1, "of": len(plan.get("steps", [])), "do": step_desc})
            await self._emit({"type": "task", "event": "progress", "task_id": task.id, "step": i + 1, "do": step_desc})

            if "tool" in step:
                tool_calls += 1
                if tool_calls > max(1, policy.max_tool_calls):
                    raise RuntimeError("tool_call_limit_exceeded")
                tool_name = str(step.get("tool"))
                tool_args = step.get("args") or {}
                if not isinstance(tool_args, dict):
                    tool_args = {"value": tool_args}
                self.task_store.append_event(task.id, "tool", {"name": tool_name, "args": tool_args})
                await self._emit({"type": "task", "event": "tool", "task_id": task.id, "name": tool_name})
                if self.tools.has(tool_name):
                    result = await asyncio.wait_for(self.tools.call(tool_name, tool_args), timeout=policy.step_timeout_seconds)
                else:
                    result = {"ok": False, "error": f"unknown_tool:{tool_name}"}
                self.task_store.append_event(task.id, "tool_result", {"name": tool_name, "result": result})
                # Keep a compact tool result trace for finalization prompt.
                tool_results.append({"name": tool_name, "args": tool_args, "result": result})
                continue

            # If not a tool, treat as thinking substep and ask agent to elaborate.
            try:
                _ = await asyncio.wait_for(
                    agent.chat(
                        f"Task: {task.title}\nStep: {step_desc}\n"
                        f"Policy: verbosity={policy.verbosity}. Do this step now; report progress.",
                        user_id=str(task.created_by),
                    ),
                    timeout=policy.step_timeout_seconds,
                )
            except Exception:
                # Non-fatal; continue.
                pass

        final = await self._finalize(agent, task, policy, tool_results=tool_results)
        self.task_store.update_status(task.id, "completed", result=final)
        self.task_store.append_event(task.id, "completed", {"result": final[:5000]})
        await self._emit({"type": "task", "event": "completed", "task": self.task_store.get_task(task.id).to_dict()})

    async def _get_plan(self, agent: Any, task: Task, policy: AgentPolicy) -> Dict[str, Any]:
        tools = [{"name": t.name, "description": t.description, "schema": t.json_schema} for t in self.tools.specs()]
        system = (
            "You are an autonomous software agent. Produce a JSON plan only.\n"
            "Rules:\n"
            "- Output MUST be valid JSON.\n"
            "- Structure: {\"goal\": string, \"steps\": [{\"do\": string, \"tool\"?: string, \"args\"?: object}]}\n"
            "- Only use tools listed.\n"
            f"- Keep <= {max(1, policy.max_plan_steps)} steps.\n"
            f"- Prefer delegation when appropriate (delegation_bias={policy.delegation_bias}).\n"
            "- If you need to create/update files as deliverables, use fs_write and write under artifacts/<task_id>/...\n"
            "- If you need to modify existing files, prefer fs_patch (exact replacement) over rewriting whole files.\n"
            "- If you need to inspect repo state, use fs_list/fs_read.\n"
            "- If you need to reference external docs, use http_get/http_get_json (host allowlist applies).\n"
            "- If you need to summarize changes you made, use git_status and git_diff (read-only).\n"
            "- If you need to propose code changes spanning multiple hunks/files, prefer fs_apply_patch (unified diff) and run it with check_only=true first.\n"
            "- IMPORTANT: by default you should NOT apply patches; write the patch to artifacts/<task_id>/change.patch and ask for approval.\n"
        )
        prompt = (
            f"{system}\n"
            f"Available tools:\n{json.dumps(tools, ensure_ascii=False)}\n\n"
            f"Task id: {task.id}\n"
            f"Task title: {task.title}\n"
            f"Task prompt: {task.prompt}\n"
        )
        try:
            text = await asyncio.wait_for(agent.chat(prompt, user_id=str(task.created_by)), timeout=policy.step_timeout_seconds)
            plan = json.loads(text)
            if not isinstance(plan, dict):
                raise ValueError("plan_not_object")
            if "steps" not in plan or not isinstance(plan["steps"], list):
                raise ValueError("plan_missing_steps")
            return plan
        except Exception as e:
            # Fallback minimal plan
            self.task_store.append_event(task.id, "progress", {"note": f"planning_fallback:{e}"})
            return {"goal": task.title, "steps": [{"do": "Respond with an actionable summary"}]}

    async def _finalize(self, agent: Any, task: Task, policy: AgentPolicy, *, tool_results: Optional[List[Dict[str, Any]]] = None) -> str:
        tool_results = tool_results or []
        # Prefer to surface produced artifacts.
        written: List[str] = []
        for tr in tool_results:
            if tr.get("name") != "fs_write":
                continue
            res = tr.get("result") or {}
            if isinstance(res, dict) and res.get("ok") and res.get("path"):
                written.append(str(res.get("path")))

        prompt = (
            f"Finalize this task for the requester.\n"
            f"Task id: {task.id}\n"
            f"Task: {task.title}\n"
            f"Prompt: {task.prompt}\n"
            f"Policy: verbosity={policy.verbosity}.\n"
            f"Tool results (most recent first):\n{json.dumps(list(reversed(tool_results))[:12], ensure_ascii=False)}\n\n"
            f"If you created files, list them explicitly (paths) and describe what they contain.\n"
            f"Prefer writing substantial deliverables to artifacts/{task.id}/... and referencing paths.\n"
            f"Return a concise deliverable and next steps.\n"
        )
        try:
            return await asyncio.wait_for(
                agent.chat(prompt, user_id=str(task.created_by)),
                timeout=float(policy.step_timeout_seconds),
            )
        except Exception as e:
            # Provide fallback that still reports artifacts.
            extra = ""
            if written:
                extra = "\nArtifacts:\n" + "\n".join(f"- {p}" for p in written)
            return f"Task completed, but finalization failed: {e}{extra}"

