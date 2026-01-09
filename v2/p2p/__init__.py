"""
Peer-to-Peer Networking

P2P networking components for decentralized MCP network.
"""

from .peer import Peer
from .peer_registry import PeerRegistry
from .discovery import (
    BootstrapDiscovery,
    MDNSDiscovery,
    GossipDiscovery,
    PeerDiscovery,
)
from .p2p_node import P2PNode

# Libp2p components (optional, may not be fully implemented)
try:
    from .libp2p_node import Libp2pP2PNode
    from .libp2p_transport import Libp2pTransport, Libp2pTransportAdapter
    from .libp2p_config import get_libp2p_config
    LIBP2P_AVAILABLE = True
except (ImportError, AttributeError):
    # Libp2p not available or not fully implemented
    LIBP2P_AVAILABLE = False
    Libp2pP2PNode = None
    Libp2pTransport = None
    Libp2pTransportAdapter = None
    get_libp2p_config = None

__all__ = [
    "Peer",
    "PeerRegistry",
    "BootstrapDiscovery",
    "MDNSDiscovery",
    "GossipDiscovery",
    "PeerDiscovery",
    "P2PNode",
    # Libp2p (optional)
    "LIBP2P_AVAILABLE",
    "Libp2pP2PNode",
    "Libp2pTransport",
    "Libp2pTransportAdapter",
    "get_libp2p_config",
]

