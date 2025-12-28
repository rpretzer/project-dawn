from interface.realtime_server import _is_allowed_git_path


def test_git_diff_allowlist_semantics() -> None:
    prefixes = ["artifacts/", "core/orchestrator.py"]
    assert _is_allowed_git_path("artifacts/tsk_1/out.txt", prefixes) is True
    assert _is_allowed_git_path("core/orchestrator.py", prefixes) is True
    assert _is_allowed_git_path("core/orchestrator.pyc", prefixes) is False
    assert _is_allowed_git_path(".env", prefixes) is False

