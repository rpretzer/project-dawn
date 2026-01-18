"""
CRDT (Conflict-free Replicated Data Type) Implementation

Simple CRDT map for distributed state synchronization.
"""

import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CRDTEntry:
    """CRDT entry with timestamp for conflict resolution"""
    value: Any
    timestamp: float
    node_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "value": self.value,
            "timestamp": self.timestamp,
            "node_id": self.node_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CRDTEntry":
        """Create from dictionary"""
        return cls(
            value=data["value"],
            timestamp=data["timestamp"],
            node_id=data["node_id"],
        )


class CRDTMap:
    """
    CRDT Map
    
    A conflict-free replicated data type for key-value maps.
    Uses last-write-wins (LWW) with timestamps for conflict resolution.
    """
    
    def __init__(self, node_id: str = "local"):
        """
        Initialize CRDT map
        
        Args:
            node_id: Node ID for this instance
        """
        self.node_id = node_id
        self.entries: Dict[str, CRDTEntry] = {}
        logger.debug(f"CRDTMap initialized for node {node_id[:16]}...")
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a value
        
        Args:
            key: Key
            value: Value
        """
        entry = CRDTEntry(
            value=value,
            timestamp=time.time(),
            node_id=self.node_id,
        )
        self.entries[key] = entry
        logger.debug(f"CRDT set: {key}")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value
        
        Args:
            key: Key
            
        Returns:
            Value or None
        """
        entry = self.entries.get(key)
        return entry.value if entry else None
    
    def remove(self, key: str) -> None:
        """
        Remove a key (tombstone)
        
        Args:
            key: Key to remove
        """
        if key in self.entries:
            del self.entries[key]
            logger.debug(f"CRDT remove: {key}")
    
    def has(self, key: str) -> bool:
        """Check if key exists"""
        return key in self.entries
    
    def keys(self) -> list:
        """Get all keys"""
        return list(self.entries.keys())
    
    def items(self) -> list:
        """Get all key-value pairs"""
        return [(k, v.value) for k, v in self.entries.items()]
    
    def get_all(self) -> Dict[str, Any]:
        """Get all key-value pairs as a dictionary"""
        return {k: v.value for k, v in self.entries.items()}
    
    def merge(self, other_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge with another CRDT state
        
        Uses last-write-wins (LWW) conflict resolution.
        
        Args:
            other_state: CRDT state from another node
            
        Returns:
            Merged state (dict of key -> value)
        """
        merged = {}
        
        # Process other state
        for key, entry_data in other_state.items():
            other_entry = CRDTEntry.from_dict(entry_data) if isinstance(entry_data, dict) and "value" in entry_data else CRDTEntry(value=entry_data, timestamp=time.time(), node_id="unknown")
            
            if isinstance(entry_data, dict) and "timestamp" in entry_data:
                other_entry = CRDTEntry.from_dict(entry_data)
            else:
                # Legacy format - just a value
                other_entry = CRDTEntry(
                    value=entry_data,
                    timestamp=time.time(),
                    node_id="unknown",
                )
            
            # Check if we have this key
            if key in self.entries:
                our_entry = self.entries[key]
                
                # Last-write-wins: keep entry with later timestamp
                if other_entry.timestamp > our_entry.timestamp:
                    self.entries[key] = other_entry
                    merged[key] = other_entry.value
                else:
                    merged[key] = our_entry.value
            else:
                # New key from other node
                self.entries[key] = other_entry
                merged[key] = other_entry.value
        
        # Add our keys that aren't in other state
        for key, entry in self.entries.items():
            if key not in merged:
                merged[key] = entry.value
        
        logger.debug(f"CRDT merged: {len(merged)} entries")
        return merged
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current state for synchronization
        
        Returns:
            Dictionary of key -> entry dict
        """
        return {
            key: entry.to_dict()
            for key, entry in self.entries.items()
        }
    
    def clear(self) -> None:
        """Clear all entries"""
        self.entries.clear()
        logger.debug("CRDT cleared")



