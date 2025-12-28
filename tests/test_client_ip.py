import ipaddress

import interface.realtime_server as rs


def test_client_ip_from_request_meta_does_not_trust_headers_by_default():
    ip = rs._client_ip_from_request_meta(
        remote="10.0.0.5",
        headers={"X-Forwarded-For": "1.2.3.4"},
        trust_proxy_headers=False,
        trusted_proxy_nets=[ipaddress.ip_network("10.0.0.0/8")],
    )
    assert ip == "10.0.0.5"


def test_client_ip_from_request_meta_trusts_only_trusted_proxy_peer():
    nets = [ipaddress.ip_network("10.0.0.0/8")]
    ip = rs._client_ip_from_request_meta(
        remote="10.0.0.5",
        headers={"X-Forwarded-For": "1.2.3.4, 10.0.0.5"},
        trust_proxy_headers=True,
        trusted_proxy_nets=nets,
    )
    assert ip == "1.2.3.4"

    # Untrusted peer -> ignore forwarded headers
    ip2 = rs._client_ip_from_request_meta(
        remote="203.0.113.9",
        headers={"X-Forwarded-For": "1.2.3.4"},
        trust_proxy_headers=True,
        trusted_proxy_nets=nets,
    )
    assert ip2 == "203.0.113.9"

