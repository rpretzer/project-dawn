import re

from crypto.signing import derive_peer_id_from_pgp_public_key


def test_peer_id_derivation_is_deterministic():
    armored = "\n".join(
        [
            "-----BEGIN PGP PUBLIC KEY BLOCK-----",
            "dGVzdC1rZXktYnl0ZXM=",  # base64("test-key-bytes")
            "=abcd",
            "-----END PGP PUBLIC KEY BLOCK-----",
        ]
    )
    peer_a = derive_peer_id_from_pgp_public_key(armored)
    peer_b = derive_peer_id_from_pgp_public_key(armored)
    assert peer_a == peer_b
    assert re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]+", peer_a)
