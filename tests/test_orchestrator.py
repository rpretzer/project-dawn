import json
import asyncio
import time
import os

from orchestrator import Orchestrator
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
