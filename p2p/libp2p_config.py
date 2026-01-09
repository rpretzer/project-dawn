"""
Libp2p Configuration

Configuration for Libp2p transport and discovery.
"""

import os
from typing import List, Optional, Dict, Any
from pathlib import Path


def get_libp2p_config(
    base_path: Optional[Path] = None,
    node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get Libp2p configuration
    
    Args:
        base_path: Base path for data storage
        node_id: Node ID for peer identification
        
    Returns:
        Configuration dictionary
    """
    base_path = base_path or Path("data")
    
    config = {
        # Transport configuration
        "transports": {
            "tcp": {
                "enabled": True,
                "listen_addresses": [
                    "/ip4/0.0.0.0/tcp/8000",
                    "/ip6/::/tcp/8000",
                ],
            },
            "websocket": {
                "enabled": True,
                "listen_addresses": [
                    "/ip4/0.0.0.0/tcp/8001/ws",
                ],
            },
            "quic": {
                "enabled": False,  # Enable if QUIC support available
                "listen_addresses": [
                    "/ip4/0.0.0.0/udp/8002/quic",
                ],
            },
        },
        
        # Discovery configuration
        "discovery": {
            "mdns": {
                "enabled": os.getenv("LIBP2P_MDNS_ENABLED", "true").lower() == "true",
                "service_name": "project-dawn",
            },
            "dht": {
                "enabled": os.getenv("LIBP2P_DHT_ENABLED", "true").lower() == "true",
                "bootstrap_peers": _get_bootstrap_peers(),
                "kademlia": {
                    "bucket_size": 20,
                    "alpha": 3,
                },
            },
            "bootstrap": {
                "enabled": True,
                "peers": _get_bootstrap_peers(),
            },
        },
        
        # Security configuration
        "security": {
            "noise": {
                "enabled": True,
            },
            "tls": {
                "enabled": False,  # Enable if TLS support available
            },
        },
        
        # Stream multiplexing
        "muxers": {
            "mplex": {
                "enabled": True,
            },
            "yamux": {
                "enabled": True,
            },
        },
        
        # NAT traversal
        "nat": {
            "enabled": True,
            "upnp": {
                "enabled": True,
            },
            "hole_punching": {
                "enabled": True,
            },
        },
        
        # Connection management
        "connection": {
            "max_connections": 100,
            "connection_timeout": 30.0,
            "keep_alive": True,
            "keep_alive_interval": 60.0,
        },
        
        # Data paths
        "paths": {
            "data_dir": str(base_path / "libp2p"),
            "keys_dir": str(base_path / "libp2p" / "keys"),
        },
    }
    
    return config


def _get_bootstrap_peers() -> List[str]:
    """Get bootstrap peer addresses from environment or defaults"""
    bootstrap_env = os.getenv("LIBP2P_BOOTSTRAP_PEERS", "")
    if bootstrap_env:
        return [addr.strip() for addr in bootstrap_env.split(",") if addr.strip()]
    
    # Default: empty list (no bootstrap peers)
    # Users can configure bootstrap peers via environment variable
    return []


def get_listen_addresses(config: Optional[Dict[str, Any]] = None) -> List[str]:
    """Get listen addresses from config"""
    if config is None:
        config = get_libp2p_config()
    
    addresses = []
    for transport_name, transport_config in config["transports"].items():
        if transport_config.get("enabled", False):
            addresses.extend(transport_config.get("listen_addresses", []))
    
    return addresses


def get_bootstrap_peers(config: Optional[Dict[str, Any]] = None) -> List[str]:
    """Get bootstrap peer addresses from config"""
    if config is None:
        config = get_libp2p_config()
    
    return config["discovery"]["bootstrap"]["peers"]
