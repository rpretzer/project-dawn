"""
Peer Representation

Represents a peer node in the P2P network.
"""

import logging
import time
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from crypto import NodeIdentity

logger = logging.getLogger(__name__)


@dataclass
class Peer:
    """
    Peer node representation
    
    Contains information about a peer in the network.
    """
    node_id: str
    address: str  # Peer address (WebSocket URL or Libp2p multiaddr)
    peer_id: Optional[str] = None  # Libp2p peer ID (optional)
    public_key: Optional[bytes] = None  # Ed25519 public key
    identity: Optional[NodeIdentity] = None  # Full identity (if available)
    
    # Connection state
    connected: bool = False
    last_seen: float = field(default_factory=time.time)
    first_seen: float = field(default_factory=time.time)
    
    # Capabilities
    agents: List[str] = field(default_factory=list)  # List of agent IDs on this peer
    tools: List[Dict[str, Any]] = field(default_factory=list)  # Tools available
    resources: List[Dict[str, Any]] = field(default_factory=list)  # Resources available
    prompts: List[Dict[str, Any]] = field(default_factory=list)  # Prompts available
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Health
    health_score: float = 1.0  # 0.0 to 1.0, based on connection success rate
    connection_attempts: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    
    def update_activity(self) -> None:
        """Update last seen timestamp"""
        self.last_seen = time.time()
    
    def is_alive(self, timeout: float = 300.0) -> bool:
        """
        Check if peer is considered alive
        
        Args:
            timeout: Seconds since last_seen to consider peer dead
            
        Returns:
            True if peer is alive, False otherwise
        """
        return (time.time() - self.last_seen) < timeout
    
    def get_age(self) -> float:
        """Get age of peer entry in seconds"""
        return time.time() - self.first_seen
    
    def record_connection_success(self) -> None:
        """Record successful connection"""
        self.connection_attempts += 1
        self.successful_connections += 1
        self.health_score = min(1.0, self.health_score + 0.1)
        self.update_activity()
    
    def record_connection_failure(self) -> None:
        """Record failed connection"""
        self.connection_attempts += 1
        self.failed_connections += 1
        self.health_score = max(0.0, self.health_score - 0.2)
    
    def get_connection_success_rate(self) -> float:
        """Get connection success rate"""
        if self.connection_attempts == 0:
            return 1.0
        return self.successful_connections / self.connection_attempts
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert peer to dictionary"""
        return {
            "node_id": self.node_id,
            "address": self.address,
            "peer_id": self.peer_id,
            "public_key": self.public_key.hex() if self.public_key else None,
            "connected": self.connected,
            "last_seen": self.last_seen,
            "first_seen": self.first_seen,
            "agents": self.agents,
            "tools_count": len(self.tools),
            "resources_count": len(self.resources),
            "prompts_count": len(self.prompts),
            "health_score": self.health_score,
            "connection_attempts": self.connection_attempts,
            "successful_connections": self.successful_connections,
            "failed_connections": self.failed_connections,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Peer":
        """Create peer from dictionary"""
        peer = cls(
            node_id=data["node_id"],
            address=data["address"],
            peer_id=data.get("peer_id"),
            public_key=bytes.fromhex(data["public_key"]) if data.get("public_key") else None,
            connected=data.get("connected", False),
            last_seen=data.get("last_seen", time.time()),
            first_seen=data.get("first_seen", time.time()),
            agents=data.get("agents", []),
            tools=data.get("tools", []),
            resources=data.get("resources", []),
            prompts=data.get("prompts", []),
            metadata=data.get("metadata", {}),
            health_score=data.get("health_score", 1.0),
            connection_attempts=data.get("connection_attempts", 0),
            successful_connections=data.get("successful_connections", 0),
            failed_connections=data.get("failed_connections", 0),
        )
        return peer
    
    def __repr__(self) -> str:
        status = "connected" if self.connected else "disconnected"
        agents_str = f", {len(self.agents)} agents" if self.agents else ""
        return f"Peer(node_id={self.node_id[:16]}..., address={self.address}, {status}{agents_str})"


