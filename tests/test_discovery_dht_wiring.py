"""
Tests for the DHT wiring changes introduced in the P2 work:

1. SovereignDiscovery.record_peer() now seeds the DHT routing table.
2. SovereignDiscovery.set_dht() replaces the DHT and seeds it with known peers.
3. End-to-end: two Orchestrators sharing a wired DHT can store and retrieve
   peer results — the same path used by broadcast_peer_result() and
   fetch_peer_results() in the main compute loop.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict

import pytest

from crypto import NodeIdentity
from discovery import SovereignDiscovery
from p2p.dht import DHT


# ---------------------------------------------------------------------------
# Helpers (reuse patterns from test_dht_integration.py)
# ---------------------------------------------------------------------------

def _make_dht(identity: NodeIdentity | None = None) -> DHT:
    return DHT(identity or NodeIdentity())


def _make_discovery(tmp_path: Path, identity: NodeIdentity | None = None) -> SovereignDiscovery:
    ident = identity or NodeIdentity()
    return SovereignDiscovery(identity=ident, data_dir=tmp_path)


def _dispatch(target_dht: DHT, request: Dict[str, Any]) -> Dict[str, Any]:
    method = request.get("method", "")
    params = request.get("params", {})
    if method == "dht_find_node":
        result = target_dht.handle_find_node(params["target_id"])
    elif method == "dht_find_value":
        result = target_dht.handle_find_value(params["key"])
    elif method == "dht_store":
        result = target_dht.handle_store(params["key"], params["value"], params["ttl"])
    else:
        return {"error": {"code": -32601, "message": f"Unknown: {method}"}}
    return {"result": result}


def _wire(dht_a: DHT, dht_b: DHT) -> None:
    dht_a.add_node(dht_b.node_id, "ws://node-b:8000")
    dht_b.add_node(dht_a.node_id, "ws://node-a:8000")

    async def a_calls_b(node_id: str, req: Dict[str, Any]) -> Dict[str, Any]:
        return _dispatch(dht_b, req)

    async def b_calls_a(node_id: str, req: Dict[str, Any]) -> Dict[str, Any]:
        return _dispatch(dht_a, req)

    dht_a.rpc_handler = a_calls_b
    dht_b.rpc_handler = b_calls_a


def _make_unique_pgp_key(seed: str) -> str:
    digest = hashlib.sha256(seed.encode()).digest()
    return base64.b64encode(digest).decode()


# ---------------------------------------------------------------------------
# Unit: record_peer seeds DHT routing table
# ---------------------------------------------------------------------------

def test_record_peer_seeds_dht_routing_table(tmp_path):
    """
    After record_peer(), the peer's node_id should appear in the DHT routing table.
    """
    identity = NodeIdentity()
    disc = _make_discovery(tmp_path, identity)
    dht = disc.get_dht()
    assert dht is not None

    peer_id = NodeIdentity().get_node_id()
    disc.record_peer(
        peer_id=peer_id,
        address="ws://10.0.0.1:8000",
        protocols=["/project-dawn/1.0"],
    )

    # The DHT routing table should now contain the peer.
    closest = dht.get_closest_nodes(peer_id, 1)
    assert any(n.node_id == peer_id for n in closest), \
        "Peer registered via record_peer() must appear in DHT routing table"


def test_record_peer_without_dht_does_not_crash(tmp_path):
    """
    SovereignDiscovery initialised without an identity has no DHT.
    record_peer() must still succeed.
    """
    disc = SovereignDiscovery(identity=None, data_dir=tmp_path)
    assert disc.get_dht() is None

    result = disc.record_peer(
        peer_id="fake-peer",
        address="ws://127.0.0.1:9999",
        protocols=["/project-dawn/1.0"],
    )
    assert result is True  # protocol allowed, no DHT crash


# ---------------------------------------------------------------------------
# Unit: set_dht replaces instance and seeds from known peers
# ---------------------------------------------------------------------------

def test_set_dht_replaces_instance(tmp_path):
    identity = NodeIdentity()
    disc = _make_discovery(tmp_path, identity)
    original_dht = disc.get_dht()

    new_dht = _make_dht()
    disc.set_dht(new_dht)

    assert disc.get_dht() is new_dht
    assert disc.get_dht() is not original_dht


def test_set_dht_seeds_known_peers(tmp_path):
    """
    Peers known to the SovereignDiscovery before set_dht() is called must be
    added to the new DHT routing table.
    """
    identity = NodeIdentity()
    disc = _make_discovery(tmp_path, identity)

    # Record two peers into the discovery cache.
    peer_a_id = NodeIdentity().get_node_id()
    peer_b_id = NodeIdentity().get_node_id()
    disc.record_peer(peer_a_id, "ws://10.0.0.1:8000", ["/project-dawn/1.0"])
    disc.record_peer(peer_b_id, "ws://10.0.0.2:8000", ["/project-dawn/1.0"])

    # Replace with a brand-new DHT that knows nothing.
    new_dht = _make_dht(identity)
    disc.set_dht(new_dht)

    closest = new_dht.get_closest_nodes(peer_a_id, 20)
    known_ids = {n.node_id for n in closest}
    assert peer_a_id in known_ids, "peer_a must be in new DHT after set_dht()"
    assert peer_b_id in known_ids, "peer_b must be in new DHT after set_dht()"


# ---------------------------------------------------------------------------
# Integration: Orchestrator broadcast/fetch via shared wired DHT
# ---------------------------------------------------------------------------

def _make_orchestrator_pair(tmp_path: Path):
    """
    Create two Orchestrators whose SovereignDiscovery DHTs are wired together
    using in-process dispatch (same pattern as test_dht_integration.py).

    Returns (orc_a, orc_b, dht_a, dht_b).
    """
    from orchestrator import Orchestrator
    from crypto.signing import derive_peer_id_from_pgp_public_key_file
    import os

    def _setup_node(name: str) -> tuple:
        root = tmp_path / name
        vault = root / "vault"
        vault.mkdir(parents=True)
        pgp_content = _make_unique_pgp_key(name)
        pgp_path = vault / "public_key.asc"
        pgp_path.write_text(pgp_content, encoding="utf-8")
        return root, pgp_path

    root_a, pgp_a = _setup_node("node-a")
    root_b, pgp_b = _setup_node("node-b")

    orc_a = Orchestrator(data_dir=root_a, pgp_public_key_path=pgp_a, enable_mdns=False)
    orc_b = Orchestrator(data_dir=root_b, pgp_public_key_path=pgp_b, enable_mdns=False)

    dht_a = orc_a.discovery._dht
    dht_b = orc_b.discovery._dht
    assert dht_a is not None
    assert dht_b is not None

    _wire(dht_a, dht_b)
    return orc_a, orc_b, dht_a, dht_b


@pytest.mark.asyncio
async def test_shared_dht_broadcast_and_fetch(tmp_path):
    """
    Orchestrator A stores a peer result via broadcast_peer_result().
    Orchestrator B can retrieve it via fetch_peer_results() using the wired DHT.
    This is the core of the broadcast→consensus path.
    """
    orc_a, orc_b, dht_a, dht_b = _make_orchestrator_pair(tmp_path)

    task_id = "task-wired-dht-001"
    peer_result = {
        "peerId": orc_a.peer_id,
        "publicKey": orc_a.identity.serialize_public_key().hex(),
        "proofOfLogits": [{"index": 0, "logitHash": "aa", "nodeSignature": "bb", "timestamp": time.time()}],
    }

    # A broadcasts the result.
    ok = await orc_a.broadcast_peer_result(task_id, peer_result)
    assert ok, "broadcast_peer_result() must return True when DHT store succeeds"

    # B fetches it.
    results = await orc_b.fetch_peer_results(task_id, [orc_a.peer_id])
    assert len(results) == 1
    assert results[0]["peerId"] == orc_a.peer_id


@pytest.mark.asyncio
async def test_set_dht_bridge_then_broadcast_and_fetch(tmp_path):
    """
    Simulate the server_p2p.py bridge: create two Orchestrators, then
    replace one's DHT with a shared wired DHT (as set_dht() does).
    Verify broadcast/fetch works through the replaced DHT.
    """
    orc_a, orc_b, dht_a, dht_b = _make_orchestrator_pair(tmp_path)

    # Simulate the bridge: replace orc_b's DHT with a fresh wired instance.
    new_dht_b = _make_dht()
    new_dht_b.add_node(dht_a.node_id, "ws://node-a:8000")
    dht_a.add_node(new_dht_b.node_id, "ws://node-b-new:8000")

    async def a_calls_new_b(node_id: str, req: Dict[str, Any]) -> Dict[str, Any]:
        return _dispatch(new_dht_b, req)

    async def new_b_calls_a(node_id: str, req: Dict[str, Any]) -> Dict[str, Any]:
        return _dispatch(dht_a, req)

    dht_a.rpc_handler = a_calls_new_b
    new_dht_b.rpc_handler = new_b_calls_a

    orc_b.discovery.set_dht(new_dht_b)

    task_id = "task-bridge-replace-001"
    peer_result = {
        "peerId": orc_b.peer_id,
        "publicKey": orc_b.identity.serialize_public_key().hex(),
        "proofOfLogits": [],
    }
    ok = await orc_b.broadcast_peer_result(task_id, peer_result)
    assert ok

    results = await orc_a.fetch_peer_results(task_id, [orc_b.peer_id])
    assert len(results) == 1


@pytest.mark.asyncio
async def test_discovery_peers_enter_dht_when_recorded(tmp_path):
    """
    When a peer is recorded via SovereignDiscovery.record_peer(), the DHT
    routing table should contain it so subsequent store() calls can route to it.
    """
    identity_a = NodeIdentity()
    disc_a = _make_discovery(tmp_path / "disc-a", identity_a)
    dht_a = disc_a.get_dht()

    identity_b = NodeIdentity()
    disc_b = _make_discovery(tmp_path / "disc-b", identity_b)
    dht_b = disc_b.get_dht()

    # Wire the RPC handlers so they can reach each other.
    async def a_calls_b(node_id: str, req: Dict[str, Any]) -> Dict[str, Any]:
        return _dispatch(dht_b, req)

    async def b_calls_a(node_id: str, req: Dict[str, Any]) -> Dict[str, Any]:
        return _dispatch(dht_a, req)

    dht_a.rpc_handler = a_calls_b
    dht_b.rpc_handler = b_calls_a

    # Record each other as peers — this should also seed the routing table.
    disc_a.record_peer(identity_b.get_node_id(), "ws://node-b:8000", ["/project-dawn/1.0"])
    disc_b.record_peer(identity_a.get_node_id(), "ws://node-a:8000", ["/project-dawn/1.0"])

    # Now a DHT store from A should reach B.
    key = "test:discovery-record-seeding"
    value = {"hello": "from A"}
    ok = await dht_a.store(key, value, ttl=3600)
    assert ok

    # B should be able to retrieve it.
    retrieved = await dht_b.find_value(key)
    assert retrieved == value
