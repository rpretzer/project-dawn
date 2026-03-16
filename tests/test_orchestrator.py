import json
import asyncio
import time
import os

from orchestrator import Orchestrator, MAX_TASK_ATTEMPTS
from compute import generate_proof_of_logits, synthetic_logits_provider
from crypto import NodeIdentity
from crypto.signing import MessageSigner


def _signed_proof(identity, index, logit_hash, timestamp):
    signer = MessageSigner(identity)
    payload = f"{index}:{logit_hash}:{timestamp}".encode("utf-8")
    signature = signer.sign(payload).hex()
    return {
        "index": index,
        "logitHash": logit_hash,
        "timestamp": timestamp,
        "nodeSignature": signature,
    }


_PGP_KEY = "\n".join([
    "-----BEGIN PGP PUBLIC KEY BLOCK-----",
    "dGVzdC1rZXktYnl0ZXM=",
    "=abcd",
    "-----END PGP PUBLIC KEY BLOCK-----",
])


def _make_orchestrator(tmp_path):
    """Create an Orchestrator with minimal required filesystem setup."""
    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(_PGP_KEY, encoding="utf-8")
    return Orchestrator(data_dir=data_dir)


# --- validate_local_proof tests ---

def test_validate_local_proof_passes_with_correct_signature(tmp_path):
    orchestrator = _make_orchestrator(tmp_path)
    signer = MessageSigner(orchestrator.identity)
    proof = {
        "index": 1,
        "logitHash": "deadbeef",
        "timestamp": 12345,
        "nodeSignature": signer.sign(b"1:deadbeef:12345").hex(),
    }
    assert orchestrator.validate_local_proof([proof]) is True


def test_validate_local_proof_fails_with_tampered_signature(tmp_path):
    orchestrator = _make_orchestrator(tmp_path)
    signer = MessageSigner(orchestrator.identity)
    proof = {
        "index": 1,
        "logitHash": "deadbeef",
        "timestamp": 12345,
        "nodeSignature": signer.sign(b"1:deadbeef:12345").hex(),
    }
    # Tamper: overwrite signature with zeroes
    proof["nodeSignature"] = "00" * 64
    assert orchestrator.validate_local_proof([proof]) is False


def test_validate_local_proof_fails_with_wrong_key(tmp_path):
    orchestrator = _make_orchestrator(tmp_path)
    foreign_identity = NodeIdentity()
    proof = _signed_proof(foreign_identity, 1, "deadbeef", 12345)
    assert orchestrator.validate_local_proof([proof]) is False


def test_validate_local_proof_fails_empty(tmp_path):
    orchestrator = _make_orchestrator(tmp_path)
    assert orchestrator.validate_local_proof([]) is False


def test_validate_local_proof_fails_missing_signature_field(tmp_path):
    orchestrator = _make_orchestrator(tmp_path)
    proof = {"index": 1, "logitHash": "deadbeef", "timestamp": 12345}  # no nodeSignature
    assert orchestrator.validate_local_proof([proof]) is False


def test_validate_local_proof_rejects_if_any_entry_invalid(tmp_path):
    orchestrator = _make_orchestrator(tmp_path)
    signer = MessageSigner(orchestrator.identity)
    good = {
        "index": 0,
        "logitHash": "aabb",
        "timestamp": 1,
        "nodeSignature": signer.sign(b"0:aabb:1").hex(),
    }
    bad = {
        "index": 1,
        "logitHash": "ccdd",
        "timestamp": 2,
        "nodeSignature": "00" * 64,
    }
    assert orchestrator.validate_local_proof([good, bad]) is False


def test_default_compute_handler_produces_valid_local_proofs(tmp_path):
    """Proofs from the default (synthetic) handler must pass validate_local_proof."""
    orchestrator = _make_orchestrator(tmp_path)
    work_unit = {
        "taskId": "task-syn",
        "inputBlob": {
            "inputTokens": [1, 2, 3],
            "outputTokens": [4, 5, 6, 7],
            "seed": 42,
        },
    }
    proofs = orchestrator.default_compute_handler(work_unit)
    assert orchestrator.validate_local_proof(proofs) is True


