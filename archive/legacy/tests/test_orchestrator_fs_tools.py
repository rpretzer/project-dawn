import asyncio
from pathlib import Path

from core.orchestrator import AgentOrchestrator
from core.task_manager import TaskStore


class _DummyAgent:
    id = "agent_001"


def test_orchestrator_fs_tools_are_sandboxed(tmp_path: Path) -> None:
    ts = TaskStore(db_path=tmp_path / "tasks.db")
    orch = AgentOrchestrator(agents=[_DummyAgent()], task_store=ts, workspace_root=tmp_path)

    async def run() -> None:
        w = await orch.tools.call("fs_write", {"path": "notes/hello.txt", "content": "hi", "overwrite": True})
        assert w["ok"] is True

        r = await orch.tools.call("fs_read", {"path": "notes/hello.txt"})
        assert r["ok"] is True
        assert "hi" in r["content"]

        lst = await orch.tools.call("fs_list", {"glob": "**/*.txt"})
        assert lst["ok"] is True
        assert "notes/hello.txt" in lst["paths"]

        # Path traversal should be rejected
        bad = await orch.tools.call("fs_read", {"path": "../etc/passwd"})
        assert bad["ok"] is False

    asyncio.run(run())

