"""
Core memory abstractions and data structures for memOS
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import time
import uuid
import json


class MemoryType(Enum):
    """Types of memory storage formats"""
    PARAMETRIC = "parametric"      # Model weights, LoRA modules
    ACTIVATION = "activation"       # KV-cache, hidden states
    PLAINTEXT = "plaintext"        # Documents, text, structured data


class MemoryState(Enum):
    """Memory lifecycle states"""
    GENERATED = "generated"        # Newly created
    ACTIVATED = "activated"        # Currently in use
    MERGED = "merged"             # Combined with other memories
    ARCHIVED = "archived"         # Stored for long-term


@dataclass
class MemCube:
    """
    Core memory abstraction unifying all memory types.
    The fundamental unit of memory in memOS.
    """
    # Memory Payload
    memory_id: str
    content: Any
    memory_type: MemoryType
    
    # Descriptive Metadata
    timestamp: float
    origin_signature: str          # Creator/source identifier
    semantic_type: str            # Domain-specific type (e.g., "insight", "fact", "experience")
    namespace: Tuple[str, str, str]  # (user_id, context, scope)
    
    # Governance Attributes
    access_control: Dict[str, List[str]]  # {role: [permissions]}
    ttl: Optional[int]            # Time-to-live in seconds
    priority_level: int           # 1-10, higher = more important
    compliance_tags: List[str]    # e.g., ["pii", "confidential"]
    
    # Behavioral Usage
    access_count: int = 0
    last_access: float = None
    contextual_fingerprint: str = ""
    version_chain: List[str] = None      # Previous version IDs
    state: MemoryState = MemoryState.GENERATED
    
    # Relationships
    related_memories: List[str] = None    # IDs of related memories
    parent_memory: Optional[str] = None   # Parent memory ID
    child_memories: List[str] = None      # Child memory IDs
    
    def __post_init__(self):
        """Initialize default values"""
        if self.memory_id is None:
            self.memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        if self.version_chain is None:
            self.version_chain = []
        if self.last_access is None:
            self.last_access = self.timestamp
        if self.related_memories is None:
            self.related_memories = []
        if self.child_memories is None:
            self.child_memories = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "memory_id": self.memory_id,
            "content": self.content if isinstance(self.content, (str, dict, list)) else str(self.content),
            "memory_type": self.memory_type.value,
            "timestamp": self.timestamp,
            "origin_signature": self.origin_signature,
            "semantic_type": self.semantic_type,
            "namespace": list(self.namespace),
            "access_control": self.access_control,
            "ttl": self.ttl,
            "priority_level": self.priority_level,
            "compliance_tags": self.compliance_tags,
            "access_count": self.access_count,
            "last_access": self.last_access,
            "contextual_fingerprint": self.contextual_fingerprint,
            "version_chain": self.version_chain,
            "state": self.state.value,
            "related_memories": self.related_memories,
            "parent_memory": self.parent_memory,
            "child_memories": self.child_memories
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemCube':
        """Create from dictionary"""
        return cls(
            memory_id=data.get("memory_id"),
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            timestamp=data["timestamp"],
            origin_signature=data["origin_signature"],
            semantic_type=data["semantic_type"],
            namespace=tuple(data["namespace"]),
            access_control=data["access_control"],
            ttl=data.get("ttl"),
            priority_level=data.get("priority_level", 1),
            compliance_tags=data.get("compliance_tags", []),
            access_count=data.get("access_count", 0),
            last_access=data.get("last_access"),
            contextual_fingerprint=data.get("contextual_fingerprint", ""),
            version_chain=data.get("version_chain", []),
            state=MemoryState(data.get("state", "generated")),
            related_memories=data.get("related_memories", []),
            parent_memory=data.get("parent_memory"),
            child_memories=data.get("child_memories", [])
        )
    
    def update_access(self):
        """Update access statistics"""
        self.access_count += 1
        self.last_access = time.time()
    
    def add_relation(self, memory_id: str):
        """Add a related memory"""
        if memory_id not in self.related_memories:
            self.related_memories.append(memory_id)
    
    def transition_state(self, new_state: MemoryState):
        """Transition to new state"""
        self.state = new_state
    
    def is_expired(self) -> bool:
        """Check if memory has expired"""
        if self.ttl is None:
            return False
        return (time.time() - self.timestamp) > self.ttl
    
    def get_age(self) -> float:
        """Get age of memory in seconds"""
        return time.time() - self.timestamp
    
    def matches_namespace(self, namespace: Tuple[str, str, str]) -> bool:
        """Check if memory matches namespace pattern"""
        for i, component in enumerate(namespace):
            if component != "*" and component != self.namespace[i]:
                return False
        return True
    
    def has_permission(self, role: str, permission: str) -> bool:
        """Check if role has permission"""
        if role in self.access_control:
            return permission in self.access_control[role]
        return False
    
    def create_child(self, content: Any, semantic_type: str) -> 'MemCube':
        """Create a child memory"""
        child = MemCube(
            memory_id=None,
            content=content,
            memory_type=self.memory_type,
            timestamp=time.time(),
            origin_signature=self.origin_signature,
            semantic_type=semantic_type,
            namespace=self.namespace,
            access_control=self.access_control.copy(),
            ttl=self.ttl,
            priority_level=self.priority_level,
            compliance_tags=self.compliance_tags.copy(),
            parent_memory=self.memory_id
        )
        
        if self.memory_id not in self.child_memories:
            self.child_memories.append(child.memory_id)
        
        return child
    
    def __repr__(self):
        return f"MemCube(id={self.memory_id}, type={self.memory_type.value}, semantic={self.semantic_type})"


@dataclass
class MemoryQuery:
    """Structured query for memory retrieval"""
    query_type: str                      # "semantic", "temporal", "relational", "hybrid"
    parameters: Dict[str, Any]
    namespace: Tuple[str, str, str]
    requester_id: str
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_type": self.query_type,
            "parameters": self.parameters,
            "namespace": list(self.namespace),
            "requester_id": self.requester_id,
            "context": self.context
        }


@dataclass
class MemoryRelation:
    """Relationship between memories"""
    source_id: str
    target_id: str
    relation_type: str                   # "derives_from", "contradicts", "supports", etc.
    strength: float = 1.0               # 0-1, strength of relationship
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "strength": self.strength,
            "metadata": self.metadata
        }