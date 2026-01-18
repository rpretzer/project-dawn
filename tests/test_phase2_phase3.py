"""
Tests for Phase 2 (Network Awareness) and Phase 3 (File System & Code Operations)
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock

from agents.coordination_agent import CoordinationAgent
from agents.code_agent import CodeAgent
from p2p.p2p_node import P2PNode


@pytest.fixture
def mock_p2p_node():
    """Create a mock P2P node"""
    node = Mock(spec=P2PNode)
    node.node_id = "test_node_1234567890123456789012345678901234567890123456789012345678901234"
    node.address = "ws://localhost:8000"
    node.start_time = 1000.0
    
    # Mock peer registry
    from p2p.peer import Peer
    peer1 = Peer(
        node_id="peer1_1234567890123456789012345678901234567890123456789012345678901234",
        address="ws://localhost:8001",
        connected=True,
    )
    peer1.agents = ["agent1", "agent2"]
    peer1.health_score = 0.9
    peer1.connection_attempts = 10
    peer1.successful_connections = 9
    peer1.failed_connections = 1
    
    peer2 = Peer(
        node_id="peer2_1234567890123456789012345678901234567890123456789012345678901234",
        address="ws://localhost:8002",
        connected=False,
    )
    peer2.health_score = 0.5
    
    node.peer_registry = Mock()
    node.peer_registry.list_peers.return_value = [peer1, peer2]
    node.peer_registry.get_peer.return_value = peer1
    node.peer_registry.get_peer_count.return_value = 2
    
    # Mock agent registry
    from consensus.agent_registry import AgentInfo
    agent1 = AgentInfo(
        agent_id="test_node_1234567890123456789012345678901234567890123456789012345678901234:agent1",
        local_agent_id="agent1",
        node_id=node.node_id,
        name="TestAgent1",
        description="Test agent 1",
        tools=[{"name": "test_tool"}],
        resources=[],
        prompts=[],
    )
    agent2 = AgentInfo(
        agent_id="peer1_1234567890123456789012345678901234567890123456789012345678901234:agent2",
        local_agent_id="agent2",
        node_id=peer1.node_id,
        name="RemoteAgent",
        description="Remote agent",
        tools=[{"name": "remote_tool"}],
        resources=[],
        prompts=[],
    )
    
    node.agent_registry = Mock()
    node.agent_registry.list_agents.return_value = [agent1, agent2]
    node.agent_registry.get_agent.return_value = agent1
    node.agent_registry.list_agents.side_effect = lambda node_id=None: (
            [a for a in [agent1, agent2] if not node_id or a.node_id == node_id]
        )
    
    # Mock local agents
    node.agents = {"agent1": Mock()}
    node.list_agents.return_value = ["agent1"]
    
    return node


@pytest.fixture
def coord_agent(mock_p2p_node):
    """Create a coordination agent"""
    return CoordinationAgent("coordinator", mock_p2p_node, "CoordinationAgent")


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace"""
    workspace = tempfile.mkdtemp()
    workspace_path = Path(workspace)
    
    # Create some test files
    (workspace_path / "test.py").write_text("def hello():\n    print('Hello')\n")
    (workspace_path / "test.txt").write_text("Hello World\n")
    (workspace_path / "subdir").mkdir()
    (workspace_path / "subdir" / "nested.py").write_text("import os\n")
    
    yield workspace_path
    
    # Cleanup
    shutil.rmtree(workspace)


@pytest.fixture
def code_agent(temp_workspace):
    """Create a code agent"""
    return CodeAgent("code", workspace_path=str(temp_workspace), name="CodeAgent")


