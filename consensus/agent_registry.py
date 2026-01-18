"""
Distributed Agent Registry

Maintains a distributed registry of agents across the P2P network.
Uses CRDT-like semantics for eventual consistency.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from .crdt import CRDTMap

logger = logging.getLogger(__name__)


@dataclass
class AgentInfo:
    """
    Information about an agent in the network
    
    Represents an agent that may be on this node or a remote peer.
    """
    agent_id: str  # Full ID: node_id:agent_id
    node_id: str
    local_agent_id: str  # Agent ID within the node
    name: str
    description: Optional[str] = None
    
    # Capabilities
    tools: List[Dict[str, Any]] = field(default_factory=list)
    resources: List[Dict[str, Any]] = field(default_factory=list)
    prompts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    registered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    
    # Health
    available: bool = True
    health_score: float = 1.0
    
    def update_activity(self) -> None:
        """Update last seen timestamp"""
        self.last_seen = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "node_id": self.node_id,
            "local_agent_id": self.local_agent_id,
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "resources": self.resources,
            "prompts": self.prompts,
            "metadata": self.metadata,
            "registered_at": self.registered_at,
            "last_seen": self.last_seen,
            "available": self.available,
            "health_score": self.health_score,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInfo":
        """Create from dictionary"""
        return cls(
            agent_id=data["agent_id"],
            node_id=data["node_id"],
            local_agent_id=data["local_agent_id"],
            name=data["name"],
            description=data.get("description"),
            tools=data.get("tools", []),
            resources=data.get("resources", []),
            prompts=data.get("prompts", []),
            metadata=data.get("metadata", {}),
            registered_at=data.get("registered_at", time.time()),
            last_seen=data.get("last_seen", time.time()),
            available=data.get("available", True),
            health_score=data.get("health_score", 1.0),
        )


class DistributedAgentRegistry:
    """
    Distributed agent registry
    
    Maintains a registry of all agents in the network, both local and remote.
    Uses CRDT-like semantics for eventual consistency across nodes.
    """
    
    def __init__(self, node_id: str):
        """
        Initialize distributed agent registry
        
        Args:
            node_id: This node's ID
        """
        self.node_id = node_id
        self.agents: Dict[str, AgentInfo] = {}  # agent_id -> AgentInfo
        self.crdt = CRDTMap()  # For distributed state synchronization
        
        logger.debug(f"DistributedAgentRegistry initialized for node {node_id[:16]}...")
    
    def register_local_agent(
        self,
        agent_id: str,
        name: str,
        description: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        resources: Optional[List[Dict[str, Any]]] = None,
        prompts: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentInfo:
        """
        Register a local agent
        
        Args:
            agent_id: Local agent ID (within this node)
            name: Agent name
            description: Agent description
            tools: List of tools
            resources: List of resources
            prompts: List of prompts
            metadata: Additional metadata
            
        Returns:
            AgentInfo for the registered agent
        """
        full_agent_id = f"{self.node_id}:{agent_id}"
        
        agent_info = AgentInfo(
            agent_id=full_agent_id,
            node_id=self.node_id,
            local_agent_id=agent_id,
            name=name,
            description=description,
            tools=tools or [],
            resources=resources or [],
            prompts=prompts or [],
            metadata=metadata or {},
        )
        
        self.agents[full_agent_id] = agent_info
        
        # Update CRDT
        self.crdt.set(full_agent_id, agent_info.to_dict())
        
        logger.info(f"Registered local agent: {full_agent_id} ({name})")
        return agent_info
    
    def unregister_local_agent(self, agent_id: str) -> None:
        """
        Unregister a local agent
        
        Args:
            agent_id: Local agent ID
        """
        full_agent_id = f"{self.node_id}:{agent_id}"
        
        if full_agent_id in self.agents:
            del self.agents[full_agent_id]
            self.crdt.remove(full_agent_id)
            logger.info(f"Unregistered local agent: {full_agent_id}")
    
    def register_remote_agent(self, agent_info: AgentInfo) -> None:
        """
        Register a remote agent (from another node)
        
        Args:
            agent_info: Agent information
        """
        # Don't overwrite local agents
        if agent_info.agent_id in self.agents:
            existing = self.agents[agent_info.agent_id]
            if existing.node_id == self.node_id:
                logger.warning(f"Attempted to register remote agent as local: {agent_info.agent_id}")
                return
        
        self.agents[agent_info.agent_id] = agent_info
        
        # Update CRDT
        self.crdt.set(agent_info.agent_id, agent_info.to_dict())
        
        logger.debug(f"Registered remote agent: {agent_info.agent_id} from {agent_info.node_id[:16]}...")
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """
        Get agent by ID
        
        Args:
            agent_id: Full agent ID (node_id:agent_id) or local agent ID
            
        Returns:
            AgentInfo or None
        """
        # Try full ID first
        if agent_id in self.agents:
            return self.agents[agent_id]
        
        # Try as local agent ID
        full_id = f"{self.node_id}:{agent_id}"
        if full_id in self.agents:
            return self.agents[full_id]
        
        return None
    
    def list_agents(
        self,
        node_id: Optional[str] = None,
        available_only: bool = False,
        local_only: bool = False,
    ) -> List[AgentInfo]:
        """
        List agents
        
        Args:
            node_id: Filter by node ID (optional)
            available_only: Only return available agents
            local_only: Only return local agents
            
        Returns:
            List of AgentInfo
        """
        agents = list(self.agents.values())
        
        if local_only:
            agents = [a for a in agents if a.node_id == self.node_id]
        
        if node_id:
            agents = [a for a in agents if a.node_id == node_id]
        
        if available_only:
            agents = [a for a in agents if a.available]
        
        return agents
    
    def list_local_agents(self) -> List[AgentInfo]:
        """List all local agents"""
        return self.list_agents(local_only=True)
    
    def list_remote_agents(self) -> List[AgentInfo]:
        """List all remote agents"""
        return [a for a in self.agents.values() if a.node_id != self.node_id]
    
    def find_agents_by_capability(
        self,
        capability_type: str,  # "tool", "resource", "prompt"
        capability_name: Optional[str] = None,
    ) -> List[AgentInfo]:
        """
        Find agents that have a specific capability
        
        Args:
            capability_type: Type of capability ("tool", "resource", "prompt")
            capability_name: Name of capability (optional)
            
        Returns:
            List of agents with the capability
        """
        agents = []
        
        for agent in self.agents.values():
            if not agent.available:
                continue
            
            if capability_type == "tool":
                capabilities = agent.tools
            elif capability_type == "resource":
                capabilities = agent.resources
            elif capability_type == "prompt":
                capabilities = agent.prompts
            else:
                continue
            
            if capability_name:
                # Check if specific capability exists
                if any(c.get("name") == capability_name for c in capabilities):
                    agents.append(agent)
            else:
                # Any capability of this type
                if capabilities:
                    agents.append(agent)
        
        return agents
    
    def update_agent_health(self, agent_id: str, health_score: float) -> None:
        """
        Update agent health score
        
        Args:
            agent_id: Agent ID
            health_score: Health score (0.0 to 1.0)
        """
        agent = self.get_agent(agent_id)
        if agent:
            agent.health_score = max(0.0, min(1.0, health_score))
            agent.update_activity()
    
    def mark_agent_unavailable(self, agent_id: str) -> None:
        """Mark agent as unavailable"""
        agent = self.get_agent(agent_id)
        if agent:
            agent.available = False
            agent.update_activity()
    
    def mark_agent_available(self, agent_id: str) -> None:
        """Mark agent as available"""
        agent = self.get_agent(agent_id)
        if agent:
            agent.available = True
            agent.update_activity()
    
    def sync_from_crdt(self, crdt_state: Dict[str, Any]) -> None:
        """
        Synchronize registry state from CRDT
        
        Args:
            crdt_state: CRDT state from another node
        """
        # Merge CRDT states
        merged = self.crdt.merge(crdt_state)
        
        # Update agents from merged state
        for agent_id, agent_data in merged.items():
            # Don't overwrite local agents
            if agent_id in self.agents:
                existing = self.agents[agent_id]
                if existing.node_id == self.node_id:
                    continue
            
            # Create or update agent info
            try:
                agent_info = AgentInfo.from_dict(agent_data)
                self.agents[agent_id] = agent_info
            except Exception as e:
                logger.warning(f"Failed to parse agent info for {agent_id}: {e}")
    
    def get_crdt_state(self) -> Dict[str, Any]:
        """Get current CRDT state for synchronization"""
        return self.crdt.get_state()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        local = self.list_local_agents()
        remote = self.list_remote_agents()
        available = [a for a in self.agents.values() if a.available]
        
        return {
            "total_agents": len(self.agents),
            "local_agents": len(local),
            "remote_agents": len(remote),
            "available_agents": len(available),
            "unavailable_agents": len(self.agents) - len(available),
        }



