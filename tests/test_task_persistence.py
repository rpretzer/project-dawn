"""
Tests for TaskManager Persistence
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from agents.task_manager import TaskManager, TaskStatus

class TestTaskPersistence:
    """Test suite for TaskManager persistence"""
    
    def setup_method(self):
        """Set up for each test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def teardown_method(self):
        """Clean up after each test"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_task_creation_persistence(self):
        """Test that created tasks are saved and loaded"""
        # Create first manager and add task
        tm1 = TaskManager(data_dir=self.temp_dir)
        task = tm1.create_task("Test Task", "Description")
        task_id = task.task_id
        
        # Create second manager pointing to same dir
        tm2 = TaskManager(data_dir=self.temp_dir)
        
        # Check if task was loaded
        loaded_task = tm2.get_task(task_id)
        assert loaded_task is not None
        assert loaded_task.title == "Test Task"
        assert loaded_task.description == "Description"

    def test_task_status_persistence(self):
        """Test that task status updates are persisted"""
        tm1 = TaskManager(data_dir=self.temp_dir)
        task = tm1.create_task("Test Status", "Desc")
        task_id = task.task_id
        
        # Update status
        tm1.assign_task(task_id, "agent1")
        tm1.start_task(task_id)
        
        # Reload in new manager
        tm2 = TaskManager(data_dir=self.temp_dir)
        loaded_task = tm2.get_task(task_id)
        
        assert loaded_task.status == TaskStatus.IN_PROGRESS
        assert loaded_task.assignee == "agent1"
        assert loaded_task.started_at is not None

    def test_task_completion_persistence(self):
        """Test that task completion and results are persisted"""
        tm1 = TaskManager(data_dir=self.temp_dir)
        task = tm1.create_task("Test Result", "Desc")
        task_id = task.task_id
        
        tm1.assign_task(task_id, "agent1")
        tm1.start_task(task_id)
        tm1.complete_task(task_id, result={"output": "success"})
        
        # Reload
        tm2 = TaskManager(data_dir=self.temp_dir)
        loaded_task = tm2.get_task(task_id)
        
        assert loaded_task.status == TaskStatus.COMPLETED
        assert loaded_task.metadata["result"] == {"output": "success"}
        assert loaded_task.completed_at is not None

    def test_clear_persistence(self):
        """Test that clearing tasks is persisted"""
        tm1 = TaskManager(data_dir=self.temp_dir)
        tm1.create_task("Task 1", "D1")
        
        tm1.clear()
        
        tm2 = TaskManager(data_dir=self.temp_dir)
        assert tm2.get_stats()["total_tasks"] == 0
