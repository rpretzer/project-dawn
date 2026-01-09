import asyncio
import json
from pathlib import Path

from core.orchestrator import AgentOrchestrator
from core.task_manager import TaskStore


class _ScriptedAgent:
    def __init__(self):
        self.id = "agent_123"
        self.calls = 0

    async def chat(self, prompt: str, user_id: str = "u") -> str:
        self.calls += 1
        # Planning prompt
        if "Produce a JSON plan only" in prompt:
            # Extract task id to write under artifacts/<task_id>/
            task_id = ""
            for line in prompt.splitlines():
                if line.startswith("Task id:"):
                    task_id = line.split("Task id:", 1)[1].strip()
                    break
            return json.dumps(
                {
                    "goal": "write an artifact",
                    "steps": [
                        {
                            "do": "Write deliverable file",
                            "tool": "fs_write",
                            "args": {"path": f"artifacts/{task_id}/result.txt", "content": "hello world", "overwrite": True},
                        }
                    ],
                }
            )

        # Finalization prompt
        if "Finalize this task for the requester" in prompt:
            assert "Tool results" in prompt
            return "Done. Wrote artifacts/<task_id>/result.txt"

        return "ok"


def test_task_writes_artifact_and_finalization_sees_tool_results(tmp_path: Path) -> None:
    ts = TaskStore(db_path=tmp_path / "tasks.db")
    agent = _ScriptedAgent()
    orch = AgentOrchestrator(agents=[agent], task_store=ts, workspace_root=tmp_path)

    t = ts.create_task(
        room="lobby",
        created_by="u1",
        requested_by_name="alice",
        assigned_to=agent.id,
        title="Write artifact",
        prompt="Create a file deliverable.",
    )

    async def run() -> None:
        await orch._run_task(agent, t.id)  # type: ignore[attr-defined]

    asyncio.run(run())

    done = ts.get_task(t.id)
    assert done is not None
    assert done.status == "completed"
    assert done.result and "Wrote" in done.result

    artifact = tmp_path / "artifacts" / t.id / "result.txt"
    assert artifact.exists()
    assert artifact.read_text(encoding="utf-8") == "hello world"

