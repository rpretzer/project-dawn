import asyncio
import subprocess
from pathlib import Path

import pytest

from core.orchestrator import AgentOrchestrator
from core.task_manager import TaskStore


class _DummyAgent:
    id = "agent_001"


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True)


@pytest.mark.usefixtures("monkeypatch")
def test_fs_apply_patch_check_and_apply(tmp_path: Path, monkeypatch) -> None:
    # Create a temp git repo so `git apply` works.
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)

    (tmp_path / "core").mkdir(parents=True, exist_ok=True)
    f = tmp_path / "core" / "x.txt"
    f.write_text("hello\n", encoding="utf-8")
    _run(["git", "add", "core/x.txt"], tmp_path)
    _run(["git", "commit", "-m", "init"], tmp_path)

    # Allow patching core/ in this test repo.
    monkeypatch.setenv("DAWN_PATCH_PREFIXES", "core/")

    ts = TaskStore(db_path=tmp_path / "tasks.db")
    orch = AgentOrchestrator(agents=[_DummyAgent()], task_store=ts, workspace_root=tmp_path)

    patch = """diff --git a/core/x.txt b/core/x.txt
index 3b18e51..2c2b0b9 100644
--- a/core/x.txt
+++ b/core/x.txt
@@ -1 +1 @@
-hello
+hello world
"""

    async def run() -> None:
        chk = await orch.tools.call("fs_apply_patch", {"patch": patch, "check_only": True})
        assert chk["ok"] is True
        assert chk["check_only"] is True

        app = await orch.tools.call("fs_apply_patch", {"patch": patch, "check_only": False})
        assert app["ok"] is True

    asyncio.run(run())
    assert f.read_text(encoding="utf-8") == "hello world\n"


def test_fs_apply_patch_denies_disallowed_paths(tmp_path: Path, monkeypatch) -> None:
    _run(["git", "init"], tmp_path)
    monkeypatch.setenv("DAWN_PATCH_PREFIXES", "core/")
    ts = TaskStore(db_path=tmp_path / "tasks.db")
    orch = AgentOrchestrator(agents=[_DummyAgent()], task_store=ts, workspace_root=tmp_path)

    patch = """diff --git a/.env b/.env
new file mode 100644
--- /dev/null
+++ b/.env
@@ -0,0 +1 @@
+SECRET=1
"""

    async def run() -> None:
        res = await orch.tools.call("fs_apply_patch", {"patch": patch, "check_only": True})
        assert res["ok"] is False
        assert res["error"] == "path_not_allowed"

    asyncio.run(run())

