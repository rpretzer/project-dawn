import subprocess
from pathlib import Path

from core.git_tools import git_diff, git_status


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True)


def test_git_tools_work_in_temp_repo(tmp_path: Path) -> None:
    _run(["git", "init"], tmp_path)
    # Configure identity locally for the repo (needed on some systems for staging/commits).
    _run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)

    f = tmp_path / "a.txt"
    f.write_text("one\n", encoding="utf-8")
    _run(["git", "add", "a.txt"], tmp_path)
    _run(["git", "commit", "-m", "init"], tmp_path)

    f.write_text("two\n", encoding="utf-8")

    st = git_status(tmp_path, porcelain=True)
    assert st.ok is True
    assert "a.txt" in st.stdout

    df = git_diff(tmp_path, staged=False, path="a.txt")
    assert df.ok is True
    assert "-one" in df.stdout or "-one\n" in df.stdout
    assert "+two" in df.stdout or "+two\n" in df.stdout

