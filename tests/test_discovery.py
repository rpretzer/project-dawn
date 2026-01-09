"""
Tests for peer discovery system
"""

import pytest
import asyncio
import time
from p2p import Peer, PeerRegistry, BootstrapDiscovery, GossipDiscovery, PeerDiscovery
from crypto import NodeIdentity


class TestPeer:
    """Test Peer representation"""
    
    def test_create_peer(self):
        """Test creating a peer"""
        peer = Peer(
            node_id="test_node_123",
            address="ws://localhost:8000"
        )
        
        assert peer.node_id == "test_node_123"
        assert peer.address == "ws://localhost:8000"
        assert not peer.connected
        assert peer.is_alive()
    
    def test_peer_activity(self):
        """Test peer activity tracking"""
        peer = Peer(
            node_id="test_node",
            address="ws://localhost:8000"
        )
        
        initial_last_seen = peer.last_seen
        time.sleep(0.1)
        peer.update_activity()
        
        assert peer.last_seen > initial_last_seen
    
    def test_peer_is_alive(self):
        """Test peer alive check"""
        peer = Peer(
            node_id="test_node",
            address="ws://localhost:8000"
        )
        
        assert peer.is_alive(timeout=1.0)
        
        # Make peer appear dead
        peer.last_seen = time.time() - 1000
        assert not peer.is_alive(timeout=1.0)
    
    def test_peer_health_tracking(self):
        """Test peer health score tracking"""
        peer = Peer(
            node_id="test_node",
            address="ws://localhost:8000"
        )
        
        initial_score = peer.health_score
        assert initial_score == 1.0  # Starts at max
        
        # Record a failure first to lower score
        peer.record_connection_failure()
        assert peer.health_score < initial_score
        assert peer.failed_connections == 1
        
        # Record success to increase score
        score_after_failure = peer.health_score
        peer.record_connection_success()
        assert peer.health_score > score_after_failure
        assert peer.successful_connections == 1
        
        # Score should be capped at 1.0
        for _ in range(10):
            peer.record_connection_success()
        assert peer.health_score <= 1.0
    
    def test_peer_serialization(self):
        """Test peer serialization"""
        peer = Peer(
            node_id="test_node",
            address="ws://localhost:8000",
            agents=["agent1", "agent2"],
        )
        
        peer_dict = peer.to_dict()
        assert peer_dict["node_id"] == "test_node"
        assert peer_dict["address"] == "ws://localhost:8000"
        assert len(peer_dict["agents"]) == 2
        
        # Deserialize
        peer2 = Peer.from_dict(peer_dict)
        assert peer2.node_id == peer.node_id
        assert peer2.address == peer.address
        assert peer2.agents == peer.agents


class TestPeerRegistry:
    """Test PeerRegistry"""
    
    def test_add_peer(self):
        """Test adding peer to registry"""
        registry = PeerRegistry()
        
        peer = Peer(
            node_id="test_node",
            address="ws://localhost:8000"
        )
        
        registry.add_peer(peer)
        assert registry.has_peer("test_node")
        assert registry.get_peer_count() == 1
    
    def test_remove_peer(self):
        """Test removing peer from registry"""
        registry = PeerRegistry()
        
        peer = Peer(node_id="test_node", address="ws://localhost:8000")
        registry.add_peer(peer)
        
        removed = registry.remove_peer("test_node")
        assert removed is not None
        assert removed.node_id == "test_node"
        assert not registry.has_peer("test_node")
    
    def test_list_peers(self):
        """Test listing peers"""
        registry = PeerRegistry()
        
        peer1 = Peer(node_id="node1", address="ws://localhost:8000")
        peer2 = Peer(node_id="node2", address="ws://localhost:8001")
        
        registry.add_peer(peer1)
        registry.add_peer(peer2)
        
        peers = registry.list_peers()
        assert len(peers) == 2
    
    def test_list_alive_peers(self):
        """Test listing alive peers"""
        registry = PeerRegistry()
        
        peer1 = Peer(node_id="node1", address="ws://localhost:8000")
        peer2 = Peer(node_id="node2", address="ws://localhost:8001")
        peer2.last_seen = time.time() - 1000  # Make dead
        
        registry.add_peer(peer1)
        registry.add_peer(peer2)
        
        alive = registry.list_alive_peers()
        assert len(alive) == 1
        assert alive[0].node_id == "node1"
    
    def test_cleanup_dead_peers(self):
        """Test cleaning up dead peers"""
        registry = PeerRegistry(peer_timeout=1.0)
        
        peer1 = Peer(node_id="node1", address="ws://localhost:8000")
        peer2 = Peer(node_id="node2", address="ws://localhost:8001")
        peer2.last_seen = time.time() - 1000  # Make dead
        
        registry.add_peer(peer1)
        registry.add_peer(peer2)
        
        dead = registry.cleanup_dead_peers()
        assert len(dead) == 1
        assert dead[0].node_id == "node2"
        assert registry.get_peer_count() == 1
    
    def test_peer_stats(self):
        """Test peer registry statistics"""
        registry = PeerRegistry()
        
        peer1 = Peer(node_id="node1", address="ws://localhost:8000")
        peer2 = Peer(node_id="node2", address="ws://localhost:8001")
        
        registry.add_peer(peer1)
        registry.add_peer(peer2)
        
        stats = registry.get_peer_stats()
        assert stats["total_peers"] == 2
        assert stats["alive_peers"] == 2


