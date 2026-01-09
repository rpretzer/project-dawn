import asyncio
import json
import subprocess
from pathlib import Path

from core.orchestrator import AgentOrchestrator
from core.task_manager import TaskStore


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True)


class _PatchProposingAgent:
    def __init__(self):
        self.id = "agent_patch"
        self.saw_finalize = False

    async def chat(self, prompt: str, user_id: str = "u") -> str:
        # Planning prompt: create a patch artifact and validate with check_only.
        if "Produce a JSON plan only" in prompt:
            task_id = ""
            for line in prompt.splitlines():
                if line.startswith("Task id:"):
                    task_id = line.split("Task id:", 1)[1].strip()
                    break
            patch_path = f"artifacts/{task_id}/change.patch"
            patch = (
                "diff --git a/core/x.txt b/core/x.txt\n"
                "index 3b18e51..2c2b0b9 100644\n"
                "--- a/core/x.txt\n"
                "+++ b/core/x.txt\n"
                "@@ -1 +1 @@\n"
                "-hello\n"
                "+hello world\n"
            )
            return json.dumps(
                {
                    "goal": "propose a patch",
                    "steps": [
                        {"do": "Write patch artifact", "tool": "fs_write", "args": {"path": patch_path, "content": patch, "overwrite": True}},
                        {"do": "Check patch applies cleanly", "tool": "fs_apply_patch", "args": {"patch": patch, "check_only": True}},
                    ],
                }
            )

        if "Finalize this task for the requester" in prompt:
            self.saw_finalize = True
            assert "Patch artifacts" in prompt
            return "Proposed patch written to artifacts/<task_id>/change.patch. Admin should check/apply in UI."

        return "ok"


def test_orchestrator_patch_proposal_flow(tmp_path: Path, monkeypatch) -> None:
    # Setup a git repo with a target file so `git apply --check` can succeed.
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)
    (tmp_path / "core").mkdir(parents=True, exist_ok=True)
    f = tmp_path / "core" / "x.txt"
    f.write_text("hello\n", encoding="utf-8")
    _run(["git", "add", "core/x.txt"], tmp_path)
    _run(["git", "commit", "-m", "init"], tmp_path)

    # Allow patch checks on core/; still keep apply disabled by default.
    monkeypatch.setenv("DAWN_PATCH_PREFIXES", "core/,artifacts/")
    monkeypatch.delenv("DAWN_ALLOW_AGENT_PATCH_APPLY", raising=False)

    ts = TaskStore(db_path=tmp_path / "tasks.db")
    agent = _PatchProposingAgent()
    orch = AgentOrchestrator(agents=[agent], task_store=ts, workspace_root=tmp_path)

    t = ts.create_task(
        room="lobby",
        created_by="u1",
        requested_by_name="alice",
        assigned_to=agent.id,
        title="Propose patch",
        prompt="Change greeting in core/x.txt via patch artifact.",
    )

    async def run() -> None:
        await orch._run_task(agent, t.id)  # type: ignore[attr-defined]

    asyncio.run(run())

    done = ts.get_task(t.id)
    assert done is not None
    assert done.status == "completed"
    assert done.result and "patch" in done.result.lower()
    assert agent.saw_finalize is True

    patch_file = tmp_path / "artifacts" / t.id / "change.patch"
    assert patch_file.exists()
    # Patch check_only should not have modified the file.
    assert f.read_text(encoding="utf-8") == "hello\n"

