from pathlib import Path

from interface.realtime_server import _is_allowed_read_path, _list_files_under, _read_text_file


def test_ui_file_read_is_prefix_restricted(tmp_path: Path) -> None:
    (tmp_path / "artifacts" / "tsk_1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts" / "tsk_1" / "out.txt").write_text("ok", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")

    prefixes = ["artifacts/"]
    assert _is_allowed_read_path("artifacts/tsk_1/out.txt", prefixes) is True
    assert _is_allowed_read_path(".env", prefixes) is False
    assert _is_allowed_read_path("../.env", prefixes) is False

    files = _list_files_under(tmp_path, "artifacts/tsk_1", limit=50)
    assert "artifacts/tsk_1/out.txt" in files

    res = _read_text_file(tmp_path, "artifacts/tsk_1/out.txt", max_bytes=1000)
    assert res["ok"] is True
    assert res["content"] == "ok"