def test_orchestrator_processes_inbox(tmp_path):
    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        "\n".join(
            [
                "-----BEGIN PGP PUBLIC KEY BLOCK-----",
                "dGVzdC1rZXktYnl0ZXM=",
                "=abcd",
                "-----END PGP PUBLIC KEY BLOCK-----",
            ]
        ),
        encoding="utf-8",
    )

    inbox_dir = data_dir / "mesh" / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    work_unit = {
        "taskId": "task-1",
        "modelId": "model-x",
        "inputBlob": {"prompt": "hello"},
        "redundancyFactor": 3,
        "rewardValue": 1.0,
    }
    (inbox_dir / "task-1.json").write_text(json.dumps(work_unit), encoding="utf-8")

    identity = NodeIdentity()

    def handler(_work_unit):
        return [_signed_proof(identity, 1, "deadbeef", 1)]

    orchestrator = Orchestrator(data_dir=data_dir, compute_handler=handler)
    result_path = orchestrator.process_work_unit(work_unit, handler(work_unit))

    assert result_path.exists()
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["taskId"] == "task-1"


def test_orchestrator_throttles_when_resource_state(tmp_path):
    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        "\n".join(
            [
                "-----BEGIN PGP PUBLIC KEY BLOCK-----",
                "dGVzdC1rZXktYnl0ZXM=",
                "=abcd",
                "-----END PGP PUBLIC KEY BLOCK-----",
            ]
        ),
        encoding="utf-8",
    )

    mesh_dir = data_dir / "mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    (mesh_dir / "resource_state.json").write_text(
        json.dumps({"throttled": True}),
        encoding="utf-8",
    )

    orchestrator = Orchestrator(data_dir=data_dir, compute_handler=lambda _: [])
    assert orchestrator._should_throttle() is True


def test_orchestrator_default_compute_handler(tmp_path):
    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        "\n".join(
            [
                "-----BEGIN PGP PUBLIC KEY BLOCK-----",
                "dGVzdC1rZXktYnl0ZXM=",
                "=abcd",
                "-----END PGP PUBLIC KEY BLOCK-----",
            ]
        ),
        encoding="utf-8",
    )

    work_unit = {
        "taskId": "task-2",
        "modelId": "model-x",
        "inputBlob": {
            "inputTokens": [1, 2, 3],
            "outputTokens": [4, 5, 6, 7],
            "seed": 7,
        },
        "redundancyFactor": 3,
        "rewardValue": 1.0,
    }

    orchestrator = Orchestrator(data_dir=data_dir)
    proofs = orchestrator.default_compute_handler(work_unit)
    assert proofs


def test_validate_peer_result_consensus(tmp_path):
    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        "\n".join(
            [
                "-----BEGIN PGP PUBLIC KEY BLOCK-----",
                "dGVzdC1rZXktYnl0ZXM=",
                "=abcd",
                "-----END PGP PUBLIC KEY BLOCK-----",
            ]
        ),
        encoding="utf-8",
    )

    orchestrator = Orchestrator(data_dir=data_dir)
    identity_a = NodeIdentity()
    identity_b = NodeIdentity()
    identity_c = NodeIdentity()
    proof_a = [_signed_proof(identity_a, 1, "aa", 1)]
    proof_b = [_signed_proof(identity_b, 1, "aa", 2)]
    proof_c = [_signed_proof(identity_c, 1, "bb", 3)]

    peer_results = [
        {
            "peerId": "peer-1",
            "publicKey": identity_a.serialize_public_key().hex(),
            "proofOfLogits": proof_a,
        },
        {
            "peerId": "peer-2",
            "publicKey": identity_b.serialize_public_key().hex(),
            "proofOfLogits": proof_b,
        },
        {
            "peerId": "peer-3",
            "publicKey": identity_c.serialize_public_key().hex(),
            "proofOfLogits": proof_c,
        },
    ]

    result = orchestrator.validate_peer_result(peer_results)
    assert result["accepted"] is True
    assert orchestrator.reputation.get_peer("peer-1").reputationScore > 0.1
    assert orchestrator.reputation.get_peer("peer-2").reputationScore > 0.1
    assert orchestrator.reputation.get_peer("peer-3").reputationScore <= 0.1


def test_verify_peer_result_signature(tmp_path):
    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        "\n".join(
            [
                "-----BEGIN PGP PUBLIC KEY BLOCK-----",
                "dGVzdC1rZXktYnl0ZXM=",
                "=abcd",
                "-----END PGP PUBLIC KEY BLOCK-----",
            ]
        ),
        encoding="utf-8",
    )

    orchestrator = Orchestrator(data_dir=data_dir)
    identity = NodeIdentity()
    signer = MessageSigner(identity)
    signature = signer.sign(b"1:aa:1").hex()
    peer_result = {
        "peerId": "peer-1",
        "publicKey": identity.serialize_public_key().hex(),
        "proofOfLogits": [{"index": 1, "logitHash": "aa", "timestamp": 1, "nodeSignature": signature}],
    }
    assert orchestrator._verify_peer_result(peer_result) is True

    peer_result["proofOfLogits"][0]["nodeSignature"] = "00" * 64
    assert orchestrator._verify_peer_result(peer_result) is False


