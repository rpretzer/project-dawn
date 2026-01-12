"""
Peer Registry

Manages local registry of known peers.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from .peer import Peer
from data_paths import data_root

logger = logging.getLogger(__name__)


class PeerRegistry:
    """
    Local peer registry
    
    Maintains a registry of known peers with health tracking.
    """
    
    def __init__(self, peer_timeout: float = 300.0, peer_validator: Optional[Any] = None, 
                 data_dir: Optional[Path] = None, persist: bool = True):
        """
        Initialize peer registry
        
        Args:
            peer_timeout: Seconds before considering peer dead (default 5 minutes)
            peer_validator: Optional peer validator for trust checks
            data_dir: Data directory for persistence (defaults to data_root/mesh)
            persist: Enable persistence (default True)
        """
        self.peers: Dict[str, Peer] = {}  # node_id -> Peer
        self.peer_timeout = peer_timeout
        self.peer_validator = peer_validator
        self.persist = persist
        self.data_dir = data_dir or data_root() / "mesh"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.peer_registry_path = self.data_dir / "peer_registry.json"
        
        self.on_peer_added: Optional[Callable[[Peer], None]] = None
        self.on_peer_removed: Optional[Callable[[Peer], None]] = None
        self.on_peer_updated: Optional[Callable[[Peer], None]] = None
        
        # Load persisted peers
        if self.persist:
            self._load()
        
        logger.debug(f"PeerRegistry initialized with {len(self.peers)} peers")
    
    def add_peer(self, peer: Peer, skip_validation: bool = False) -> bool:
        """
        Add or update peer in registry
        
        Args:
            peer: Peer to add/update
            skip_validation: Skip trust validation (for bootstrap/trusted peers)
            
        Returns:
            True if peer was added/updated, False if rejected
        """
        # Validate peer if validator is available
        if self.peer_validator and not skip_validation:
            if not self.peer_validator.can_connect(peer.node_id):
                logger.warning(f"Rejected peer {peer.node_id[:16]}... (not trusted)")
                return False
        
        is_new = peer.node_id not in self.peers
        
        if is_new:
            self.peers[peer.node_id] = peer
            logger.info(f"Added peer: {peer.node_id[:16]}... ({peer.address})")
            if self.on_peer_added:
                self.on_peer_added(peer)
        else:
            # Update existing peer
            old_peer = self.peers[peer.node_id]
            self.peers[peer.node_id] = peer
            logger.debug(f"Updated peer: {peer.node_id[:16]}...")
            if self.on_peer_updated:
                self.on_peer_updated(peer)
        
        # Persist changes
        if self.persist:
            self._save()
        
        return True
    
    def remove_peer(self, node_id: str) -> Optional[Peer]:
        """
        Remove peer from registry
        
        Args:
            node_id: Node ID of peer to remove
            
        Returns:
            Removed peer or None if not found
        """
        if node_id in self.peers:
            peer = self.peers.pop(node_id)
            logger.info(f"Removed peer: {node_id[:16]}...")
            if self.on_peer_removed:
                self.on_peer_removed(peer)
            # Persist changes
            if self.persist:
                self._save()
            return peer
        return None
    
    def get_peer(self, node_id: str) -> Optional[Peer]:
        """
        Get peer by node ID
        
        Args:
            node_id: Node ID
            
        Returns:
            Peer or None if not found
        """
        return self.peers.get(node_id)
    
    def get_peer_by_address(self, address: str) -> Optional[Peer]:
        """
        Get peer by address
        
        Args:
            address: Peer address
            
        Returns:
            Peer or None if not found
        """
        for peer in self.peers.values():
            if peer.address == address:
                return peer
        return None
    
    def list_peers(self, alive_only: bool = False) -> List[Peer]:
        """
        List all peers
        
        Args:
            alive_only: Only return alive peers
            
        Returns:
            List of peers
        """
        peers = list(self.peers.values())
        
        if alive_only:
            peers = [p for p in peers if p.is_alive(self.peer_timeout)]
        
        return peers
    
    def list_connected_peers(self) -> List[Peer]:
        """List all connected peers"""
        return [p for p in self.peers.values() if p.connected]
    
    def list_alive_peers(self) -> List[Peer]:
        """List all alive peers"""
        return self.list_peers(alive_only=True)
    
    def cleanup_dead_peers(self) -> List[Peer]:
        """
        Remove dead peers from registry
        
        Returns:
            List of removed peers
        """
        dead_peers = []
        current_time = time.time()
        
        for node_id, peer in list(self.peers.items()):
            if not peer.is_alive(self.peer_timeout):
                dead_peers.append(self.remove_peer(node_id))
                logger.debug(f"Removed dead peer: {node_id[:16]}... (last seen {current_time - peer.last_seen:.0f}s ago)")
        
        return dead_peers
    
    def update_peer_activity(self, node_id: str) -> bool:
        """
        Update peer's last seen timestamp
        
        Args:
            node_id: Node ID
            
        Returns:
            True if peer found and updated, False otherwise
        """
        peer = self.get_peer(node_id)
        if peer:
            peer.update_activity()
            return True
        return False
    
    def get_peer_count(self) -> int:
        """Get total number of peers"""
        return len(self.peers)
    
    def get_alive_peer_count(self) -> int:
        """Get number of alive peers"""
        return len(self.list_alive_peers())
    
    def get_connected_peer_count(self) -> int:
        """Get number of connected peers"""
        return len(self.list_connected_peers())
    
    def has_peer(self, node_id: str) -> bool:
        """Check if peer exists in registry"""
        return node_id in self.peers
    
    def clear(self) -> None:
        """Clear all peers from registry"""
        self.peers.clear()
        logger.debug("Peer registry cleared")
        # Persist changes
        if self.persist:
            self._save()
    
    def get_peer_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        alive = self.list_alive_peers()
        connected = self.list_connected_peers()
        
        return {
            "total_peers": len(self.peers),
            "alive_peers": len(alive),
            "connected_peers": len(connected),
            "dead_peers": len(self.peers) - len(alive),
            "average_health_score": sum(p.health_score for p in self.peers.values()) / len(self.peers) if self.peers else 0.0,
        }
    
    def _load(self) -> None:
        """Load peer registry from disk"""
        if not self.peer_registry_path.exists():
            return
        
        try:
            data = json.loads(self.peer_registry_path.read_text(encoding="utf-8"))
            for item in data.get("peers", []):
                peer = Peer.from_dict(item)
                self.peers[peer.node_id] = peer
            logger.debug(f"Loaded {len(self.peers)} peers from {self.peer_registry_path}")
        except Exception as e:
            logger.warning(f"Failed to load peer registry: {e}")
    
    def _save(self) -> None:
        """Save peer registry to disk (atomic write)"""
        try:
            data = {
                "version": 1,
                "peers": [peer.to_dict() for peer in self.peers.values()],
            }
            tmp_path = self.peer_registry_path.with_suffix(".json.tmp")
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp_path.replace(self.peer_registry_path)
            logger.debug(f"Saved {len(self.peers)} peers to {self.peer_registry_path}")
        except Exception as e:
            logger.error(f"Failed to save peer registry: {e}")



