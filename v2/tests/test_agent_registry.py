"""
Tests for distributed agent registry
"""

import pytest
import time
from consensus import DistributedAgentRegistry, AgentInfo, CRDTMap


class TestAgentInfo:
    """Test AgentInfo"""
    
    def test_create_agent_info(self):
        """Test creating agent info"""
        agent = AgentInfo(
            agent_id="node1:agent1",
            node_id="node1",
            local_agent_id="agent1",
            name="Test Agent",
            description="Test description",
        )
        
        assert agent.agent_id == "node1:agent1"
        assert agent.node_id == "node1"
        assert agent.local_agent_id == "agent1"
        assert agent.name == "Test Agent"
        assert agent.available is True
    
    def test_agent_info_serialization(self):
        """Test agent info serialization"""
        agent = AgentInfo(
            agent_id="node1:agent1",
            node_id="node1",
            local_agent_id="agent1",
            name="Test Agent",
        )
        
        data = agent.to_dict()
        assert data["agent_id"] == "node1:agent1"
        assert data["name"] == "Test Agent"
        
        # Deserialize
        agent2 = AgentInfo.from_dict(data)
        assert agent2.agent_id == agent.agent_id
        assert agent2.name == agent.name


class TestDistributedAgentRegistry:
    """Test DistributedAgentRegistry"""
    
    def test_initialization(self):
        """Test registry initialization"""
        registry = DistributedAgentRegistry("node1")
        
        assert registry.node_id == "node1"
        assert len(registry.agents) == 0
    
    def test_register_local_agent(self):
        """Test registering local agent"""
        registry = DistributedAgentRegistry("node1")
        
        agent_info = registry.register_local_agent(
            agent_id="agent1",
            name="Test Agent",
            description="Test",
        )
        
        assert agent_info.agent_id == "node1:agent1"
        assert agent_info.node_id == "node1"
        assert "node1:agent1" in registry.agents
    
    def test_unregister_local_agent(self):
        """Test unregistering local agent"""
        registry = DistributedAgentRegistry("node1")
        
        registry.register_local_agent("agent1", "Test Agent")
        registry.unregister_local_agent("agent1")
        
        assert "node1:agent1" not in registry.agents
    
    def test_get_agent(self):
        """Test getting agent"""
        registry = DistributedAgentRegistry("node1")
        
        registry.register_local_agent("agent1", "Test Agent")
        
        # Get by full ID
        agent = registry.get_agent("node1:agent1")
        assert agent is not None
        assert agent.name == "Test Agent"
        
        # Get by local ID
        agent = registry.get_agent("agent1")
        assert agent is not None
    
    def test_list_agents(self):
        """Test listing agents"""
        registry = DistributedAgentRegistry("node1")
        
        registry.register_local_agent("agent1", "Agent 1")
        registry.register_local_agent("agent2", "Agent 2")
        
        agents = registry.list_agents()
        assert len(agents) == 2
        
        local = registry.list_local_agents()
        assert len(local) == 2
    
    def test_register_remote_agent(self):
        """Test registering remote agent"""
        registry = DistributedAgentRegistry("node1")
        
        remote_agent = AgentInfo(
            agent_id="node2:agent1",
            node_id="node2",
            local_agent_id="agent1",
            name="Remote Agent",
        )
        
        registry.register_remote_agent(remote_agent)
        
        assert "node2:agent1" in registry.agents
        assert len(registry.list_remote_agents()) == 1
    
    def test_find_agents_by_capability(self):
        """Test finding agents by capability"""
        registry = DistributedAgentRegistry("node1")
        
        # Register agent with tools
        registry.register_local_agent(
            agent_id="agent1",
            name="Tool Agent",
            tools=[{"name": "test_tool", "description": "Test"}],
        )
        
        # Find by capability
        agents = registry.find_agents_by_capability("tool")
        assert len(agents) == 1
        
        agents = registry.find_agents_by_capability("tool", "test_tool")
        assert len(agents) == 1
    
    def test_agent_health(self):
        """Test agent health tracking"""
        registry = DistributedAgentRegistry("node1")
        
        registry.register_local_agent("agent1", "Test Agent")
        
        registry.update_agent_health("node1:agent1", 0.8)
        agent = registry.get_agent("node1:agent1")
        assert agent.health_score == 0.8
    
    def test_mark_agent_unavailable(self):
        """Test marking agent unavailable"""
        registry = DistributedAgentRegistry("node1")
        
        registry.register_local_agent("agent1", "Test Agent")
        registry.mark_agent_unavailable("node1:agent1")
        
        agent = registry.get_agent("node1:agent1")
        assert agent.available is False
        
        available = registry.list_agents(available_only=True)
        assert len(available) == 0


class TestCRDTMap:
    """Test CRDTMap"""
    
    def test_set_get(self):
        """Test setting and getting values"""
        crdt = CRDTMap("node1")
        
        crdt.set("key1", "value1")
        assert crdt.get("key1") == "value1"
    
    def test_remove(self):
        """Test removing keys"""
        crdt = CRDTMap("node1")
        
        crdt.set("key1", "value1")
        crdt.remove("key1")
        assert not crdt.has("key1")
    
    def test_merge(self):
        """Test merging CRDT states"""
        crdt1 = CRDTMap("node1")
        crdt2 = CRDTMap("node2")
        
        # Set different values
        crdt1.set("key1", "value1")
        crdt2.set("key2", "value2")
        
        # Merge
        state2 = crdt2.get_state()
        merged = crdt1.merge(state2)
        
        assert "key1" in merged
        assert "key2" in merged
    
    def test_last_write_wins(self):
        """Test last-write-wins conflict resolution"""
        crdt1 = CRDTMap("node1")
        crdt2 = CRDTMap("node2")
        
        # Set same key with different values
        crdt1.set("key1", "value1")
        time.sleep(0.01)  # Ensure different timestamps
        crdt2.set("key1", "value2")
        
        # Merge (value2 should win)
        state2 = crdt2.get_state()
        merged = crdt1.merge(state2)
        
        assert merged["key1"] == "value2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



