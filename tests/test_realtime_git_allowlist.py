from interface.realtime_server import _is_allowed_git_path, _is_patch_artifact_path


def test_git_diff_allowlist_semantics() -> None:
    prefixes = ["artifacts/", "core/orchestrator.py"]
    assert _is_allowed_git_path("artifacts/tsk_1/out.txt", prefixes) is True
    assert _is_allowed_git_path("core/orchestrator.py", prefixes) is True
    assert _is_allowed_git_path("core/orchestrator.pyc", prefixes) is False
    assert _is_allowed_git_path(".env", prefixes) is False


def test_patch_path_must_end_with_dot_patch() -> None:
    assert _is_patch_artifact_path("artifacts/tsk_1/change.patch") is True
    assert _is_patch_artifact_path("artifacts/tsk_1/change.PATCH") is False
    assert _is_patch_artifact_path("artifacts/tsk_1/change.txt") is False

