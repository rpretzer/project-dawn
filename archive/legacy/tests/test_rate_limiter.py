from collections import deque

from interface.realtime_server import _rate_allow


def test_rate_allow_sliding_window() -> None:
    q = deque(maxlen=10)
    now = 1000.0
    assert _rate_allow(q, now=now, window_seconds=60, limit=2) is True
    assert _rate_allow(q, now=now + 1, window_seconds=60, limit=2) is True
    assert _rate_allow(q, now=now + 2, window_seconds=60, limit=2) is False

    # After window passes, should allow again.
    assert _rate_allow(q, now=now + 61, window_seconds=60, limit=2) is True

