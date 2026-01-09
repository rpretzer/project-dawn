import interface.realtime_server as rs


def test_fetch_metadata_blocks_cross_site_only_in_prod():
    old = rs.ENV
    try:
        rs.ENV = "dev"
        assert rs._fetch_metadata_blocks_cross_site({"Sec-Fetch-Site": "cross-site"}) is False

        rs.ENV = "prod"
        assert rs._fetch_metadata_blocks_cross_site({"Sec-Fetch-Site": "cross-site"}) is True
        assert rs._fetch_metadata_blocks_cross_site({"Sec-Fetch-Site": "same-origin"}) is False
        assert rs._fetch_metadata_blocks_cross_site({}) is False
    finally:
        rs.ENV = old


def test_csrf_token_helpers():
    t1 = rs._issue_csrf_token()
    t2 = rs._issue_csrf_token()
    assert isinstance(t1, str) and t1
    assert isinstance(t2, str) and t2
    assert t1 != t2

    assert rs._constant_time_equal("abc", "abc") is True
    assert rs._constant_time_equal("abc", "abd") is False
    assert rs._constant_time_equal("", "") is True