class TestPhase2NetworkAwareness:
    """Tests for Phase 2: Network Awareness & Discovery"""
    
    def test_network_peers_tool(self, coord_agent):
        """Test network_peers tool"""
        result = asyncio.run(coord_agent._network_peers())
        assert result["success"] is True
        assert result["count"] == 2
        assert result["total_connected"] == 1
        assert result["total_disconnected"] == 1
    
    def test_network_peers_filter_connected(self, coord_agent):
        """Test network_peers with status filter"""
        result = asyncio.run(coord_agent._network_peers(status="connected"))
        assert result["success"] is True
        assert result["count"] == 1
        assert result["total_connected"] == 1
    
    def test_network_info_tool(self, coord_agent):
        """Test network_info tool"""
        result = asyncio.run(coord_agent._network_info())
        assert result["success"] is True
        assert "network_stats" in result
        stats = result["network_stats"]
        assert stats["node_count"] == 2
        assert stats["connected_nodes"] == 1
        assert stats["total_agents"] == 2
        assert "average_health_score" in stats
        assert "connection_success_rate" in stats
    
    def test_node_info_local(self, coord_agent):
        """Test node_info for local node"""
        result = asyncio.run(coord_agent._node_info(coord_agent.p2p_node.node_id))
        assert result["success"] is True
        assert result["is_local"] is True
        assert "agents" in result
        assert result["status"] == "online"
    
    def test_node_info_remote(self, coord_agent):
        """Test node_info for remote node"""
        peer = coord_agent.p2p_node.peer_registry.list_peers()[0]
        result = asyncio.run(coord_agent._node_info(peer.node_id))
        assert result["success"] is True
        assert result["node"]["is_local"] is False
        assert result["node"]["connected"] is True
        assert "agent_count" in result["node"]
    
    def test_node_info_not_found(self, coord_agent):
        """Test node_info for non-existent node"""
        coord_agent.p2p_node.peer_registry.get_peer.return_value = None
        result = asyncio.run(coord_agent._node_info("nonexistent"))
        assert result["success"] is False
        assert "error" in result
    
    def test_agent_discover_by_capability(self, coord_agent):
        """Test agent_discover by capability"""
        result = asyncio.run(coord_agent._agent_discover(capability="test_tool"))
        assert result["success"] is True
        assert result["count"] >= 1
        assert any("test_tool" in str(agent.get("tools", [])) for agent in result["agents"])
    
    def test_agent_discover_by_name(self, coord_agent):
        """Test agent_discover by name pattern"""
        result = asyncio.run(coord_agent._agent_discover(name_pattern="Test*"))
        assert result["success"] is True
        assert result["count"] >= 1
    
    def test_network_topology_resource(self, coord_agent):
        """Test network://topology resource"""
        result = asyncio.run(coord_agent._network_topology_resource())
        import json
        topology = json.loads(result)
        assert "nodes" in topology
        assert "edges" in topology
        assert topology["total_nodes"] >= 1
        assert any(node["type"] == "local" for node in topology["nodes"])
    
    def test_network_stats_resource(self, coord_agent):
        """Test network://stats resource"""
        result = asyncio.run(coord_agent._network_stats_resource())
        import json
        stats = json.loads(result)
        assert "network" in stats
        assert "health" in stats
        assert "connections" in stats
        assert stats["network"]["total_nodes"] >= 1
    
    def test_network_analysis_prompt(self, coord_agent):
        """Test network_analysis prompt"""
        result = asyncio.run(coord_agent._network_analysis_prompt("{}", "performance"))
        assert isinstance(result, str)
        assert "Network Analysis" in result
        assert "performance" in result
    
    def test_peer_recommendation_prompt(self, coord_agent):
        """Test peer_recommendation prompt"""
        result = asyncio.run(coord_agent._peer_recommendation_prompt("test task", "[]"))
        assert isinstance(result, str)
        assert "test task" in result
        assert "recommend" in result.lower()


