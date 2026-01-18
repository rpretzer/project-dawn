"""
System-level Tests

Tests for complete system functionality.
"""

import pytest
from crypto import NodeIdentity
from p2p import P2PNode, Peer
from agents import FirstAgent
from consensus import DistributedAgentRegistry


class TestSystemComponents:
    """Test all system components work together"""
    
    def test_system_initialization(self):
        """Test complete system initialization"""
        # Create node
        identity = NodeIdentity()
        node = P2PNode(identity, enable_encryption=False)
        
        # Verify all components are initialized
        assert node.identity is not None
        assert node.peer_registry is not None
        assert node.agent_registry is not None
        assert node.discovery is not None
    
    @pytest.mark.asyncio
    async def test_agent_lifecycle(self):
        """Test complete agent lifecycle"""
        identity = NodeIdentity()
        node = P2PNode(identity, enable_encryption=False)
        
        # Create and register agent
        agent = FirstAgent("agent1", "TestAgent")
        node.register_agent("agent1", agent.server)
        
        # Verify registration
        assert "agent1" in node.agents
        agent_info = node.agent_registry.get_agent(f"{node.node_id}:agent1")
        assert agent_info is not None
        
        # Verify agent appears in list
        agents = await node._handle_node_method("node/list_agents", {})
        assert len(agents["result"]["agents"]) == 1
        
        # Unregister agent
        node.unregister_agent("agent1")
        
        # Verify removal
        assert "agent1" not in node.agents
        agent_info = node.agent_registry.get_agent(f"{node.node_id}:agent1")
        assert agent_info is None
    
    @pytest.mark.asyncio
    async def test_message_routing_flow(self):
        """Test complete message routing flow"""
        identity = NodeIdentity()
        node = P2PNode(identity, enable_encryption=False)
        
        # Register agent
        agent = FirstAgent("agent1", "TestAgent")
        node.register_agent("agent1", agent.server)
        
        # Route message through node
        message = {
            "jsonrpc": "2.0",
            "method": f"{node.node_id}:agent1/tools/list",
            "params": {},
            "id": "1",
        }
        
        response = await node._route_message(message)
        
        assert response is not None
        assert response["jsonrpc"] == "2.0"
    
    def test_peer_registry_integration(self):
        """Test peer registry integration"""
        identity = NodeIdentity()
        node = P2PNode(identity, enable_encryption=False)
        node.peer_registry.persist = False
        node.peer_registry.clear()
        
        # Add peer to registry
        peer = Peer(node_id="peer1", address="ws://peer1:8000")
        node.peer_registry.add_peer(peer)
        
        # Verify peer is in registry
        assert node.peer_registry.has_peer("peer1")
        
        # List peers via node method
        # (This would require the method to be called, tested separately)
        assert len(node.peer_registry.list_peers()) == 1
    
    def test_crdt_synchronization(self):
        """Test CRDT state synchronization"""
        node_id1 = "node1"
        node_id2 = "node2"
        
        registry1 = DistributedAgentRegistry(node_id1)
        registry2 = DistributedAgentRegistry(node_id2)
        
        # Add agent to registry1
        registry1.register_local_agent(
            agent_id="agent1",
            name="Agent 1",
            description="Test agent",
            tools=[{"name": "tool1", "description": "Tool 1"}],
        )
        
        # Sync to registry2
        state1 = registry1.get_crdt_state()
        registry2.sync_from_crdt(state1)
        
        # Verify sync
        agent = registry2.get_agent(f"{node_id1}:agent1")
        assert agent is not None
        assert agent.name == "Agent 1"
        assert len(agent.tools) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



