"""
DHT two-node integration tests.

These tests wire two real DHT instances together using direct in-process
RPC dispatch (no sockets required) and verify the full store → retrieve
path that the existing unit tests do not cover:

  test_dht.py::test_multiple_dht_nodes   — only tests find_node, not store/find_value
  test_dht.py::test_store_and_find_value_async — single-node, mocked remote

Milestone 5 adds:
  1. Two-DHT cross-node store/find_value (pure DHT layer)
  2. Three-DHT Kademlia routing (value stored on closest, retrieved by third)
  3. TTL expiry across nodes
  4. Orchestrator.broadcast_peer_result() + fetch_peer_results() over wired DHTs
  5. Orchestrator.sync_peer_results_from_dht() end-to-end
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import pytest

from crypto import NodeIdentity
from p2p.dht import DHT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dht() -> DHT:
    return DHT(NodeIdentity())


def _dispatch(target_dht: DHT, request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronously dispatch a DHT wire-protocol request to *target_dht*'s
    handle_* methods and return a response envelope.

    This replaces the real WebSocket send/receive with a direct in-memory
    call — the protocol shape is identical.
    """
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "dht_find_node":
        result = target_dht.handle_find_node(params["target_id"])
    elif method == "dht_find_value":
        result = target_dht.handle_find_value(params["key"])
    elif method == "dht_store":
        result = target_dht.handle_store(params["key"], params["value"], params["ttl"])
    else:
        return {"error": {"code": -32601, "message": f"Unknown DHT method: {method}"}}

    return {"result": result}