def test_process_peer_results(tmp_path):
    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        "\n".join(
            [
                "-----BEGIN PGP PUBLIC KEY BLOCK-----",
                "dGVzdC1rZXktYnl0ZXM=",
                "=abcd",
                "-----END PGP PUBLIC KEY BLOCK-----",
            ]
        ),
        encoding="utf-8",
    )

    orchestrator = Orchestrator(data_dir=data_dir)
    task_id = "task-99"
    identity_a = NodeIdentity()
    identity_b = NodeIdentity()
    identity_c = NodeIdentity()
    for peer_id, logit, identity in [
        ("peer-1", "aa", identity_a),
        ("peer-2", "aa", identity_b),
        ("peer-3", "bb", identity_c),
    ]:
        orchestrator.submit_peer_result(
            task_id,
            {
                "peerId": peer_id,
                "publicKey": identity.serialize_public_key().hex(),
                "proofOfLogits": [_signed_proof(identity, 1, logit, 1)],
            },
        )

    receipts = orchestrator.process_peer_results()
    assert receipts
    receipt_payload = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt_payload["taskId"] == task_id
    assert receipt_payload["accepted"] is True


def test_broadcast_peer_result_uses_dht(tmp_path):
    class StubDHT:
        def __init__(self):
            self.calls = []

        async def store(self, key, value, ttl=0.0):
            self.calls.append((key, value, ttl))
            return True

        async def find_value(self, key):
            return None

    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        "\n".join(
            [
                "-----BEGIN PGP PUBLIC KEY BLOCK-----",
                "dGVzdC1rZXktYnl0ZXM=",
                "=abcd",
                "-----END PGP PUBLIC KEY BLOCK-----",
            ]
        ),
        encoding="utf-8",
    )

    orchestrator = Orchestrator(data_dir=data_dir)
    orchestrator.discovery._dht = StubDHT()

    identity = NodeIdentity()
    peer_result = {
        "peerId": "peer-1",
        "publicKey": identity.serialize_public_key().hex(),
        "proofOfLogits": [_signed_proof(identity, 1, "aa", 1)],
    }

    asyncio.run(orchestrator.broadcast_peer_result("task-1", peer_result))
    assert orchestrator.discovery.get_dht().calls


def test_cleanup_stale_files(tmp_path):
    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        "\n".join(
            [
                "-----BEGIN PGP PUBLIC KEY BLOCK-----",
                "dGVzdC1rZXktYnl0ZXM=",
                "=abcd",
                "-----END PGP PUBLIC KEY BLOCK-----",
            ]
        ),
        encoding="utf-8",
    )

    orchestrator = Orchestrator(data_dir=data_dir)
    processed_path = orchestrator.peer_results_dir / "task-1.jsonl.processed"
    processed_path.write_text("{}", encoding="utf-8")
    consensus_path = orchestrator.consensus_dir / "task-1.json"
    consensus_path.write_text("{}", encoding="utf-8")

    old_time = time.time() - (2 * 24 * 60 * 60)
    os.utime(processed_path, (old_time, old_time))
    os.utime(consensus_path, (old_time, old_time))

    orchestrator.cleanup_stale_files()
    assert not processed_path.exists()
    assert not consensus_path.exists()


def test_work_unit_expiration(tmp_path):
    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        "\n".join(
            [
                "-----BEGIN PGP PUBLIC KEY BLOCK-----",
                "dGVzdC1rZXktYnl0ZXM=",
                "=abcd",
                "-----END PGP PUBLIC KEY BLOCK-----",
            ]
        ),
        encoding="utf-8",
    )

    orchestrator = Orchestrator(data_dir=data_dir)
    expired = {"taskId": "task-expired", "expiresAt": time.time() - 5}
    assert orchestrator.is_work_unit_expired(expired) is True


