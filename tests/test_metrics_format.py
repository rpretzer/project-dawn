from interface.realtime_server import _format_prometheus_metrics


def test_metrics_format_contains_types_and_values() -> None:
    text = _format_prometheus_metrics(
        counters={"dawn_chat_messages_total": 3, "dawn_ws_connections_total": 2},
        gauges={"dawn_ws_clients": 1},
        info={"env": "dev", "version": "dawn"},
    )
    assert "dawn_info" in text
    assert "# TYPE dawn_chat_messages_total counter" in text
    assert "dawn_chat_messages_total 3" in text
    assert "# TYPE dawn_ws_clients gauge" in text
    assert "dawn_ws_clients 1" in text

