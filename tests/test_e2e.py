"""
End-to-End Tests

Full system integration tests.
"""

import pytest
import asyncio
import json
from crypto import NodeIdentity
from p2p import P2PNode
from agents import FirstAgent


class TestE2EFlow:
    """End-to-end flow tests"""
    
    @pytest.mark.asyncio
    async def test_complete_flow(self):
        """Test complete system flow"""
        # Create node
        identity = NodeIdentity()
        node = P2PNode(
            identity,
            address="ws://localhost:9000",
            enable_encryption=False,
        )
        
        # Register agent
        agent = FirstAgent("agent1", "TestAgent")
        node.register_agent("agent1", agent.server)
        
        # Verify agent is registered
        assert "agent1" in node.agents
        assert len(node.list_agents()) == 1
        
        # Verify agent is in registry
        agent_info = node.agent_registry.get_agent(f"{node.node_id}:agent1")
        assert agent_info is not None
        
        # Test agent routing
        response = await node.call_agent(
            target="agent1",
            method="tools/list",
            params={}
        )
        
        assert response is not None
        assert response.get("jsonrpc") == "2.0"
    
    @pytest.mark.asyncio
    async def test_node_api_flow(self):
        """Test node API methods"""
        identity = NodeIdentity()
        node = P2PNode(identity, enable_encryption=False)
        
        # Register agent
        agent = FirstAgent("agent1", "TestAgent")
        node.register_agent("agent1", agent.server)
        
        # Test node/get_info
        response = await node._handle_node_method("node/get_info", {})
        assert response["jsonrpc"] == "2.0"
        assert response["result"]["node_id"] == node.node_id
        assert len(response["result"]["agents"]) == 1
        
        # Test node/list_agents
        response = await node._handle_node_method("node/list_agents", {})
        assert response["jsonrpc"] == "2.0"
        assert len(response["result"]["agents"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