def test_processed_results_persistence(tmp_path):
    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        "\n".join(
            [
                "-----BEGIN PGP PUBLIC KEY BLOCK-----",
                "dGVzdC1rZXktYnl0ZXM=",
                "=abcd",
                "-----END PGP PUBLIC KEY BLOCK-----",
            ]
        ),
        encoding="utf-8",
    )

    orchestrator = Orchestrator(data_dir=data_dir)
    assert orchestrator._is_duplicate_result("task-1", "peer-1") is False

    reloaded = Orchestrator(data_dir=data_dir)
    assert reloaded._is_duplicate_result("task-1", "peer-1") is True


def test_task_attempts_failure_persisted(tmp_path):
    data_dir = tmp_path / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        "\n".join(
            [
                "-----BEGIN PGP PUBLIC KEY BLOCK-----",
                "dGVzdC1rZXktYnl0ZXM=",
                "=abcd",
                "-----END PGP PUBLIC KEY BLOCK-----",
            ]
        ),
        encoding="utf-8",
    )

    def failing_handler(_work_unit):
        raise RuntimeError("boom")

    inbox_dir = data_dir / "mesh" / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    task = {"taskId": "task-2", "inputBlob": {"inputTokens": [1], "outputTokens": [2]}}
    (inbox_dir / "task-2.json").write_text(json.dumps(task), encoding="utf-8")

    orchestrator = Orchestrator(data_dir=data_dir, compute_handler=failing_handler)
    asyncio.run(orchestrator.run_once())

    attempts = json.loads((data_dir / "mesh" / "task_attempts.json").read_text(encoding="utf-8"))
    assert attempts["task-2"] == 1


# ---------------------------------------------------------------------------
# End-to-end pipeline tests
# ---------------------------------------------------------------------------


def test_run_once_writes_signed_result_to_outbox(tmp_path):
    """
    Full pipeline: a work unit in the inbox is picked up by run_once(),
    proofs are generated with the synthetic provider, signatures are valid,
    and the result is persisted atomically to the outbox.
    """
    orchestrator = _make_orchestrator(tmp_path)
    work_unit = {
        "taskId": "task-e2e",
        "inputBlob": {
            "inputTokens": [10, 20, 30],
            "outputTokens": [40, 50, 60, 70],
            "seed": 99,
        },
    }
    (orchestrator.inbox_dir / "task-e2e.json").write_text(
        json.dumps(work_unit), encoding="utf-8"
    )

    result_path = asyncio.run(orchestrator.run_once())

    assert result_path is not None, "run_once should return the outbox path"
    assert result_path.exists(), "outbox file must exist"

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["taskId"] == "task-e2e"
    assert payload["peerId"] == orchestrator.peer_id

    proofs = payload["proofOfLogits"]
    assert proofs, "proofs must be non-empty"
    # Verify every proof is signed with this node's key
    assert orchestrator.validate_local_proof(proofs) is True


def test_run_once_requester_reputation_updated(tmp_path):
    """
    When a work unit includes a requesterPeerId, that peer's reputation is
    updated after processing.
    """
    orchestrator = _make_orchestrator(tmp_path)
    work_unit = {
        "taskId": "task-rep",
        "requesterPeerId": "requester-1",
        "inputBlob": {
            "inputTokens": [1, 2],
            "outputTokens": [3, 4],
            "seed": 0,
        },
    }
    (orchestrator.inbox_dir / "task-rep.json").write_text(
        json.dumps(work_unit), encoding="utf-8"
    )

    asyncio.run(orchestrator.run_once())

    record = orchestrator.reputation.get_peer("requester-1")
    assert record is not None, "reputation record should be created for requester"


def test_run_once_max_attempts_blocks_execution(tmp_path):
    """
    A task that has already reached MAX_TASK_ATTEMPTS must not be processed again.
    """
    orchestrator = _make_orchestrator(tmp_path)
    task_id = "task-maxed"
    work_unit = {
        "taskId": task_id,
        "inputBlob": {"inputTokens": [1], "outputTokens": [2], "seed": 0},
    }
    (orchestrator.inbox_dir / f"{task_id}.json").write_text(
        json.dumps(work_unit), encoding="utf-8"
    )

    # Pre-load the attempt counter to the maximum
    orchestrator._task_attempts[task_id] = MAX_TASK_ATTEMPTS
    orchestrator._save_task_attempts()

    result = asyncio.run(orchestrator.run_once())

    assert result is None, "run_once must return None when max attempts exceeded"
    # Outbox should be empty — the task was not computed
    assert not list(orchestrator.outbox_dir.glob("*.json"))


