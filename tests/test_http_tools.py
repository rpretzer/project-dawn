from core.http_tools import is_allowed_url


def test_http_tools_blocks_non_http_schemes() -> None:
    ok, reason = is_allowed_url("file:///etc/passwd", allowed_hosts=("example.com",))
    assert ok is False
    assert reason == "scheme_not_allowed"


def test_http_tools_blocks_localhost() -> None:
    ok, reason = is_allowed_url("http://localhost:8000/", allowed_hosts=("localhost",))
    assert ok is False
    assert reason == "host_not_allowed"


def test_http_tools_respects_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("DAWN_HTTP_ALLOWED_HOSTS", "example.com")
    ok, reason = is_allowed_url("https://example.com/")
    # DNS might be unavailable in some sandboxes; accept either allow or dns_failed.
    assert (ok is True and reason == "ok") or (ok is False and reason in ("dns_failed", "ip_not_allowed"))

    ok2, reason2 = is_allowed_url("https://raw.githubusercontent.com/")
    # With env override, raw.githubusercontent.com should not be allowed anymore.
    assert ok2 is False
    assert reason2 == "host_not_in_allowlist"

