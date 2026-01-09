import subprocess
from pathlib import Path

from interface.realtime_server import _git_apply_stat


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True)


def test_git_apply_stat_preview(tmp_path: Path) -> None:
    _run(["git", "init"], tmp_path)
    (tmp_path / "core").mkdir(parents=True, exist_ok=True)
    f = tmp_path / "core" / "x.txt"
    f.write_text("hello\n", encoding="utf-8")
    _run(["git", "add", "core/x.txt"], tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)
    _run(["git", "commit", "-m", "init"], tmp_path)

    patch = """diff --git a/core/x.txt b/core/x.txt
index 3b18e51..2c2b0b9 100644
--- a/core/x.txt
+++ b/core/x.txt
@@ -1 +1 @@
-hello
+hello world
"""
    res = _git_apply_stat(repo_root=tmp_path, patch_text=patch)
    assert res["ok"] is True
    assert "core/x.txt" in (res.get("stdout") or "")

