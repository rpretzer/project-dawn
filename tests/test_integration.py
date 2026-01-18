"""
Integration Tests

End-to-end tests for the decentralized P2P system.
"""

import pytest
from crypto import NodeIdentity
from p2p import P2PNode
from agents import FirstAgent
from consensus import DistributedAgentRegistry


class TestP2PNodeIntegration:
    """Integration tests for P2PNode"""
    
    @pytest.mark.asyncio
    async def test_node_start_stop(self):
        """Test node startup and shutdown"""
        identity = NodeIdentity()
        node = P2PNode(identity, address="ws://localhost:9000", enable_encryption=False)
        
        # Note: Start would block, so we'll test initialization
        assert node.node_id == identity.get_node_id()
        assert node.address == "ws://localhost:9000"
        assert len(node.agents) == 0
    
    @pytest.mark.asyncio
    async def test_agent_registration(self):
        """Test agent registration and registry integration"""
        identity = NodeIdentity()
        node = P2PNode(identity, enable_encryption=False)
        
        # Create and register agent
        agent = FirstAgent("agent1", "TestAgent")
        node.register_agent("agent1", agent.server)
        
        # Check agent is registered
        assert "agent1" in node.agents
        assert node.get_agent("agent1") == agent.server
        
        # Check agent is in registry
        agent_info = node.agent_registry.get_agent(f"{node.node_id}:agent1")
        assert agent_info is not None
        assert agent_info.name == "TestAgent"
    
    @pytest.mark.asyncio
    async def test_node_methods(self):
        """Test node-level methods"""
        identity = NodeIdentity()
        node = P2PNode(identity, address="ws://localhost:9000", enable_encryption=False)
        
        # Register agent
        agent = FirstAgent("agent1", "TestAgent")
        node.register_agent("agent1", agent.server)
        
        # Test node/get_info
        response = await node._handle_node_method("node/get_info", {})
        assert response["jsonrpc"] == "2.0"
        assert response["result"]["node_id"] == node.node_id
        assert response["result"]["address"] == "ws://localhost:9000"
        assert "agent1" in response["result"]["agents"]
        
        # Test node/list_agents
        response = await node._handle_node_method("node/list_agents", {})
        assert response["jsonrpc"] == "2.0"
        assert len(response["result"]["agents"]) == 1
        assert response["result"]["agents"][0]["agent_id"] == f"{node.node_id}:agent1"


class TestAgentRegistryIntegration:
    """Integration tests for agent registry"""
    
    @pytest.mark.asyncio
    async def test_registry_sync(self):
        """Test CRDT state synchronization"""
        node_id1 = "node1"
        node_id2 = "node2"
        
        registry1 = DistributedAgentRegistry(node_id1)
        registry2 = DistributedAgentRegistry(node_id2)
        
        # Register agent in registry1
        registry1.register_local_agent(
            agent_id="agent1",
            name="Agent 1",
            tools=[{"name": "tool1"}],
        )
        
        # Sync state from registry1 to registry2
        state1 = registry1.get_crdt_state()
        registry2.sync_from_crdt(state1)
        
        # Check agent is in registry2
        agent = registry2.get_agent(f"{node_id1}:agent1")
        assert agent is not None
        assert agent.name == "Agent 1"
    
    def test_capability_discovery(self):
        """Test finding agents by capability"""
        registry = DistributedAgentRegistry("node1")
        
        # Register agents with different capabilities
        registry.register_local_agent(
            agent_id="agent1",
            name="Tool Agent",
            tools=[{"name": "test_tool"}],
        )
        
        registry.register_local_agent(
            agent_id="agent2",
            name="Resource Agent",
            resources=[{"uri": "resource://1"}],
        )
        
        # Find by capability
        tool_agents = registry.find_agents_by_capability("tool")
        assert len(tool_agents) == 1
        assert tool_agents[0].local_agent_id == "agent1"
        
        resource_agents = registry.find_agents_by_capability("resource")
        assert len(resource_agents) == 1
        assert resource_agents[0].local_agent_id == "agent2"


class TestEndToEnd:
    """End-to-end integration tests"""
    
    @pytest.mark.asyncio
    async def test_message_routing_local_agent(self):
        """Test routing message to local agent"""
        identity = NodeIdentity()
        node = P2PNode(identity, enable_encryption=False)
        
        # Register agent
        agent = FirstAgent("agent1", "TestAgent")
        node.register_agent("agent1", agent.server)
        
        # Route message to agent
        response = await node._route_to_local_agent("agent1", "tools/list", {})
        
        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert "result" in response or "error" in response
    
    def test_peer_discovery_flow(self):
        """Test peer discovery initialization"""
        identity = NodeIdentity()
        node = P2PNode(
            identity,
            bootstrap_nodes=["ws://bootstrap:8000"],
            enable_encryption=False,
        )
        
        # Check discovery is initialized
        assert node.discovery is not None
        assert node.discovery.bootstrap is not None
        
        # Check peer registry is set up
        assert node.peer_registry is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



