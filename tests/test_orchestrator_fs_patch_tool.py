import asyncio
from pathlib import Path

from core.orchestrator import AgentOrchestrator
from core.task_manager import TaskStore


class _DummyAgent:
    id = "agent_001"


def test_fs_patch_replaces_exactly_once(tmp_path: Path) -> None:
    ts = TaskStore(db_path=tmp_path / "tasks.db")
    orch = AgentOrchestrator(agents=[_DummyAgent()], task_store=ts, workspace_root=tmp_path)

    f = tmp_path / "code.py"
    f.write_text("x = 1\nprint(x)\n", encoding="utf-8")

    async def run() -> None:
        ok = await orch.tools.call(
            "fs_patch",
            {"path": "code.py", "old": "x = 1\n", "new": "x = 2\n", "expected_occurrences": 1},
        )
        assert ok["ok"] is True
        assert ok["replacements"] == 1

        bad = await orch.tools.call(
            "fs_patch",
            {"path": "code.py", "old": "print", "new": "echo", "expected_occurrences": 2},
        )
        assert bad["ok"] is False
        assert bad["error"] == "unexpected_occurrence_count"

    asyncio.run(run())

    assert f.read_text(encoding="utf-8") == "x = 2\nprint(x)\n"

