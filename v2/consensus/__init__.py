"""
Consensus and Distributed State

CRDT and distributed registry implementations.
"""

from .crdt import CRDTMap, CRDTEntry
from .agent_registry import DistributedAgentRegistry, AgentInfo

__all__ = [
    "CRDTMap",
    "CRDTEntry",
    "DistributedAgentRegistry",
    "AgentInfo",
]



