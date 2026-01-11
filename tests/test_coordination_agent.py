"""
Tests for Coordination Agent (Phase 1)
"""

import pytest
import asyncio
from agents.coordination_agent import CoordinationAgent
from agents.task_manager import TaskManager, TaskStatus
from p2p.p2p_node import P2PNode
from crypto import NodeIdentity


class TestTaskManager:
    """Tests for TaskManager"""
    
    def test_create_task(self):
        """Test task creation"""
        manager = TaskManager()
        task = manager.create_task("Test Task", "Test description", priority=3)
        
        assert task.task_id is not None
        assert task.title == "Test Task"
        assert task.description == "Test description"
        assert task.status == TaskStatus.OPEN
        assert task.priority == 3
    
    def test_list_tasks(self):
        """Test task listing"""
        manager = TaskManager()
        task1 = manager.create_task("Task 1", "Desc 1", priority=1)
        task2 = manager.create_task("Task 2", "Desc 2", priority=5)
        task3 = manager.create_task("Task 3", "Desc 3", assignee="agent1", priority=3)
        
        all_tasks = manager.list_tasks()
        assert len(all_tasks) == 3
        
        open_tasks = manager.list_tasks(status=TaskStatus.OPEN)
        assert len(open_tasks) == 2  # task1 and task2 (task3 is ASSIGNED)
        
        assigned_tasks = manager.list_tasks(status=TaskStatus.ASSIGNED)
        assert len(assigned_tasks) == 1  # task3
    
    def test_assign_task(self):
        """Test task assignment"""
        manager = TaskManager()
        task = manager.create_task("Test", "Desc")
        
        assert manager.assign_task(task.task_id, "agent1")
        assert task.assignee == "agent1"
        assert task.status == TaskStatus.ASSIGNED
    
    def test_complete_task(self):
        """Test task completion"""
        manager = TaskManager()
        task = manager.create_task("Test", "Desc", assignee="agent1")
        manager.assign_task(task.task_id, "agent1")
        manager.start_task(task.task_id)
        
        assert manager.complete_task(task.task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None


class TestCoordinationAgent:
    """Tests for CoordinationAgent"""
    
    @pytest.fixture
    def p2p_node(self):
        """Create a P2P node for testing"""
        identity = NodeIdentity()
        node = P2PNode(
            identity=identity,
            address="ws://localhost:8000",
            enable_encryption=False,
        )
        return node
    
    @pytest.fixture
    def coord_agent(self, p2p_node):
        """Create a coordination agent for testing"""
        return CoordinationAgent("coordinator", p2p_node, "CoordinationAgent")
    
    def test_initialization(self, coord_agent):
        """Test coordination agent initialization"""
        assert coord_agent.agent_id == "coordinator"
        assert coord_agent.name == "CoordinationAgent"
        assert coord_agent.task_manager is not None
        tool_names = {tool["name"] for tool in coord_agent.get_tools()}
        for required_tool in ("agent_list", "agent_call", "agent_broadcast", "task_create", "task_list"):
            assert required_tool in tool_names
        assert len(coord_agent.get_tools()) >= 5
        assert len(coord_agent.server.get_resources()) >= 3
        assert len(coord_agent.server.get_prompts()) >= 3
    
    @pytest.mark.asyncio
    async def test_agent_list_tool(self, coord_agent):
        """Test agent_list tool"""
        result = await coord_agent._agent_list()
        
        assert result["success"] == True
        assert "agents" in result
        assert "count" in result
        assert isinstance(result["agents"], list)
    
    @pytest.mark.asyncio
    async def test_task_create_tool(self, coord_agent):
        """Test task_create tool"""
        result = await coord_agent._task_create(
            title="Test Task",
            description="Test description",
            priority=3,
        )
        
        assert result["success"] == True
        assert "task_id" in result
        assert "task" in result
        assert result["task"]["title"] == "Test Task"
    
    @pytest.mark.asyncio
    async def test_task_list_tool(self, coord_agent):
        """Test task_list tool"""
        # Create a task first
        await coord_agent._task_create("Task 1", "Desc 1")
        
        result = await coord_agent._task_list()
        
        assert result["success"] == True
        assert "tasks" in result
        assert len(result["tasks"]) >= 1
    
    @pytest.mark.asyncio
    async def test_agent_registry_resource(self, coord_agent):
        """Test agent://registry resource"""
        result = await coord_agent._agent_registry_resource()
        
        assert isinstance(result, str)
        data = eval(result) if isinstance(result, str) else result
        assert "agents" in data or "agents" in eval(result)
    
    @pytest.mark.asyncio
    async def test_room_active_resource(self, coord_agent):
        """Test room://active resource"""
        # Ensure a room exists
        coord_agent.ensure_room("main", "Main Room")
        coord_agent.add_participant("main", "agent1")
        
        result = await coord_agent._room_active_resource()
        
        assert isinstance(result, str)
        import json
        data = json.loads(result)
        assert "rooms" in data
        assert len(data["rooms"]) >= 1
    
    @pytest.mark.asyncio
    async def test_task_queue_resource(self, coord_agent):
        """Test task://queue resource"""
        # Create a task first
        await coord_agent._task_create("Test Task", "Desc")
        
        result = await coord_agent._task_queue_resource()
        
        assert isinstance(result, str)
        import json
        data = json.loads(result)
        assert "open" in data
        assert "stats" in data
    
    @pytest.mark.asyncio
    async def test_agent_coordination_prompt(self, coord_agent):
        """Test agent_coordination prompt"""
        result = await coord_agent._agent_coordination_prompt(
            task="Build a website",
            available_agents="agent1,agent2",
            context="Using Python and React"
        )
        
        assert isinstance(result, str)
        assert "Build a website" in result
        assert "Using Python and React" in result
        # Note: May not contain agent names if agents not in registry (expected in isolation)
    
    @pytest.mark.asyncio
    async def test_task_decomposition_prompt(self, coord_agent):
        """Test task_decomposition prompt"""
        result = await coord_agent._task_decomposition_prompt(
            task="Build a full-stack application",
            complexity="complex"
        )
        
        assert isinstance(result, str)
        assert "Build a full-stack application" in result
        assert "complex" in result
    
    @pytest.mark.asyncio
    async def test_agent_selection_prompt(self, coord_agent):
        """Test agent_selection prompt"""
        result = await coord_agent._agent_selection_prompt(
            task="Analyze this code",
            agent_list="agent1,agent2",
            criteria="code analysis capability"
        )
        
        assert isinstance(result, str)
        assert "Analyze this code" in result
        assert "code analysis capability" in result
        # Note: May not contain agent names if agents not in registry (expected in isolation)
