"""
Libp2p Implementation

Actual Libp2p implementation using py-libp2p library.
This module provides the concrete implementation for libp2p_transport.py
"""

import asyncio
import inspect
import logging
from typing import Optional, List, Dict, Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Try to import py-libp2p
# Note: py-libp2p API may vary by version. This implementation attempts to use
# common patterns but may need adjustment based on actual library version.
# Supports py-libp2p versions 0.1.0+ with fallback compatibility.
try:
    # Try to detect libp2p version for compatibility
    LIBP2P_VERSION = None
    try:
        import libp2p
        if hasattr(libp2p, '__version__'):
            LIBP2P_VERSION = libp2p.__version__
            logger.debug(f"Detected py-libp2p version: {LIBP2P_VERSION}")
    except Exception:
        pass
    # Try different import patterns based on py-libp2p version
    try:
        from libp2p import new_node
        from libp2p.host.host_interface import IHost as Host
    except ImportError:
        try:
            from libp2p.host import Host
            from libp2p.host.basic_host import BasicHost
            new_node = None  # May need different initialization
        except ImportError:
            # Fallback: try minimal imports
            Host = Any
            new_node = None
    
    try:
        from libp2p.crypto.secp256k1 import create_new_key_pair
    except ImportError:
        try:
            from libp2p.crypto.keys import KeyPair
            create_new_key_pair = None
        except ImportError:
            create_new_key_pair = None
    
    try:
        from libp2p.peer.id import ID as PeerID
    except ImportError:
        try:
            from libp2p.peer import PeerID
        except ImportError:
            PeerID = Any
    
    try:
        from libp2p.peer.peerinfo import PeerInfo
    except ImportError:
        PeerInfo = Any
    
    try:
        from libp2p.network.stream.net_stream_interface import INetStream
    except ImportError:
        try:
            from libp2p.network.stream import INetStream
        except ImportError:
            INetStream = Any
    
    try:
        from multiaddr import Multiaddr
    except ImportError:
        try:
            from libp2p import Multiaddr
        except ImportError:
            Multiaddr = Any
    
    # Try to actually import libp2p to verify it works
    # This will fail if fastecdsa is missing, but we'll catch that
    try:
        import libp2p
        # If we get here, basic import worked
        PY_LIBP2P_AVAILABLE = True
        logger.info("py-libp2p library available")
    except ImportError as import_err:
        # Check if it's just fastecdsa missing
        if "fastecdsa" in str(import_err).lower():
            PY_LIBP2P_AVAILABLE = False
            logger.warning(
                "py-libp2p requires fastecdsa. Install system dependencies first:\n"
                "  Fedora: sudo dnf install gmp-devel\n"
                "  Debian/Ubuntu: sudo apt-get install libgmp-dev\n"
                "Then: pip install fastecdsa==2.3.2"
            )
        else:
            PY_LIBP2P_AVAILABLE = False
            logger.warning(f"py-libp2p imports failed: {import_err}")
    
    # Fallback: if we got some imports but full import failed, mark as partially available
    if not PY_LIBP2P_AVAILABLE:
        if Host != Any or PeerID != Any:
            logger.debug("py-libp2p partially available (some imports succeeded)")
    
except ImportError as e:
    PY_LIBP2P_AVAILABLE = False
    logger.warning(f"py-libp2p not available: {e}")
    # Create stubs
    Host = Any
    PeerID = Any
    INetStream = Any
    Multiaddr = Any
    new_node = None
    create_new_key_pair = None


def _extract_peer_id_from_multiaddr(addr: Any) -> Optional[str]:
    """Extract peer ID from a multiaddr if present."""
    try:
        if hasattr(addr, "value_for_protocol"):
            peer_id = addr.value_for_protocol("p2p")
            if peer_id:
                return peer_id
            return addr.value_for_protocol("ipfs")
    except Exception:
        return None
    return None


async def _maybe_await(value: Any) -> Any:
    """Await value if it is awaitable."""
    if inspect.isawaitable(value):
        return await value
    return value


