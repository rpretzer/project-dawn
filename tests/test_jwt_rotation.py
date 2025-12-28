import time

import jwt

import interface.realtime_server as rs


def test_decode_token_accepts_old_secrets():
    old_secrets = rs.JWT_SECRETS
    old_current = rs.JWT_SECRET_CURRENT
    try:
        rs.JWT_SECRETS = ["new-secret", "old-secret"]
        rs.JWT_SECRET_CURRENT = rs.JWT_SECRETS[0]

        now = int(time.time())
        token_signed_with_old = jwt.encode(
            {"sub": "1", "username": "u", "nickname": "n", "iat": now, "exp": now + 60},
            "old-secret",
            algorithm=rs.JWT_ALG,
        )
        decoded = rs._decode_token(token_signed_with_old)
        assert decoded is not None
        assert decoded.get("username") == "u"

        token_signed_with_new = jwt.encode(
            {"sub": "2", "username": "u2", "nickname": "n2", "iat": now, "exp": now + 60},
            "new-secret",
            algorithm=rs.JWT_ALG,
        )
        decoded2 = rs._decode_token(token_signed_with_new)
        assert decoded2 is not None
        assert decoded2.get("username") == "u2"
    finally:
        rs.JWT_SECRETS = old_secrets
        rs.JWT_SECRET_CURRENT = old_current