class TestPhase3FileSystemCodeOps:
    """Tests for Phase 3: File System & Code Operations"""
    
    def test_file_read(self, code_agent):
        """Test file_read tool"""
        result = asyncio.run(code_agent._file_read("test.txt"))
        assert result["success"] is True
        assert "Hello World" in result["content"]
        assert result["encoding"] == "utf-8"
        assert "lines" in result
    
    def test_file_read_not_found(self, code_agent):
        """Test file_read with non-existent file"""
        result = asyncio.run(code_agent._file_read("nonexistent.txt"))
        assert result["success"] is False
        assert "error" in result
    
    def test_file_write(self, code_agent):
        """Test file_write tool"""
        result = asyncio.run(code_agent._file_write("new_file.txt", "New content"))
        assert result["success"] is True
        assert result["size"] == len("New content")
        
        # Verify file was written
        read_result = asyncio.run(code_agent._file_read("new_file.txt"))
        assert read_result["success"] is True
        assert read_result["content"] == "New content"
    
    def test_file_list(self, code_agent):
        """Test file_list tool"""
        result = asyncio.run(code_agent._file_list("."))
        assert result["success"] is True
        assert result["count"] >= 2  # At least test.py and test.txt
        assert any(f["path"] == "test.py" for f in result["files"])
    
    def test_file_list_recursive(self, code_agent):
        """Test file_list with recursive option"""
        result = asyncio.run(code_agent._file_list(".", recursive=True))
        assert result["success"] is True
        assert result["count"] >= 3  # Should include nested files
        assert any("subdir" in f["path"] for f in result["files"])
    
    def test_file_list_pattern(self, code_agent):
        """Test file_list with pattern filter"""
        result = asyncio.run(code_agent._file_list(".", pattern="*.py"))
        assert result["success"] is True
        assert all(f["path"].endswith(".py") for f in result["files"])
    
    def test_file_search_content(self, code_agent):
        """Test file_search by content"""
        result = asyncio.run(code_agent._file_search("Hello", type="content"))
        assert result["success"] is True
        assert result["count"] >= 1
        assert any("Hello" in match.get("snippet", "") for match in result["matches"])
    
    def test_file_search_name(self, code_agent):
        """Test file_search by name"""
        result = asyncio.run(code_agent._file_search("test", type="name"))
        assert result["success"] is True
        assert result["count"] >= 1
        assert all("test" in match["path"] for match in result["matches"])
    
    def test_code_analyze(self, code_agent):
        """Test code_analyze tool"""
        result = asyncio.run(code_agent._code_analyze("test.py"))
        assert result["success"] is True
        assert "analysis" in result
        analysis = result["analysis"]
        assert analysis["language"] == "python"
        assert "functions" in analysis
        assert "hello" in analysis["functions"]
    
    def test_code_execute_python(self, code_agent):
        """Test code_execute for Python"""
        result = asyncio.run(code_agent._code_execute("print('Hello')", "python"))
        assert result["success"] is True
        assert "Hello" in result["stdout"]
        assert result["return_code"] == 0
    
    def test_code_execute_timeout(self, code_agent):
        """Test code_execute with timeout"""
        result = asyncio.run(code_agent._code_execute("import time; time.sleep(60)", "python", timeout=1.0))
        assert result["success"] is False
        assert "timeout" in result["error"].lower()
    
    def test_code_format(self, code_agent):
        """Test code_format tool"""
        code = "def test():\n    pass"
        result = asyncio.run(code_agent._code_format(code, "python"))
        assert result["success"] is True
        assert "formatted_code" in result
    
    def test_file_tree_resource(self, code_agent):
        """Test file://tree resource"""
        result = asyncio.run(code_agent._file_tree_resource())
        import json
        tree = json.loads(result)
        assert "workspace" in tree
        assert "tree" in tree
        assert tree["tree"]["type"] == "directory"
    
    def test_code_dependencies_resource(self, code_agent):
        """Test code://dependencies resource"""
        result = asyncio.run(code_agent._code_dependencies_resource())
        import json
        deps = json.loads(result)
        assert "dependencies" in deps
    
    def test_code_metrics_resource(self, code_agent):
        """Test code://metrics resource"""
        result = asyncio.run(code_agent._code_metrics_resource())
        import json
        metrics = json.loads(result)
        assert "metrics" in metrics
        assert "total_files" in metrics["metrics"]
        assert "total_lines" in metrics["metrics"]
    
    def test_file_history_resource(self, code_agent):
        """Test file://history resource"""
        # Write a file first
        asyncio.run(code_agent._file_write("history_test.txt", "test"))
        
        result = asyncio.run(code_agent._file_history_resource())
        import json
        history = json.loads(result)
        assert "history" in history
    
    def test_code_review_prompt(self, code_agent):
        """Test code_review prompt"""
        result = asyncio.run(code_agent._code_review_prompt("def test(): pass", "python", "security"))
        assert isinstance(result, str)
        assert "Code Review" in result
        assert "python" in result
        assert "security" in result
    
    def test_code_explanation_prompt(self, code_agent):
        """Test code_explanation prompt"""
        result = asyncio.run(code_agent._code_explanation_prompt("def test(): pass", "python", "simple"))
        assert isinstance(result, str)
        assert "Code Explanation" in result
        assert "python" in result
    
    def test_refactoring_suggestion_prompt(self, code_agent):
        """Test refactoring_suggestion prompt"""
        result = asyncio.run(code_agent._refactoring_suggestion_prompt("def test(): pass", "python", '["readability"]'))
        assert isinstance(result, str)
        assert "Refactoring" in result
        assert "python" in result


class TestPhase2Phase3Integration:
    """Integration tests for Phase 2 and Phase 3"""
    
    def test_coord_agent_has_phase2_tools(self, coord_agent):
        """Verify coordination agent has Phase 2 tools"""
        tools = coord_agent.get_tools()
        tool_names = [t["name"] for t in tools]
        assert "network_peers" in tool_names
        assert "network_info" in tool_names
        assert "node_info" in tool_names
        assert "agent_discover" in tool_names
    
    def test_code_agent_has_phase3_tools(self, code_agent):
        """Verify code agent has Phase 3 tools"""
        tools = code_agent.get_tools()
        tool_names = [t["name"] for t in tools]
        assert "file_read" in tool_names
        assert "file_write" in tool_names
        assert "file_list" in tool_names
        assert "file_search" in tool_names
        assert "code_analyze" in tool_names
        assert "code_execute" in tool_names
        assert "code_format" in tool_names
        assert "code_test" in tool_names
    
    def test_path_security(self, code_agent):
        """Test that code agent restricts paths to workspace"""
        # Try to access file outside workspace
        result = asyncio.run(code_agent._file_read("/etc/passwd"))
        assert result["success"] is False
        assert "outside" in result["error"].lower() or "not found" in result["error"].lower()