def test_three_peer_consensus_pipeline(tmp_path):
    """
    Full 3-peer consensus pipeline using synthetic_logits_provider:

    - Peers A and B compute with the same seed (same logit hashes → agreement).
    - Peer C computes with a different seed (different logit hashes → minority).
    - process_peer_results() must produce an accepted receipt naming A and B as winners.
    - Peer C's reputation must be penalised; A and B's must improve.
    """
    orchestrator = _make_orchestrator(tmp_path)
    task_id = "task-3peer"

    input_tokens = [1, 2, 3]
    output_tokens = [4, 5, 6, 7, 8]

    peers = [
        ("peer-a", 42),   # same seed — will agree with peer-b
        ("peer-b", 42),   # same seed — will agree with peer-a
        ("peer-c", 99),   # different seed — minority
    ]

    for peer_name, seed in peers:
        identity = NodeIdentity()
        signer = MessageSigner(identity)
        proofs = generate_proof_of_logits(
            model=None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            sample_rate=1.0,   # prove every token position
            top_k=5,
            seed=seed,
            signer=signer,
            logits_provider=synthetic_logits_provider(seed),
        )
        orchestrator.submit_peer_result(
            task_id,
            {
                "peerId": peer_name,
                "publicKey": identity.serialize_public_key().hex(),
                "proofOfLogits": proofs,
            },
        )

    receipts = orchestrator.process_peer_results()

    assert receipts, "consensus receipt must be written"
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))

    assert receipt["taskId"] == task_id
    assert receipt["accepted"] is True
    assert set(receipt["winners"]) == {"peer-a", "peer-b"}

    # Winners should have improved reputation; loser should be penalised.
    assert orchestrator.reputation.get_peer("peer-a").reputationScore > 0.1
    assert orchestrator.reputation.get_peer("peer-b").reputationScore > 0.1
    assert orchestrator.reputation.get_peer("peer-c").reputationScore <= 0.1


def test_consensus_rejected_when_no_majority(tmp_path):
    """
    If all three peers produce different logit hashes, no pair agrees and
    consensus must be rejected (no majority of 2).
    """
    orchestrator = _make_orchestrator(tmp_path)
    task_id = "task-no-majority"

    input_tokens = [1]
    output_tokens = [2, 3]

    # Use three unique seeds so every logit hash is different.
    for i, seed in enumerate([1, 2, 3]):
        identity = NodeIdentity()
        signer = MessageSigner(identity)
        proofs = generate_proof_of_logits(
            model=None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            sample_rate=1.0,
            top_k=5,
            seed=seed,
            signer=signer,
            logits_provider=synthetic_logits_provider(seed),
        )
        orchestrator.submit_peer_result(
            task_id,
            {
                "peerId": f"peer-{i}",
                "publicKey": identity.serialize_public_key().hex(),
                "proofOfLogits": proofs,
            },
        )

    receipts = orchestrator.process_peer_results()
    assert receipts, "receipt must still be written even for rejected consensus"
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["accepted"] is False


def test_write_json_atomic_is_crash_safe(tmp_path):
    """
    _write_json_atomic must produce a file at the target path with the expected
    content.  The tmp file must not remain after a successful write.
    """
    target = tmp_path / "state.json"
    payload = {"key": "value", "number": 42}
    Orchestrator._write_json_atomic(target, payload)

    assert target.exists()
    assert not (tmp_path / "state.json.tmp").exists(), "tmp file must be cleaned up"

    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded == payload


def test_consensus_receipt_written_atomically(tmp_path):
    """
    process_peer_results() must write the consensus receipt via _write_json_atomic
    (no tmp file left behind).
    """
    orchestrator = _make_orchestrator(tmp_path)
    task_id = "task-atomic-receipt"

    for i, seed in enumerate([7, 7, 99]):
        identity = NodeIdentity()
        signer = MessageSigner(identity)
        proofs = generate_proof_of_logits(
            model=None,
            input_tokens=[1],
            output_tokens=[2, 3],
            sample_rate=1.0,
            top_k=5,
            seed=seed,
            signer=signer,
            logits_provider=synthetic_logits_provider(seed),
        )
        orchestrator.submit_peer_result(
            task_id,
            {
                "peerId": f"p{i}",
                "publicKey": identity.serialize_public_key().hex(),
                "proofOfLogits": proofs,
            },
        )

    receipts = orchestrator.process_peer_results()
    assert receipts

    # No leftover tmp file
    assert not list(orchestrator.consensus_dir.glob("*.tmp"))
