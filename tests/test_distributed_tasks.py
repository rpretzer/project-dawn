"""
Tests for Distributed Task Execution
"""

import pytest
import asyncio
import json
from crypto import NodeIdentity
from p2p.p2p_node import P2PNode
from agents.coordination_agent import CoordinationAgent
from agents.task_manager import TaskStatus

class TestDistributedTasks:
    """Test suite for distributed task execution and sync"""
    
    @pytest.mark.asyncio
    async def test_task_sync_via_gossip(self):
        """Test that tasks are synchronized when receiving a gossip announcement"""
        identity = NodeIdentity()
        node = P2PNode(identity=identity, address="ws://localhost:8000")
        
        # Initialize coordination agent (which initializes task manager)
        coord = CoordinationAgent("coordinator", node)
        node.coordination_agent = coord
        coord.task_manager.clear()
        
        # Verify initial state
        assert len(coord.task_manager.tasks) == 0
        
        # Create a mock gossip announcement with a task
        remote_node_id = "remote_node_123"
        task_data = {
            "task_id": "remote_task_1",
            "title": "Remote Task",
            "description": "Created on remote node",
            "status": "open",
            "assignee": None,
            "priority": 1,
            "dependencies": [],
            "created_at": 1000.0,
            "updated_at": 1000.0,
            "metadata": {}
        }
        
        # CRDT state format (simplified for mock)
        task_registry_state = {
            "remote_task_1": {
                "value": task_data,
                "timestamp": 1000.0,
                "node_id": remote_node_id
            }
        }
        
        announcement = {
            "type": "gossip_announcement",
            "task_registry": task_registry_state
        }
        
        # Simulate receiving the gossip message
        await node._handle_peer_message(remote_node_id, json.dumps(announcement))
        
        # Verify task was synced
        assert "remote_task_1" in coord.task_manager.tasks
        synced_task = coord.task_manager.get_task("remote_task_1")
        assert synced_task.title == "Remote Task"
        assert synced_task.priority == 1

    @pytest.mark.asyncio
    async def test_task_update_propagation(self):
        """Test that local task updates are reflected in the distributed registry state"""
        identity = NodeIdentity()
        node = P2PNode(identity=identity, address="ws://localhost:8000")
        coord = CoordinationAgent("coordinator", node)
        node.coordination_agent = coord
        coord.task_manager.clear()
        
        # Create a local task
        task = coord.task_manager.create_task("Local Task", "Desc")
        task_id = task.task_id
        
        # Check distributed registry (task_manager._save calls registry.update_task)
        distributed_task = node.task_registry.get_task(task_id)
        assert distributed_task is not None
        assert distributed_task["title"] == "Local Task"
        
        # Update task status
        coord.task_manager.complete_task(task_id)
        
        # Verify update propagated to distributed registry
        updated_distributed = node.task_registry.get_task(task_id)
        assert updated_distributed["status"] == "completed"