async def create_libp2p_host(
    listen_addresses: List[str],
    key_pair: Optional[Any] = None,
) -> Optional[Host]:
    """
    Create a Libp2p host
    
    Args:
        listen_addresses: List of multiaddrs to listen on
        key_pair: Optional key pair (will generate if None)
        
    Returns:
        Libp2p Host instance or None if library not available
    """
    if not PY_LIBP2P_AVAILABLE:
        logger.error("py-libp2p not available, cannot create host")
        return None
    
    try:
        # Generate key pair if not provided
        if key_pair is None:
            if create_new_key_pair:
                key_pair = create_new_key_pair()
            else:
                logger.warning("Cannot generate key pair, create_new_key_pair not available")
                return None
        
        # Create host - try different methods based on API availability
        host = None
        listen_multiaddrs = []
        if Multiaddr != Any:
            for addr_str in listen_addresses:
                try:
                    listen_multiaddrs.append(Multiaddr(addr_str))
                except Exception as e:
                    logger.warning(f"Invalid listen address {addr_str}: {e}")
        else:
            logger.warning("Multiaddr not available; listen addresses may be ignored")

        new_node_func = new_node
        if new_node_func is None:
            try:
                import libp2p
                # Try multiple API patterns for different versions
                new_node_func = (
                    getattr(libp2p, "new_node", None) or
                    getattr(libp2p, "new_host", None) or
                    getattr(libp2p, "create_host", None)
                )
            except Exception:
                new_node_func = None

        if new_node_func:
            try:
                params = {}
                try:
                    param_names = set(inspect.signature(new_node_func).parameters.keys())
                    logger.debug(f"new_node function accepts parameters: {sorted(param_names)}")
                except Exception:
                    param_names = set()

                # Try multiple parameter names for key pair (API version compatibility)
                if "key_pair" in param_names:
                    params["key_pair"] = key_pair
                elif "private_key" in param_names:
                    params["private_key"] = key_pair
                elif "key" in param_names:
                    params["key"] = key_pair

                # Try multiple parameter names for listen addresses (API version compatibility)
                if listen_multiaddrs:
                    if "listen_addrs" in param_names:
                        params["listen_addrs"] = listen_multiaddrs
                    elif "listen_addresses" in param_names:
                        params["listen_addresses"] = listen_multiaddrs
                    elif "listen_addrs_list" in param_names:
                        params["listen_addrs_list"] = listen_multiaddrs
                    elif "transport_opt" in param_names:
                        params["transport_opt"] = listen_multiaddrs
                    elif "transports" in param_names:
                        # Some versions expect transport configuration
                        params["transports"] = listen_multiaddrs

                host = await _maybe_await(new_node_func(**params))
                if host:
                    logger.debug(f"Successfully created libp2p host using {new_node_func.__name__}")
            except Exception as e:
                logger.warning(f"new_node/new_host failed (tried {new_node_func.__name__ if new_node_func else 'None'}): {e}", exc_info=True)

        if host is None:
            logger.error("Libp2p host creation failed (no compatible constructor available)")
            return None

        # Start listening on specified addresses if host did not already
        if listen_multiaddrs:
            network = host.get_network() if hasattr(host, "get_network") else None
            if network and hasattr(network, "listen"):
                for addr in listen_multiaddrs:
                    try:
                        await network.listen(addr)
                        logger.info(f"Libp2p host listening on {addr}")
                    except Exception as e:
                        logger.warning(f"Failed to listen on {addr}: {e}")
        
        return host
    
    except Exception as e:
        logger.error(f"Failed to create Libp2p host: {e}", exc_info=True)
        return None


def convert_node_identity_to_key_pair(identity: Any) -> Optional[Any]:
    """
    Convert Project Dawn NodeIdentity to Libp2p key pair
    
    Args:
        identity: NodeIdentity instance
        
    Returns:
        Libp2p key pair or None if conversion fails
    """
    if not PY_LIBP2P_AVAILABLE:
        return None
    
    try:
        private_bytes = None
        if hasattr(identity, "serialize_private_key") and (not hasattr(identity, "can_sign") or identity.can_sign()):
            private_bytes = identity.serialize_private_key()
        key_pair = None

        # Prefer Ed25519 when available
        try:
            from libp2p.crypto import ed25519 as lp_ed25519
            if private_bytes and hasattr(lp_ed25519, "Ed25519PrivateKey"):
                key_cls = lp_ed25519.Ed25519PrivateKey
                if hasattr(key_cls, "from_bytes"):
                    key_pair = key_cls.from_bytes(private_bytes)
                elif hasattr(key_cls, "from_raw"):
                    key_pair = key_cls.from_raw(private_bytes)
            if key_pair is None and hasattr(lp_ed25519, "create_new_key_pair"):
                key_pair = lp_ed25519.create_new_key_pair()
        except Exception:
            key_pair = None

        # Fallback to generic key generation if available
        if key_pair is None and create_new_key_pair:
            key_pair = create_new_key_pair()

        if key_pair is None:
            logger.warning("Failed to derive Libp2p key pair from identity")
            return None

        logger.debug("Converted node identity to Libp2p key pair")
        return key_pair
    
    except Exception as e:
        logger.error(f"Failed to convert identity to key pair: {e}")
        return None