class TestBootstrapDiscovery:
    """Test BootstrapDiscovery"""
    
    @pytest.mark.asyncio
    async def test_discover(self):
        """Test bootstrap discovery"""
        registry = PeerRegistry()
        bootstrap = BootstrapDiscovery(
            bootstrap_nodes=["ws://bootstrap1:8000", "ws://bootstrap2:8000"],
            peer_registry=registry
        )
        
        discovered = await bootstrap.discover()
        
        # Should discover bootstrap nodes
        assert len(discovered) > 0
        assert registry.get_peer_count() > 0


class TestGossipDiscovery:
    """Test GossipDiscovery"""
    
    def test_create_announcement(self):
        """Test creating gossip announcement"""
        registry = PeerRegistry()
        gossip = GossipDiscovery(registry)
        
        # Add some peers
        peer1 = Peer(node_id="node1", address="ws://localhost:8000")
        peer2 = Peer(node_id="node2", address="ws://localhost:8001")
        registry.add_peer(peer1)
        registry.add_peer(peer2)
        
        announcement = gossip._create_announcement()
        
        assert announcement["type"] == "gossip_announcement"
        assert "timestamp" in announcement
        assert "peers" in announcement
        assert len(announcement["peers"]) > 0
    
    def test_handle_announcement(self):
        """Test handling gossip announcement"""
        registry = PeerRegistry()
        gossip = GossipDiscovery(registry)
        
        # Create announcement
        peer_data = {
            "node_id": "remote_node",
            "address": "ws://remote:8000",
            "connected": False,
            "last_seen": time.time(),
            "first_seen": time.time(),
            "agents": [],
            "tools": [],
            "resources": [],
            "prompts": [],
            "metadata": {},
            "health_score": 1.0,
            "connection_attempts": 0,
            "successful_connections": 0,
            "failed_connections": 0,
        }
        
        announcement = {
            "type": "gossip_announcement",
            "timestamp": time.time(),
            "peers": [peer_data],
        }
        
        gossip.handle_announcement(announcement, "sender_node")
        
        # Should have added peer
        assert registry.has_peer("remote_node")
    
    @pytest.mark.asyncio
    async def test_announce_loop(self):
        """Test announcement loop"""
        registry = PeerRegistry()
        gossip = GossipDiscovery(registry, announce_interval=0.1)
        
        announcements = []
        
        async def announce_callback(msg):
            announcements.append(msg)
        
        gossip.start(announce_callback)
        
        # Wait for at least one announcement
        await asyncio.sleep(0.15)
        
        gossip.stop()
        
        assert len(announcements) > 0
        assert announcements[0]["type"] == "gossip_announcement"


class TestPeerDiscovery:
    """Test unified PeerDiscovery"""
    
    def test_initialization(self):
        """Test PeerDiscovery initialization"""
        registry = PeerRegistry()
        discovery = PeerDiscovery(
            registry,
            bootstrap_nodes=["ws://bootstrap:8000"],
            enable_mdns=False,  # Disable for testing
            enable_gossip=True
        )
        
        assert discovery.bootstrap is not None
        assert discovery.gossip is not None
    
    @pytest.mark.asyncio
    async def test_bootstrap_discovery(self):
        """Test bootstrap discovery"""
        registry = PeerRegistry()
        discovery = PeerDiscovery(
            registry,
            bootstrap_nodes=["ws://bootstrap1:8000"],
            enable_mdns=False,
            enable_gossip=False
        )
        
        discovered = await discovery.discover_bootstrap()
        assert len(discovered) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

