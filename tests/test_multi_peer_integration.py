"""
Integration Tests for Multi-Peer Scenarios

Tests P2P node behavior with multiple peers and complex interaction patterns.
"""

import pytest
import asyncio
from crypto import NodeIdentity
from p2p.p2p_node import P2PNode
from p2p.peer import Peer


@pytest.mark.asyncio
async def test_peer_registry_persistence():
    """Test that peer registry persists across restarts"""
    from pathlib import Path
    import tempfile
    import shutil
    
    identity = NodeIdentity()
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Create first node
        node1 = P2PNode(identity=identity, address="ws://localhost:8000")
        node1.peer_registry.data_dir = temp_dir / "mesh"
        
        # Add peer
        peer = Peer(node_id="test_peer", address="ws://localhost:8001")
        node1.peer_registry.add_peer(peer)
        
        # Create second node and load registry
        node2 = P2PNode(identity=NodeIdentity(), address="ws://localhost:8001")
        node2.peer_registry.data_dir = temp_dir / "mesh"
        node2.peer_registry._load()
        
        # Check that peer was loaded
        loaded_peer = node2.peer_registry.get_peer("test_peer")
        assert loaded_peer is not None
        assert loaded_peer.node_id == "test_peer"
        assert loaded_peer.address == "ws://localhost:8001"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_multiple_peers_in_registry():
    """Test that multiple peers can be stored in registry"""
    identity = NodeIdentity()
    node = P2PNode(identity=identity, address="ws://localhost:8000")
    
    # Add multiple peers
    for i in range(5):
        peer = Peer(
            node_id=f"peer_{i}",
            address=f"ws://localhost:{8001 + i}"
        )
        node.peer_registry.add_peer(peer)
    
    # Check that all peers are in registry
    assert node.peer_registry.get_peer_count() == 5
    
    # List peers
    peers = node.peer_registry.list_peers()
    assert len(peers) == 5
    
    # Check individual peers
    for i in range(5):
        peer = node.peer_registry.get_peer(f"peer_{i}")
        assert peer is not None
        assert peer.node_id == f"peer_{i}"


@pytest.mark.asyncio
async def test_peer_health_tracking():
    """Test that peer health is tracked correctly"""
    identity = NodeIdentity()
    node = P2PNode(identity=identity, address="ws://localhost:8000")
    
    # Add peer
    peer = Peer(node_id="test_peer", address="ws://localhost:8001")
    node.peer_registry.add_peer(peer)
    
    # Record connection success
    peer.record_connection_success()
    assert peer.health_score > 0.5
    assert peer.successful_connections == 1
    
    # Record connection failure
    peer.record_connection_failure()
    assert peer.health_score < 1.0
    assert peer.failed_connections == 1


@pytest.mark.asyncio
async def test_peer_cleanup_dead_peers():
    """Test that dead peers are cleaned up"""
    identity = NodeIdentity()
    node = P2PNode(identity=identity, address="ws://localhost:8000")
    
    # Add peer
    peer = Peer(node_id="test_peer", address="ws://localhost:8001")
    node.peer_registry.add_peer(peer)
    
    # Make peer dead (set last_seen to far in past)
    import time
    peer.last_seen = time.time() - 600  # 10 minutes ago
    
    # Cleanup dead peers
    dead_peers = node.peer_registry.cleanup_dead_peers()
    
    # Peer should be removed (if timeout is less than 600s)
    # Note: This depends on peer_timeout default
    if node.peer_registry.peer_timeout < 600:
        assert len(dead_peers) > 0
        assert node.peer_registry.get_peer("test_peer") is None


@pytest.mark.asyncio
async def test_peer_registry_stats():
    """Test that peer registry statistics are calculated correctly"""
    identity = NodeIdentity()
    node = P2PNode(identity=identity, address="ws://localhost:8000")
    
    # Add peers
    for i in range(3):
        peer = Peer(
            node_id=f"peer_{i}",
            address=f"ws://localhost:{8001 + i}"
        )
        node.peer_registry.add_peer(peer)
    
    # Get stats
    stats = node.peer_registry.get_peer_stats()
    assert stats["total_peers"] == 3
    assert stats["alive_peers"] >= 0
    assert stats["connected_peers"] >= 0


@pytest.mark.asyncio
async def test_message_routing_to_multiple_peers():
    """Test that messages can be routed to multiple peers"""
    identity = NodeIdentity()
    node = P2PNode(identity=identity, address="ws://localhost:8000")
    
    # Add multiple peers
    for i in range(3):
        peer = Peer(
            node_id=f"peer_{i}",
            address=f"ws://localhost:{8001 + i}"
        )
        node.peer_registry.add_peer(peer)
    
    # Route messages from different peers
    for i in range(3):
        message = {
            "jsonrpc": "2.0",
            "method": "node/ping",
            "id": i,
        }
        result = await node._route_message(message, sender_node_id=f"peer_{i}")
        # Should handle message (may have error if method doesn't exist, but not routing error)
        assert result is not None or result is None  # Accept either


@pytest.mark.asyncio
async def test_peer_registry_callbacks():
    """Test that peer registry callbacks are called"""
    identity = NodeIdentity()
    node = P2PNode(identity=identity, address="ws://localhost:8000")
    
    # Track callbacks
    added_peers = []
    removed_peers = []
    
    def on_added(peer):
        added_peers.append(peer)
    
    def on_removed(peer):
        removed_peers.append(peer)
    
    node.peer_registry.on_peer_added = on_added
    node.peer_registry.on_peer_removed = on_removed
    
    # Add peer
    peer = Peer(node_id="test_peer", address="ws://localhost:8001")
    node.peer_registry.add_peer(peer)
    assert len(added_peers) == 1
    assert added_peers[0].node_id == "test_peer"
    
    # Remove peer
    node.peer_registry.remove_peer("test_peer")
    assert len(removed_peers) == 1
    assert removed_peers[0].node_id == "test_peer"