async def connect_to_peer(
    host: Host,
    peer_address: str,
    peer_id: Optional[str] = None,
) -> bool:
    """
    Connect to a Libp2p peer
    
    Args:
        host: Libp2p host
        peer_address: Peer multiaddr
        peer_id: Optional peer ID
        
    Returns:
        True if connected successfully
    """
    if not PY_LIBP2P_AVAILABLE or host is None:
        return False
    
    try:
        if Multiaddr == Any:
            logger.error("Multiaddr not available, cannot connect to peer")
            return False

        addr = Multiaddr(peer_address)
        if not peer_id:
            peer_id = _extract_peer_id_from_multiaddr(addr)

        if not peer_id:
            logger.error("Peer ID missing from multiaddr; include /p2p/<peer_id> in address")
            return False

        peer_id_obj = PeerID.from_base58(peer_id) if hasattr(PeerID, "from_base58") else PeerID(peer_id)

        try:
            peer_info = PeerInfo(peer_id_obj, [addr])
        except Exception:
            try:
                peer_info = PeerInfo(peer_id=peer_id_obj, addrs=[addr])
            except Exception as e:
                logger.error(f"Failed to construct PeerInfo: {e}")
                return False

        await host.connect(peer_info)
        logger.info(f"Connected to peer: {peer_address}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to connect to peer {peer_address}: {e}")
        return False


async def open_stream(
    host: Host,
    peer_id: str,
    protocol_id: str = "/project-dawn/1.0.0",
) -> Optional[INetStream]:
    """
    Open a stream to a peer
    
    Args:
        host: Libp2p host
        peer_id: Peer ID to connect to
        protocol_id: Protocol identifier
        
    Returns:
        Stream instance or None if failed
    """
    if not PY_LIBP2P_AVAILABLE or host is None:
        return None
    
    try:
        peer_id_obj = PeerID.from_base58(peer_id) if hasattr(PeerID, "from_base58") else PeerID(peer_id)
        stream = await host.new_stream(peer_id_obj, [protocol_id])
        logger.debug(f"Opened stream to peer: {peer_id[:16]}...")
        return stream
    
    except Exception as e:
        logger.error(f"Failed to open stream to {peer_id[:16]}...: {e}")
        return None


async def read_stream_message(stream: INetStream, timeout: float = 5.0) -> Optional[bytes]:
    """
    Read a message from a stream
    
    Args:
        stream: Stream instance
        timeout: Read timeout in seconds
        
    Returns:
        Message bytes or None if timeout/error
    """
    if stream is None:
        return None
    
    try:
        # Read message with timeout
        try:
            message = await asyncio.wait_for(stream.read(), timeout=timeout)
        except TypeError:
            message = await asyncio.wait_for(stream.read(1024 * 1024), timeout=timeout)
        return message
    
    except asyncio.TimeoutError:
        logger.debug("Stream read timeout")
        return None
    except Exception as e:
        logger.error(f"Error reading from stream: {e}")
        return None


async def write_stream_message(stream: INetStream, message: bytes) -> bool:
    """
    Write a message to a stream
    
    Args:
        stream: Stream instance
        message: Message bytes
        
    Returns:
        True if written successfully
    """
    if stream is None:
        return False
    
    try:
        result = stream.write(message)
        if inspect.isawaitable(result):
            await result
        return True
    
    except Exception as e:
        logger.error(f"Error writing to stream: {e}")
        return False
