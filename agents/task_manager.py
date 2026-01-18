"""
Task Management System

Manages tasks for agent coordination and collaboration.
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from data_paths import data_root

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status"""
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Task definition"""
    task_id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.OPEN
    assignee: Optional[str] = None  # agent_id
    priority: int = 5  # 1 (highest) to 10 (lowest)
    dependencies: List[str] = field(default_factory=list)  # List of task_ids
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "assignee": self.assignee,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create task from dictionary"""
        return cls(
            task_id=data["task_id"],
            title=data["title"],
            description=data["description"],
            status=TaskStatus(data["status"]),
            assignee=data.get("assignee"),
            priority=data.get("priority", 5),
            dependencies=data.get("dependencies", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )


class TaskManager:
    """
    Task manager for agent coordination
    
    Manages tasks across the network, tracking assignments and progress.
    """
    
    def __init__(self, data_dir: Optional[Path] = None, persist: bool = True, distributed_registry: Any = None):
        """
        Initialize task manager
        
        Args:
            data_dir: Data directory for persistence (defaults to data_root/agents/tasks)
            persist: Enable persistence (default True)
            distributed_registry: Optional DistributedTaskRegistry for network sync
        """
        self.tasks: Dict[str, Task] = {}  # task_id -> Task
        self.persist = persist
        self.distributed_registry = distributed_registry
        self.data_dir = data_dir or data_root() / "agents" / "tasks"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_path = self.data_dir / "tasks.json"
        
        # Load persisted tasks
        if self.persist:
            self._load()
            
        logger.info(f"TaskManager initialized with {len(self.tasks)} tasks")
    
    def _load(self) -> None:
        """Load tasks from disk"""
        if not self.tasks_path.exists():
            return
        
        try:
            data = json.loads(self.tasks_path.read_text(encoding="utf-8"))
            for item in data.get("tasks", []):
                task = Task.from_dict(item)
                self.tasks[task.task_id] = task
            logger.debug(f"Loaded {len(self.tasks)} tasks from {self.tasks_path}")
        except Exception as e:
            logger.warning(f"Failed to load tasks: {e}")

    def _save(self) -> None:
        """Save tasks to disk (atomic write)"""
        if not self.persist:
            return
            
        try:
            data = {
                "version": 1,
                "tasks": [task.to_dict() for task in self.tasks.values()],
                "updated_at": time.time()
            }
            tmp_path = self.tasks_path.with_suffix(".json.tmp")
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp_path.replace(self.tasks_path)
            logger.debug(f"Saved {len(self.tasks)} tasks to {self.tasks_path}")
            
            # Sync to distributed registry if available
            if self.distributed_registry:
                for task in self.tasks.values():
                    self.distributed_registry.update_task(task.to_dict())
        except Exception as e:
            logger.error(f"Failed to save tasks: {e}")

    def sync_from_distributed(self) -> None:
        """Sync local task state from the distributed registry"""
        if not self.distributed_registry:
            return
            
        distributed_tasks = self.distributed_registry.list_tasks()
        for task_dict in distributed_tasks:
            task_id = task_dict["task_id"]
            # Only update if distributed task is newer than local (simple check)
            if task_id not in self.tasks or task_dict.get("updated_at", 0) > self.tasks[task_id].updated_at:
                self.tasks[task_id] = Task.from_dict(task_dict)
        
        logger.debug(f"Synced {len(distributed_tasks)} tasks from distributed registry")

    def clear(self) -> None:
        """Clear all tasks"""
        self.tasks.clear()
        self._save()
        logger.info("Task manager cleared")
    
    def create_task(
        self,
        title: str,
        description: str,
        assignee: Optional[str] = None,
        priority: int = 5,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        Create a new task
        
        Args:
            title: Task title
            description: Task description
            assignee: Optional agent ID to assign task to
            priority: Task priority (1-10, 1 is highest)
            dependencies: List of task IDs this task depends on
            metadata: Optional metadata
            
        Returns:
            Created task
        """
        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Validate dependencies exist
        if dependencies:
            for dep_id in dependencies:
                if dep_id not in self.tasks:
                    logger.warning(f"Dependency {dep_id} does not exist, ignoring")
                    dependencies = [d for d in dependencies if d in self.tasks]
        
        task = Task(
            task_id=task_id,
            title=title,
            description=description,
            status=TaskStatus.ASSIGNED if assignee else TaskStatus.OPEN,
            assignee=assignee,
            priority=max(1, min(10, priority)),  # Clamp to 1-10
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        
        self.tasks[task_id] = task
        self._save()
        
        logger.info(f"Created task: {task_id} - {title} (priority: {priority})")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        assignee: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Task]:
        """
        List tasks with filters
        
        Args:
            status: Filter by status
            assignee: Filter by assignee
            limit: Maximum number of tasks to return
            
        Returns:
            List of tasks
        """
        tasks = list(self.tasks.values())
        
        # Apply filters
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        if assignee:
            tasks = [t for t in tasks if t.assignee == assignee]
        
        # Sort by priority (lower = higher priority) and creation time
        tasks.sort(key=lambda t: (t.priority, t.created_at))
        
        # Apply limit
        if limit:
            tasks = tasks[:limit]
        
        return tasks
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """
        Assign a task to an agent
        
        Args:
            task_id: Task ID
            agent_id: Agent ID to assign to
            
        Returns:
            True if successful, False otherwise
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return False
        
        # Check if dependencies are met
        if task.dependencies:
            for dep_id in task.dependencies:
                dep_task = self.get_task(dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    logger.warning(f"Task {task_id} has unmet dependencies")
                    return False
        
        task.assignee = agent_id
        task.status = TaskStatus.ASSIGNED
        task.updated_at = time.time()
        self._save()
        
        logger.info(f"Assigned task {task_id} to {agent_id}")
        return True
    
    def start_task(self, task_id: str) -> bool:
        """
        Mark task as in progress
        
        Args:
            task_id: Task ID
            
        Returns:
            True if successful, False otherwise
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return False
        
        if task.status != TaskStatus.ASSIGNED:
            logger.warning(f"Task {task_id} is not assigned, cannot start")
            return False
        
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = time.time()
        task.updated_at = time.time()
        self._save()
        
        logger.info(f"Started task {task_id}")
        return True
    
    def complete_task(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark task as completed
        
        Args:
            task_id: Task ID
            result: Optional result data
            
        Returns:
            True if successful, False otherwise
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return False
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = time.time()
        task.updated_at = time.time()
        
        if result:
            task.metadata["result"] = result
        
        self._save()
        logger.info(f"Completed task {task_id}")
        return True
    
    def fail_task(self, task_id: str, error: Optional[str] = None) -> bool:
        """
        Mark task as failed
        
        Args:
            task_id: Task ID
            error: Optional error message
            
        Returns:
            True if successful, False otherwise
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return False
        
        task.status = TaskStatus.FAILED
        task.updated_at = time.time()
        
        if error:
            task.metadata["error"] = error
        
        self._save()
        logger.warning(f"Task {task_id} failed: {error}")
        return True
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task
        
        Args:
            task_id: Task ID
            
        Returns:
            True if successful, False otherwise
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return False
        
        if task.status == TaskStatus.COMPLETED:
            logger.warning(f"Task {task_id} is already completed, cannot cancel")
            return False
        
        task.status = TaskStatus.CANCELLED
        task.updated_at = time.time()
        self._save()
        
        logger.info(f"Cancelled task {task_id}")
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get task manager statistics"""
        tasks_by_status = {}
        for status in TaskStatus:
            tasks_by_status[status.value] = len([t for t in self.tasks.values() if t.status == status])
        
        return {
            "total_tasks": len(self.tasks),
            "tasks_by_status": tasks_by_status,
            "tasks_by_priority": {
                f"priority_{i}": len([t for t in self.tasks.values() if t.priority == i])
                for i in range(1, 11)
            },
        }



