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
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from core.task_manager import Task, TaskStore
from core.agent_policy import PolicyStore, AgentPolicy

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

    def __init__(self, *, agents: List[Any], swarm: Any = None, task_store: Optional[TaskStore] = None):
        self.agents = agents
        self.swarm = swarm
        self.task_store = task_store or TaskStore()

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

        final = await self._finalize(agent, task, policy)
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
        )
        prompt = (
            f"{system}\n"
            f"Available tools:\n{json.dumps(tools, ensure_ascii=False)}\n\n"
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

    async def _finalize(self, agent: Any, task: Task, policy: AgentPolicy) -> str:
        prompt = (
            f"Finalize this task for the requester.\n"
            f"Task: {task.title}\n"
            f"Prompt: {task.prompt}\n"
            f"Return a concise deliverable and next steps.\n"
        )
        try:
            return await asyncio.wait_for(
                agent.chat(prompt, user_id=str(task.created_by)),
                timeout=float(policy.step_timeout_seconds),
            )
        except Exception as e:
            return f"Task completed, but finalization failed: {e}"

