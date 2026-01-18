"""
Distributed Task Registry

Maintains a distributed registry of tasks across the P2P network.
Uses CRDT-like semantics for eventual consistency.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from .crdt import CRDTMap

logger = logging.getLogger(__name__)

class DistributedTaskRegistry:
    """
    Distributed task registry
    
    Maintains a registry of all tasks in the network.
    Uses CRDT-like semantics for eventual consistency across nodes.
    """
    
    def __init__(self, node_id: str):
        """
        Initialize distributed task registry
        
        Args:
            node_id: This node's ID
        """
        self.node_id = node_id
        self.crdt = CRDTMap(node_id)
        
        logger.debug(f"DistributedTaskRegistry initialized for node {node_id[:16]}...")
    
    def update_task(self, task_dict: Dict[str, Any]) -> None:
        """
        Update or add a task in the registry
        
        Args:
            task_dict: Dictionary representation of the Task
        """
        task_id = task_dict["task_id"]
        self.crdt.set(task_id, task_dict)
        logger.debug(f"Task registry updated: {task_id}")
    
    def remove_task(self, task_id: str) -> None:
        """Remove a task from the registry"""
        self.crdt.remove(task_id)
        logger.debug(f"Task removed from registry: {task_id}")
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task data by ID"""
        return self.crdt.get(task_id)
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks in the registry"""
        return list(self.crdt.get_all().values())
    
    def sync_from_crdt(self, crdt_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronize registry state from CRDT
        
        Args:
            crdt_state: CRDT state from another node
            
        Returns:
            The merged state
        """
        return self.crdt.merge(crdt_state)
    
    def get_crdt_state(self) -> Dict[str, Any]:
        """Get current CRDT state for synchronization"""
        return self.crdt.get_state()