def _wire(dht_a: DHT, dht_b: DHT) -> None:
    """
    Bidirectionally wire two DHT instances so that each can query the other.
    After wiring, each node knows the other's address in its routing table.
    """
    dht_a.add_node(dht_b.node_id, "ws://node-b:8000")
    dht_b.add_node(dht_a.node_id, "ws://node-a:8000")

    async def a_calls_b(node_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        return _dispatch(dht_b, request)

    async def b_calls_a(node_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        return _dispatch(dht_a, request)

    dht_a.rpc_handler = a_calls_b
    dht_b.rpc_handler = b_calls_a


def _wire_mesh(*dhts: DHT) -> None:
    """
    Fully connect N DHT instances: every pair can reach every other.
    Each DHT gets a single rpc_handler that dispatches to any known node_id.
    Replaces repeated _wire() calls which would overwrite each other's handler.
    """
    dht_map: Dict[str, DHT] = {d.node_id: d for d in dhts}
    for dht in dhts:
        for other in dhts:
            if other.node_id != dht.node_id:
                dht.add_node(other.node_id, f"ws://mesh-{other.node_id[:8]}:8000")

    for dht in dhts:
        def _make_handler(dm: Dict[str, DHT]):
            async def rpc(node_id: str, req: Dict[str, Any]) -> Dict[str, Any]:
                target = dm.get(node_id)
                if not target:
                    return {"error": {"code": -32601, "message": f"Unknown node: {node_id[:8]}"}}
                return _dispatch(target, req)
            return rpc
        dht.rpc_handler = _make_handler(dht_map)


# ---------------------------------------------------------------------------
# Pure DHT layer tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_node_store_and_retrieve():
    """
    DHT A stores a value.  After clearing A's local copy the value is
    retrieved from DHT B via the iterative find_value lookup.
    """
    dht_a = _make_dht()
    dht_b = _make_dht()
    _wire(dht_a, dht_b)

    key = "result:task-x:peer-a"
    value = {"peerId": "peer-a", "score": 42}

    success = await dht_a.store(key, value, ttl=3600)
    assert success, "store must succeed when at least one remote node is reachable"

    # Prove the value left A (clear local copy) so retrieval must go to B.
    assert key in dht_a.storage, "store() must also persist locally"
    del dht_a.storage[key]

    retrieved = await dht_a.find_value(key)
    assert retrieved == value, "find_value must retrieve the value from the remote node"


@pytest.mark.asyncio
async def test_cross_node_store_multiple_keys():
    """Multiple independent key/value pairs can be stored and retrieved."""
    dht_a = _make_dht()
    dht_b = _make_dht()
    _wire(dht_a, dht_b)

    pairs = {
        "result:task-1:peer-a": {"data": 1},
        "result:task-2:peer-b": {"data": 2},
        "consensus:task-1": {"accepted": True},
    }

    for key, value in pairs.items():
        ok = await dht_a.store(key, value, ttl=3600)
        assert ok, f"store failed for key '{key}'"

    # Clear A's local cache entirely
    dht_a.storage.clear()

    for key, expected in pairs.items():
        result = await dht_a.find_value(key)
        assert result == expected, f"wrong value for key '{key}'"


@pytest.mark.asyncio
async def test_find_value_returns_none_for_unknown_key():
    """find_value must return None when no node holds the key."""
    dht_a = _make_dht()
    dht_b = _make_dht()
    _wire(dht_a, dht_b)

    result = await dht_a.find_value("nonexistent:key")
    assert result is None


@pytest.mark.asyncio
async def test_ttl_expiry_not_returned():
    """A value whose TTL has already elapsed must not be returned."""
    dht_a = _make_dht()
    dht_b = _make_dht()
    _wire(dht_a, dht_b)

    key = "result:task-ttl:peer-x"
    value = {"score": 9}

    # Store with TTL in the past — simulate an already-expired entry by writing
    # directly to storage with an elapsed expiry timestamp.
    dht_b.storage[key] = (value, time.time() - 1)  # expired 1 second ago
    dht_a.storage.pop(key, None)  # ensure A doesn't have a local copy

    result = await dht_a.find_value(key)
    assert result is None, "expired values must not be returned"


@pytest.mark.asyncio
async def test_three_node_routing_stores_on_closest():
    """
    Three DHT nodes in a line: A — B — C.
    A stores a value; because B is the only peer A knows directly, the value
    is forwarded to B.  C (which only knows B) retrieves it via B.
    """
    dht_a = _make_dht()
    dht_b = _make_dht()
    dht_c = _make_dht()

    # Fully wire all three so each can reach every other.
    _wire_mesh(dht_a, dht_b, dht_c)

    key = "result:task-3node:peer-a"
    value = {"route": "A-B-C"}

    await dht_a.store(key, value, ttl=3600)
    # Clear A's own local copy so it cannot serve the request.
    del dht_a.storage[key]

    # C retrieves via find_value — must route through B.
    result = await dht_c.find_value(key)
    assert result == value


@pytest.mark.asyncio
async def test_store_idempotent():
    """Storing the same key twice replaces the old value (last-write wins)."""
    dht_a = _make_dht()
    dht_b = _make_dht()
    _wire(dht_a, dht_b)

    key = "result:task-idem:peer-a"
    await dht_a.store(key, {"v": 1}, ttl=3600)
    await dht_a.store(key, {"v": 2}, ttl=3600)

    dht_a.storage.clear()
    result = await dht_a.find_value(key)
    assert result == {"v": 2}, "second store must overwrite the first"


# ---------------------------------------------------------------------------
# Orchestrator-level DHT integration tests
# ---------------------------------------------------------------------------


def _make_unique_pgp_key(seed: str) -> str:
    """
    Produce a syntactically valid fake PGP public key whose payload is
    sha256(seed).  Different seeds → different key bytes → different peer_ids.
    """
    import base64
    import hashlib
    payload = base64.b64encode(hashlib.sha256(seed.encode()).digest()).decode()
    return "\n".join([
        "-----BEGIN PGP PUBLIC KEY BLOCK-----",
        payload,
        "=xxxx",
        "-----END PGP PUBLIC KEY BLOCK-----",
    ])


def _make_orchestrator_with_dht(root: Path, name: str = "node"):
    """
    Build an Orchestrator with a unique PGP identity (keyed by *name*) and
    return (orchestrator, dht).

    Each call with a different *name* produces a distinct peer_id, which is
    required for multi-node integration tests where results are keyed by
    peer_id in the DHT.

    SovereignDiscovery creates a DHT automatically (stored as _dht); we
    return that instance so the caller can wire nodes together.
    """
    from orchestrator import Orchestrator

    data_dir = root / "data"
    vault_dir = data_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "public_key.asc").write_text(
        _make_unique_pgp_key(name), encoding="utf-8"
    )
    orc = Orchestrator(data_dir=data_dir)
    dht = orc.discovery._dht
    assert dht is not None, "SovereignDiscovery must create a DHT in __init__"
    return orc, dht


@pytest.mark.asyncio
async def test_orchestrator_broadcast_fetch_via_dht(tmp_path):
    """
    Orchestrator A computes a task, calls broadcast_peer_result() which stores
    the result in the DHT.  Orchestrator B calls fetch_peer_results() and
    retrieves A's proof over the wired DHT — without any file-based IPC.
    """
    from compute import generate_proof_of_logits, synthetic_logits_provider
    from crypto.signing import MessageSigner

    orc_a, dht_a = _make_orchestrator_with_dht(tmp_path / "a", name="node-alpha")
    orc_b, dht_b = _make_orchestrator_with_dht(tmp_path / "b", name="node-beta")
    _wire(dht_a, dht_b)

    task_id = "task-dht-broadcast"
    signer = MessageSigner(orc_a.identity)
    proofs = generate_proof_of_logits(
        model=None,
        input_tokens=[1, 2, 3],
        output_tokens=[4, 5, 6],
        sample_rate=1.0,
        top_k=5,
        seed=7,
        signer=signer,
        logits_provider=synthetic_logits_provider(7),
    )
    peer_result = {
        "peerId": orc_a.peer_id,
        "publicKey": orc_a.identity.serialize_public_key().hex(),
        "proofOfLogits": proofs,
    }

    # A broadcasts.
    success = await orc_a.broadcast_peer_result(task_id, peer_result)
    assert success, "broadcast_peer_result must return True when DHT store succeeds"

    # Clear A's local DHT copy so B must actually go to the network.
    key = f"result:{task_id}:{orc_a.peer_id}"
    dht_a.storage.pop(key, None)

    # B fetches explicitly by task + peer_id.
    results = await orc_b.fetch_peer_results(task_id, [orc_a.peer_id])
    assert results, "fetch_peer_results must return at least one result"
    assert results[0]["peerId"] == orc_a.peer_id
    assert results[0]["proofOfLogits"] == proofs


@pytest.mark.asyncio
async def test_orchestrator_sync_then_consensus(tmp_path):
    """
    Full pipeline over DHT:
    - Three orchestrators each compute the same task.
    - A and B use the same seed (agree); C uses a different seed (disagrees).
    - All three broadcast via DHT.
    - B then syncs peer results from the DHT and runs consensus.
    - Consensus must be accepted with A and B as winners.
    """
    from compute import generate_proof_of_logits, synthetic_logits_provider
    from crypto.signing import MessageSigner
    from discovery import SovereignDiscovery, PeerRecord
    import time as _time

    orc_a, dht_a = _make_orchestrator_with_dht(tmp_path / "a", name="node-alpha")
    orc_b, dht_b = _make_orchestrator_with_dht(tmp_path / "b", name="node-beta")
    orc_c, dht_c = _make_orchestrator_with_dht(tmp_path / "c", name="node-gamma")

    # Fully wire all three DHTs so each can reach every other.
    _wire_mesh(dht_a, dht_b, dht_c)

    task_id = "task-consensus-dht"
    input_tokens = [10, 20, 30]
    output_tokens = [40, 50, 60, 70]

    def _make_result(orc, seed: int) -> Dict[str, Any]:
        signer = MessageSigner(orc.identity)
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
        return {
            "peerId": orc.peer_id,
            "publicKey": orc.identity.serialize_public_key().hex(),
            "proofOfLogits": proofs,
        }

    result_a = _make_result(orc_a, seed=42)
    result_b = _make_result(orc_b, seed=42)   # agrees with A
    result_c = _make_result(orc_c, seed=99)   # disagrees

    # All three broadcast into the DHT.
    await orc_a.broadcast_peer_result(task_id, result_a)
    await orc_b.broadcast_peer_result(task_id, result_b)
    await orc_c.broadcast_peer_result(task_id, result_c)

    # Register A and C as known peers in B's discovery so sync can find them.
    for peer_id in (orc_a.peer_id, orc_c.peer_id):
        orc_b.discovery._peers[peer_id] = PeerRecord(
            peerId=peer_id,
            address="ws://localhost:0",
            protocols=["/project-dawn/1.0"],
            reputationScore=0.5,
            uptime=0.0,
            lastVerified=_time.time(),
            lastSeen=_time.time(),
        )

    # Seed B's outbox with a task file so sync_peer_results_from_dht
    # knows which task to look for.
    (orc_b.outbox_dir / f"{task_id}.json").write_text(
        json.dumps({"taskId": task_id}), encoding="utf-8"
    )

    # B syncs from DHT.
    await orc_b.sync_peer_results_from_dht()

    # B should now have 3 peer result entries for task_id.
    result_file = orc_b.peer_results_dir / f"{task_id}.jsonl"
    assert result_file.exists(), "peer result file must be created after sync"
    lines = [l for l in result_file.read_text().splitlines() if l.strip()]
    assert len(lines) >= 3, f"expected ≥3 results, got {len(lines)}"

    # Run consensus.
    receipts = orc_b.process_peer_results()
    assert receipts, "process_peer_results must produce a receipt"

    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["taskId"] == task_id
    assert receipt["accepted"] is True
    assert set(receipt["winners"]) == {orc_a.peer_id, orc_b.peer_id}
