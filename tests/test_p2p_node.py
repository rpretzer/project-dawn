"""
Tests for P2P Node
"""

import pytest
from p2p import P2PNode, Peer
from crypto import NodeIdentity
from mcp.server import MCPServer


class TestP2PNode:
    """Test P2PNode"""
    
    def test_initialization(self):
        """Test P2PNode initialization"""
        identity = NodeIdentity()
        node = P2PNode(identity, address="ws://localhost:8000")
        
        assert node.identity == identity
        assert node.node_id == identity.get_node_id()
        assert node.address == "ws://localhost:8000"
        assert len(node.agents) == 0
        assert len(node.peer_connections) == 0
    
    def test_register_agent(self):
        """Test registering an agent"""
        identity = NodeIdentity()
        node = P2PNode(identity)
        
        # Create a simple agent
        agent_server = MCPServer("test_agent")
        node.register_agent("agent1", agent_server)
        
        assert "agent1" in node.agents
        assert node.get_agent("agent1") == agent_server
        assert "agent1" in node.list_agents()
    
    def test_unregister_agent(self):
        """Test unregistering an agent"""
        identity = NodeIdentity()
        node = P2PNode(identity)
        
        agent_server = MCPServer("test_agent")
        node.register_agent("agent1", agent_server)
        node.unregister_agent("agent1")
        
        assert "agent1" not in node.agents
        assert node.get_agent("agent1") is None
    
    @pytest.mark.asyncio
    async def test_handle_node_method_list_agents(self):
        """Test node/list_agents method"""
        identity = NodeIdentity()
        node = P2PNode(identity)
        
        # Register an agent
        agent_server = MCPServer("test_agent")
        node.register_agent("agent1", agent_server)
        
        # Call node method
        response = await node._handle_node_method("node/list_agents", {})
        
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        assert len(response["result"]["agents"]) == 1
        # New format uses full agent_id
        assert response["result"]["agents"][0]["agent_id"] == f"{node.node_id}:agent1"
    
    @pytest.mark.asyncio
    async def test_handle_node_method_get_info(self):
        """Test node/get_info method"""
        identity = NodeIdentity()
        node = P2PNode(identity, address="ws://localhost:8000")
        
        response = await node._handle_node_method("node/get_info", {})
        
        assert response["jsonrpc"] == "2.0"
        assert response["result"]["node_id"] == node.node_id
        assert response["result"]["address"] == "ws://localhost:8000"
    
    @pytest.mark.asyncio
    async def test_route_to_local_agent(self):
        """Test routing to local agent"""
        identity = NodeIdentity()
        node = P2PNode(identity)
        
        # Create agent with a tool
        agent_server = MCPServer("test_agent")
        
        # Register a tool using register_function (simpler)
        async def test_tool_handler(arguments):
            return "test result"
        
        agent_server.register_function(
            name="test_tool",
            description="Test tool",
            handler=test_tool_handler,
            inputSchema={"type": "object", "properties": {}}
        )
        
        node.register_agent("agent1", agent_server)
        
        # Route to agent
        response = await node._route_to_local_agent("agent1", "tools/list", {})
        
        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
    
    @pytest.mark.asyncio
    async def test_route_to_local_agent_not_found(self):
        """Test routing to non-existent local agent"""
        identity = NodeIdentity()
        node = P2PNode(identity)
        
        response = await node._route_to_local_agent("nonexistent", "tools/list", {})
        
        assert response is not None
        assert "error" in response
        assert response["error"]["code"] == -32601
    
    def test_peer_registry_integration(self):
        """Test integration with peer registry"""
        identity = NodeIdentity()
        node = P2PNode(identity)
        node.peer_registry.persist = False
        node.peer_registry.clear()
        
        # Add peer to registry
        peer = Peer(node_id="peer1", address="ws://peer1:8000")
        node.peer_registry.add_peer(peer)
        
        assert node.peer_registry.has_peer("peer1")
        assert node.peer_registry.get_peer_count() == 1


class TestP2PNodeRouting:
    """Test P2P routing functionality"""
    
    @pytest.mark.asyncio
    async def test_route_message_node_method(self):
        """Test routing node-level method"""
        identity = NodeIdentity()
        node = P2PNode(identity)
        
        message = {
            "jsonrpc": "2.0",
            "method": "node/get_info",
            "params": {},
            "id": "1",
        }
        
        response = await node._route_message(message)
        
        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
    
    @pytest.mark.asyncio
    async def test_route_message_local_agent(self):
        """Test routing to local agent"""
        identity = NodeIdentity()
        node = P2PNode(identity)
        
        # Register agent
        agent_server = MCPServer("test_agent")
        node.register_agent("agent1", agent_server)
        
        # Route message with node_id:agent_id format
        message = {
            "jsonrpc": "2.0",
            "method": f"{node.node_id}:agent1/tools/list",
            "params": {},
            "id": "1",
        }
        
        response = await node._route_message(message)
        
        assert response is not None
        assert response["jsonrpc"] == "2.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

