"""
Tests for the DHT ↔ WebSocket transport bridge.

These tests cover the _handle_dht_rpc method which is the outbound side of the
DHT wiring: when the Kademlia algorithm wants to query a remote node it calls
rpc_handler(node_id, request), which must send the request over the encrypted
WebSocket transport and return the remote node's response.

The inbound side (handling dht_find_node / dht_find_value / dht_store messages
that arrive from peers) is exercised via _handle_node_method and is covered by
the routing tests below.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crypto import NodeIdentity
from p2p.dht import DHT, DHTNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_identity() -> NodeIdentity:
    return NodeIdentity()


def _make_p2p_node(enable_dht: bool = False):
    """Return a P2PNode with mocked security / registry dependencies."""
    from p2p.p2p_node import P2PNode

    identity = _make_identity()
    with (
        patch("p2p.p2p_node.TrustManager"),
        patch("p2p.p2p_node.AuthManager"),
        patch("p2p.p2p_node.AuditLogger"),
        patch("p2p.p2p_node.PeerValidator"),
        patch("p2p.p2p_node.PeerRegistry"),
        patch("p2p.p2p_node.DistributedAgentRegistry"),
        patch("p2p.p2p_node.DistributedTaskRegistry"),
        patch("p2p.p2p_node.register_metrics"),
        patch("p2p.p2p_node.RateLimiter"),
        patch("p2p.p2p_node.CircuitBreaker"),
        patch("p2p.p2p_node.PeerDiscovery") as mock_discovery_cls,
    ):
        mock_discovery = MagicMock()
        mock_discovery.get_dht.return_value = None
        mock_discovery_cls.return_value = mock_discovery

        node = P2PNode(
            identity=identity,
            address="ws://localhost:8001",
            enable_encryption=False,
            enable_dht=enable_dht,
        )
        node._mock_discovery = mock_discovery
        return node


# ---------------------------------------------------------------------------
# Tests: _handle_dht_rpc (outbound)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dht_rpc_sends_and_returns_response():
    """Happy path: request is forwarded to the connected peer; response is returned."""
    node = _make_p2p_node()

    remote_node_id = "a" * 64
    expected_response = {
        "jsonrpc": "2.0",
        "id": "will-be-replaced-by-actual-id",
        "result": {"nodes": []},
    }

    # Simulate a transport that "receives" the response by resolving the future.
    sent_messages: List[str] = []

    async def fake_send(msg: str) -> None:
        sent_messages.append(msg)
        # Parse the outbound message to extract the request_id, then resolve the future.
        data = json.loads(msg)
        request_id = data["id"]
        future = node.pending_requests.get(request_id)
        if future and not future.done():
            response = dict(expected_response)
            response["id"] = request_id
            future.set_result(response)

    mock_transport = MagicMock()
    mock_transport.send = fake_send
    node.peer_connections[remote_node_id] = mock_transport

    request = {"method": "dht_find_node", "params": {"target_id": "b" * 64}}
    result = await node._handle_dht_rpc(remote_node_id, request)

    assert len(sent_messages) == 1
    sent = json.loads(sent_messages[0])
    assert sent["method"] == "dht_find_node"
    assert sent["params"]["target_id"] == "b" * 64
    assert "id" in sent

    assert result.get("result", {}).get("nodes") == []
    assert "error" not in result


@pytest.mark.asyncio
async def test_dht_rpc_returns_error_when_peer_not_found():
    """If the peer isn't in peer_connections or peer_registry, return an error."""
    node = _make_p2p_node()

    # peer_registry.get_peer returns None
    node.peer_registry.get_peer.return_value = None
    # DHT routing table also empty
    node._mock_discovery.get_dht.return_value = None

    request = {"method": "dht_find_node", "params": {"target_id": "c" * 64}}
    result = await node._handle_dht_rpc("d" * 64, request)

    assert "error" in result
    assert result["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_dht_rpc_resolves_address_from_routing_table():
    """If peer not in registry but IS in DHT routing table, use the address from there."""
    node = _make_p2p_node()

    remote_node_id = "e" * 64
    remote_address = "ws://peer-via-dht:8000"

    # Peer not in registry
    node.peer_registry.get_peer.return_value = None

    # DHT routing table has the node
    mock_dht = MagicMock()
    candidate = DHTNode(node_id=remote_node_id, address=remote_address)
    mock_dht.get_closest_nodes.return_value = [candidate]
    node._mock_discovery.get_dht.return_value = mock_dht

    # connect_to_peer succeeds and adds to peer_connections
    good_response = {"jsonrpc": "2.0", "id": "x", "result": {"nodes": []}}

    async def fake_connect(peer) -> bool:
        assert peer.node_id == remote_node_id
        assert peer.address == remote_address
        mock_transport = MagicMock()
        async def fake_send(msg: str) -> None:
            data = json.loads(msg)
            fut = node.pending_requests.get(data["id"])
            if fut and not fut.done():
                r = dict(good_response)
                r["id"] = data["id"]
                fut.set_result(r)
        mock_transport.send = fake_send
        node.peer_connections[remote_node_id] = mock_transport
        return True

    node.connect_to_peer = fake_connect

    request = {"method": "dht_find_node", "params": {"target_id": "f" * 64}}
    result = await node._handle_dht_rpc(remote_node_id, request)

    assert "error" not in result
    assert result.get("result", {}).get("nodes") == []


@pytest.mark.asyncio
async def test_dht_rpc_timeout():
    """If the remote peer doesn't respond in time, return a timeout error."""
    node = _make_p2p_node()

    remote_node_id = "0" * 64

    # Transport.send does nothing (no response ever arrives)
    mock_transport = MagicMock()
    mock_transport.send = AsyncMock()
    node.peer_connections[remote_node_id] = mock_transport

    request = {"method": "dht_find_node", "params": {"target_id": "1" * 64}}

    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        result = await node._handle_dht_rpc(remote_node_id, request)

    assert "error" in result
    assert result["error"]["code"] == -32603
    assert "timeout" in result["error"]["message"].lower()


@pytest.mark.asyncio
async def test_dht_rpc_failed_connection():
    """If connect_to_peer fails, return a connection error."""
    node = _make_p2p_node()

    remote_node_id = "2" * 64
    node.peer_registry.get_peer.return_value = None
    node._mock_discovery.get_dht.return_value = None

    # Provide a peer via registry so connect_to_peer is attempted
    from p2p.peer import Peer
    mock_peer = Peer(node_id=remote_node_id, address="ws://unreachable:9999")
    node.peer_registry.get_peer.return_value = mock_peer

    async def fail_connect(peer) -> bool:
        return False

    node.connect_to_peer = fail_connect

    request = {"method": "dht_store", "params": {"key": "k", "value": "v"}}
    result = await node._handle_dht_rpc(remote_node_id, request)

    assert "error" in result
    assert result["error"]["code"] == -32603


# ---------------------------------------------------------------------------
# Tests: inbound DHT method handling via _handle_node_method
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inbound_dht_find_node_when_dht_enabled():
    """Inbound dht_find_node is dispatched to the local DHT and returns closest nodes."""
    node = _make_p2p_node(enable_dht=True)

    target_id = "9" * 64
    closest = [DHTNode(node_id="a" * 64, address="ws://nodeA:8000")]

    mock_dht = MagicMock()
    mock_dht.handle_find_node.return_value = {"nodes": [n.__dict__ for n in closest]}
    node._mock_discovery.get_dht.return_value = mock_dht

    result = await node._handle_node_method("dht_find_node", {"target_id": target_id})

    mock_dht.handle_find_node.assert_called_once_with(target_id)
    assert "result" in result
    assert "nodes" in result["result"]


@pytest.mark.asyncio
async def test_inbound_dht_find_node_when_dht_disabled():
    """If DHT is disabled, inbound dht_find_node returns a proper error."""
    node = _make_p2p_node(enable_dht=False)
    node._mock_discovery.get_dht.return_value = None

    result = await node._handle_node_method("dht_find_node", {"target_id": "a" * 64})

    assert "error" in result
    assert result["error"]["code"] == -32601


# ---------------------------------------------------------------------------
# Tests: DHT bootstrap seeding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dht_seeded_from_bootstrap_peers():
    """Bootstrap peers discovered at startup are added to the DHT routing table."""
    from p2p.peer import Peer

    node = _make_p2p_node(enable_dht=True)

    boot_peer = Peer(node_id="b" * 64, address="ws://bootstrap:8000")
    node._mock_discovery.discover_bootstrap = AsyncMock(return_value=[boot_peer])
    node._mock_discovery.start_mdns = MagicMock()
    node._mock_discovery.start_gossip = MagicMock()
    node._mock_discovery.register_mdns_service = MagicMock()

    mock_dht = MagicMock()
    node._mock_discovery.get_dht.return_value = mock_dht
    node._mock_discovery.start_dht = MagicMock()
    node._mock_discovery.discover_peers_dht = AsyncMock(return_value=[])

    # Patch out the blocking server.start call
    mock_server = AsyncMock()
    mock_server.start = AsyncMock()
    with (
        patch("p2p.p2p_node.EncryptedWebSocketServer", return_value=mock_server),
        patch("asyncio.to_thread", new=AsyncMock(return_value=None)),
        patch("asyncio.create_task"),
    ):
        # Only run the setup portion of start() before the blocking server call
        bootstrap_peers = await node.discovery.discover_bootstrap()
        dht = node.discovery.get_dht()
        if dht:
            for peer in bootstrap_peers:
                dht.add_node(peer.node_id, peer.address)

    mock_dht.add_node.assert_called_once_with(boot_peer.node_id, boot_peer.address)
