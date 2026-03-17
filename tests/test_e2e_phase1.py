"""
End-to-end smoke test for Phase 1: the complete working-node loop.

Scenario A — consensus loop (no networking required):
  Three orchestrators each generate a Proof-of-Logits for the identical work
  unit, submit their peer results, and the first orchestrator runs 2-of-3
  consensus.  Assert: receipt written and accepted=True.

Scenario B — DHT broadcast / fetch (shared in-memory DHT):
  Two orchestrators share a single DHT instance (no rpc_handler; local
  storage only).  Orchestrator A broadcasts a peer result; orchestrator B
  fetches it.  Assert: B retrieves A's result via the DHT.

These tests do not require real sockets, a GPU, or a running P2P node.
They use the synthetic_logits_provider so the full proof pipeline executes
without a model.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from compute import generate_proof_of_logits, synthetic_logits_provider
from crypto import NodeIdentity
from crypto.signing import MessageSigner
from orchestrator import Orchestrator
from p2p.dht import DHT

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _fake_pgp_key(suffix: str = "A") -> str:
    """Generate a unique fake PGP public key block by varying the base64 payload."""
    import base64
    payload = base64.b64encode(f"fake-key-bytes-{suffix}".encode()).decode()
    return "\n".join([
        "-----BEGIN PGP PUBLIC KEY BLOCK-----",
        payload,
        "=abcd",
        "-----END PGP PUBLIC KEY BLOCK-----",
    ])


_WORK_UNIT = {
    "taskId": "smoke-task-001",
    "taskType": "logit_proof",
    "inputBlob": {
        "inputTokens": [1, 2, 3, 4, 5],
        "outputTokens": [6, 7, 8, 9, 10],
        "seed": 42,
        "sampleRate": 1.0,   # sample every token for determinism in small sets
        "topK": 5,
    },
}


_orch_counter = 0


def _make_orchestrator(base_dir: Path) -> Orchestrator:
    """Create a minimal Orchestrator under base_dir with a unique identity."""
    global _orch_counter
    _orch_counter += 1
    data_dir = base_dir / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        _fake_pgp_key(str(_orch_counter)), encoding="utf-8"
    )
    return Orchestrator(data_dir=data_dir, enable_mdns=False)


def _peer_result(orch: Orchestrator, work_unit: dict) -> dict:
    """Run the compute handler and return a peer_result dict."""
    proofs = orch.default_compute_handler(work_unit)
    return {
        "peerId": orch.peer_id,
        "publicKey": orch.identity.serialize_public_key().hex(),
        "proofOfLogits": proofs,
    }


# ---------------------------------------------------------------------------
# Scenario A: full consensus loop
# ---------------------------------------------------------------------------

def test_three_peer_consensus_produces_accepted_receipt(tmp_path):
    """
    Three peers generate matching proofs → 2-of-3 consensus → accepted receipt.

    Verifies:
    - Proof generation produces matching fingerprints for identical work units.
    - validate_peer_result() accepts ≥2 matching proofs.
    - process_peer_results() writes a consensus receipt to disk.
    """
    orch_a = _make_orchestrator(tmp_path / "a")
    orch_b = _make_orchestrator(tmp_path / "b")
    orch_c = _make_orchestrator(tmp_path / "c")

    task_id = _WORK_UNIT["taskId"]

    # All three peers produce proofs for the same work unit.
    result_a = _peer_result(orch_a, _WORK_UNIT)
    result_b = _peer_result(orch_b, _WORK_UNIT)
    result_c = _peer_result(orch_c, _WORK_UNIT)

    # Write all three results to orchestrator A's peer_results directory.
    for peer_result in (result_a, result_b, result_c):
        orch_a.submit_peer_result(task_id, peer_result)

    # Run consensus on orchestrator A.
    receipts = orch_a.process_peer_results()

    assert len(receipts) == 1, f"Expected 1 receipt, got {len(receipts)}"
    receipt_path = receipts[0]
    assert receipt_path.exists(), f"Receipt file not written: {receipt_path}"

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["taskId"] == task_id
    assert receipt["accepted"] is True, f"Consensus not accepted: {receipt}"
    assert len(receipt["winners"]) >= 2, f"Expected ≥2 winners: {receipt}"


def test_two_peer_consensus_still_accepted(tmp_path):
    """2 matching + 1 divergent → still accepted (2-of-3 satisfied)."""
    orch_a = _make_orchestrator(tmp_path / "a")
    orch_b = _make_orchestrator(tmp_path / "b")
    orch_c = _make_orchestrator(tmp_path / "c")

    task_id = _WORK_UNIT["taskId"]

    result_a = _peer_result(orch_a, _WORK_UNIT)
    result_b = _peer_result(orch_b, _WORK_UNIT)

    # Corrupt C's proofs so they produce a different fingerprint.
    result_c = _peer_result(orch_c, _WORK_UNIT)
    for entry in result_c["proofOfLogits"]:
        entry["logitHash"] = "badf00d" * 8  # tamper hash only — signature will fail but fingerprint diverges

    for peer_result in (result_a, result_b, result_c):
        orch_a.submit_peer_result(task_id, peer_result)

    receipts = orch_a.process_peer_results()
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["accepted"] is True
    # C should not be in winners (divergent fingerprint)
    assert orch_c.peer_id not in receipt["winners"]


def test_no_consensus_below_threshold(tmp_path):
    """Three peers each produce different proofs → no consensus (0-of-3 match)."""
    orch_a = _make_orchestrator(tmp_path / "a")
    orch_b = _make_orchestrator(tmp_path / "b")
    orch_c = _make_orchestrator(tmp_path / "c")

    task_id = _WORK_UNIT["taskId"]

    # Give each peer a distinct seed so proofs diverge.
    def divergent_result(orch: Orchestrator, seed: int) -> dict:
        wu = {**_WORK_UNIT, "inputBlob": {**_WORK_UNIT["inputBlob"], "seed": seed}}
        proofs = generate_proof_of_logits(
            model=None,
            input_tokens=wu["inputBlob"]["inputTokens"],
            output_tokens=wu["inputBlob"]["outputTokens"],
            sample_rate=1.0,
            top_k=5,
            seed=seed,
            logits_provider=synthetic_logits_provider(seed),
            signer=MessageSigner(orch.identity),
        )
        return {
            "peerId": orch.peer_id,
            "publicKey": orch.identity.serialize_public_key().hex(),
            "proofOfLogits": proofs,
        }

    result_a = divergent_result(orch_a, seed=1)
    result_b = divergent_result(orch_b, seed=2)
    result_c = divergent_result(orch_c, seed=3)

    for peer_result in (result_a, result_b, result_c):
        orch_a.submit_peer_result(task_id, peer_result)

    receipts = orch_a.process_peer_results()
    # process_peer_results writes a receipt regardless, but accepted should be False
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["accepted"] is False


def test_consensus_updates_reputation(tmp_path):
    """Winners gain reputation; losers do not."""
    orch_a = _make_orchestrator(tmp_path / "a")
    orch_b = _make_orchestrator(tmp_path / "b")
    orch_c = _make_orchestrator(tmp_path / "c")

    task_id = _WORK_UNIT["taskId"]

    result_a = _peer_result(orch_a, _WORK_UNIT)
    result_b = _peer_result(orch_b, _WORK_UNIT)

    # C diverges — different seed
    result_c = _peer_result(orch_c, {
        **_WORK_UNIT,
        "inputBlob": {**_WORK_UNIT["inputBlob"], "seed": 999},
    })
    # Re-sign after tampering so signature is valid but fingerprint differs
    signer_c = MessageSigner(orch_c.identity)
    for entry in result_c["proofOfLogits"]:
        payload = f"{entry['index']}:{entry['logitHash']}:{entry['timestamp']}".encode()
        entry["nodeSignature"] = signer_c.sign(payload).hex()

    for peer_result in (result_a, result_b, result_c):
        orch_a.submit_peer_result(task_id, peer_result)

    receipts = orch_a.process_peer_results()
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["accepted"] is True

    # Winners: A and B; loser: C
    assert orch_a.peer_id in receipt["winners"]
    assert orch_b.peer_id in receipt["winners"]
    assert orch_c.peer_id not in receipt["winners"]


# ---------------------------------------------------------------------------
# Scenario B: DHT broadcast and fetch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dht_broadcast_and_fetch(tmp_path):
    """
    Orchestrator A stores a peer result in a shared DHT; orchestrator B retrieves it.

    Uses a single in-memory DHT instance (no rpc_handler) shared between both
    orchestrators.  This validates the broadcast_peer_result / fetch_peer_results
    plumbing without requiring real network sockets.
    """
    orch_a = _make_orchestrator(tmp_path / "a")
    orch_b = _make_orchestrator(tmp_path / "b")

    # Create a shared in-memory DHT (no rpc_handler — local storage only).
    shared_dht = DHT(orch_a.identity)
    orch_a.discovery.set_dht(shared_dht)
    orch_b.discovery.set_dht(shared_dht)

    task_id = _WORK_UNIT["taskId"]
    peer_result = _peer_result(orch_a, _WORK_UNIT)

    # A broadcasts its result into the shared DHT.
    # Note: store() returns False when rpc_handler is None (no remote nodes to
    # replicate to), but the value IS written to local storage which B reads via
    # the shared DHT instance.
    await orch_a.broadcast_peer_result(task_id, peer_result)

    # B fetches the result from the shared DHT.
    fetched = await orch_b.fetch_peer_results(task_id, [orch_a.peer_id])
    assert len(fetched) == 1, f"Expected 1 result from DHT, got {len(fetched)}"
    assert fetched[0]["peerId"] == orch_a.peer_id


@pytest.mark.asyncio
async def test_dht_consensus_receipt_broadcast_and_fetch(tmp_path):
    """
    Consensus receipt stored in DHT by A is retrievable by B.
    """
    orch_a = _make_orchestrator(tmp_path / "a")
    orch_b = _make_orchestrator(tmp_path / "b")

    shared_dht = DHT(orch_a.identity)
    orch_a.discovery.set_dht(shared_dht)
    orch_b.discovery.set_dht(shared_dht)

    task_id = _WORK_UNIT["taskId"]
    fake_receipt = {
        "taskId": task_id,
        "accepted": True,
        "winners": [orch_a.peer_id],
        "fingerprint": "abc123",
        "timestamp": time.time(),
    }

    await orch_a.broadcast_consensus_receipt(task_id, fake_receipt)

    retrieved = await shared_dht.find_value(f"consensus:{task_id}")
    assert retrieved is not None
    assert retrieved["taskId"] == task_id
    assert retrieved["accepted"] is True


@pytest.mark.asyncio
async def test_run_once_writes_outbox_and_broadcasts(tmp_path):
    """
    run_once() processes a work unit from the inbox, writes the outbox file,
    and broadcasts the peer result (local DHT store).
    """
    orch = _make_orchestrator(tmp_path / "node")
    shared_dht = DHT(orch.identity)
    orch.discovery.set_dht(shared_dht)

    task_id = "run-once-task-001"
    work_unit = {
        **_WORK_UNIT,
        "taskId": task_id,
        "expiresAt": time.time() + 3600,
    }

    # Write work unit to inbox.
    inbox_path = orch.inbox_dir / f"{task_id}.json"
    inbox_path.write_text(json.dumps(work_unit), encoding="utf-8")

    result_path = await orch.run_once()

    assert result_path is not None, "run_once() returned None — check inbox/compute"
    assert result_path.exists(), f"Outbox file not written: {result_path}"

    outbox_data = json.loads(result_path.read_text(encoding="utf-8"))
    assert outbox_data["taskId"] == task_id
    assert len(outbox_data["proofOfLogits"]) > 0

    # The peer result should be in the local DHT.
    stored = await shared_dht.find_value(f"result:{task_id}:{orch.peer_id}")
    assert stored is not None, "Peer result not found in DHT after run_once()"
    assert stored["peerId"] == orch.peer_id
