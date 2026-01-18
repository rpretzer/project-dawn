"""
Libp2p Transport Layer

Libp2p-based transport for MCP protocol, replacing custom WebSocket transport.
Provides multi-transport support, automatic NAT traversal, and battle-tested peer discovery.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional, Callable, Awaitable, List
from enum import Enum

logger = logging.getLogger(__name__)

# Feature flag: Libp2p support (disabled by default until fully implemented)
LIBP2P_ENABLED = os.getenv("LIBP2P_ENABLED", "false").lower() == "true"

# Import Libp2p implementation helpers
from .libp2p_impl import (
    PY_LIBP2P_AVAILABLE,
    create_libp2p_host,
    convert_node_identity_to_key_pair,
    connect_to_peer as libp2p_connect,
    open_stream as libp2p_open_stream,
    read_stream_message,
    write_stream_message,
)

# Try to import py-libp2p types
LIBP2P_AVAILABLE = False
Host = Any
PeerID = Any
Multiaddr = Any
INetStream = Any

try:
    if LIBP2P_ENABLED and PY_LIBP2P_AVAILABLE:
        # Try to import libp2p - if this works, we're good
        import libp2p  # type: ignore[reportMissingImports]
        from multiaddr import Multiaddr  # type: ignore[reportMissingImports]
        
        # Try to import specific types (may vary by version)
        try:
            from libp2p.host.host_interface import IHost as Host  # type: ignore[reportMissingImports]
        except ImportError:
            try:
                from libp2p.host import Host  # type: ignore[reportMissingImports]
            except ImportError:
                Host = Any
        
        try:
            from libp2p.peer.id import ID as PeerID  # type: ignore[reportMissingImports]
        except ImportError:
            try:
                from libp2p.peer import PeerID  # type: ignore[reportMissingImports]
            except ImportError:
                PeerID = Any
        
        try:
            from libp2p.network.stream.net_stream_interface import INetStream  # type: ignore[reportMissingImports]
        except ImportError:
            try:
                from libp2p.network.stream import INetStream  # type: ignore[reportMissingImports]
            except ImportError:
                INetStream = Any
        
        # If we got here, libp2p is available
        LIBP2P_AVAILABLE = True
        logger.info("py-libp2p available and enabled")
    else:
        if not LIBP2P_ENABLED:
            logger.debug("Libp2p disabled by feature flag (set LIBP2P_ENABLED=true to enable)")
        elif not PY_LIBP2P_AVAILABLE:
            logger.debug("Libp2p implementation not available")
except ImportError as e:
    if LIBP2P_ENABLED:
        logger.warning(f"Libp2p enabled but py-libp2p not available: {e}")


class Libp2pTransportState(Enum):
    """Libp2p transport state"""
    DISCONNECTED = "disconnected"
    STARTING = "starting"
    LISTENING = "listening"
    CONNECTED = "connected"
    ERROR = "error"


class Libp2pTransport:
    """
    Libp2p transport for MCP protocol
    
    Provides Libp2p-based transport with automatic peer discovery,
    NAT traversal, and multi-transport support.
    """
    
    def __init__(
        self,
        identity: Any,  # NodeIdentity
        listen_addresses: Optional[List[str]] = None,
        bootstrap_peers: Optional[List[str]] = None,
        enable_mdns: bool = True,
        enable_dht: bool = True,
        message_handler: Optional[Callable[[str, str], Awaitable[Optional[str]]]] = None,
        on_peer_connect: Optional[Callable[[str], Awaitable[None]]] = None,
        on_peer_disconnect: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        """
        Initialize Libp2p transport
        
        Args:
            identity: Node identity (for Libp2p peer ID)
            listen_addresses: List of addresses to listen on (e.g., ["/ip4/0.0.0.0/tcp/8000"])
            bootstrap_peers: List of bootstrap peer addresses
            enable_mdns: Enable mDNS discovery
            enable_dht: Enable DHT discovery
            message_handler: Handler for incoming messages (peer_id, message) -> response
            on_peer_connect: Callback when peer connects
            on_peer_disconnect: Callback when peer disconnects
            
        Raises:
            RuntimeError: If Libp2p is not available or not enabled
        """
        if not LIBP2P_ENABLED:
            raise RuntimeError(
                "Libp2p transport is disabled. Set LIBP2P_ENABLED=true to enable."
            )
        if not LIBP2P_AVAILABLE:
            # Check if it's a missing dependency issue
            try:
                import libp2p  # type: ignore[reportMissingImports]
            except ImportError as e:
                if "fastecdsa" in str(e).lower():
                    raise RuntimeError(
                        "py-libp2p requires fastecdsa. Install system dependencies:\n"
                        "  Fedora: sudo dnf install gmp-devel\n"
                        "  Debian/Ubuntu: sudo apt-get install libgmp-dev\n"
                        "Then: pip install fastecdsa==2.3.2"
                    )
                else:
                    raise RuntimeError(
                        f"py-libp2p not available: {e}\n"
                        "Install with: pip install libp2p"
                    )
            else:
                # Import worked but LIBP2P_AVAILABLE is False - shouldn't happen
                raise RuntimeError("py-libp2p import succeeded but marked unavailable")
        
        self.identity = identity
        self.listen_addresses = listen_addresses or ["/ip4/0.0.0.0/tcp/8000"]
        self.bootstrap_peers = bootstrap_peers or []
        self.enable_mdns = enable_mdns
        self.enable_dht = enable_dht
        self.message_handler = message_handler
        self.on_peer_connect = on_peer_connect
        self.on_peer_disconnect = on_peer_disconnect
        
        # Libp2p host
        self.host: Optional[Host] = None
        self.peer_id: Optional[PeerID] = None
        
        # Active connections: peer_id -> stream
        self.peer_streams: Dict[str, INetStream] = {}

        # Discovery handles (optional)
        self._mdns_service = None
        self._dht = None
        
        # State
        self.state = Libp2pTransportState.DISCONNECTED
        self._running = False
        
        logger.debug("Libp2pTransport initialized")
    
    async def start(self) -> None:
        """Start Libp2p host and begin listening"""
        if self.state != Libp2pTransportState.DISCONNECTED:
            logger.warning("Transport already started")
            return
        
        self.state = Libp2pTransportState.STARTING
        logger.info("Starting Libp2p transport...")
        
        try:
            # Convert node identity to Libp2p key pair
            key_pair = convert_node_identity_to_key_pair(self.identity)
            if key_pair is None and LIBP2P_AVAILABLE:
                logger.warning("Failed to convert identity, Libp2p may not work correctly")
            
            # Create Libp2p host
            self.host = await create_libp2p_host(
                listen_addresses=self.listen_addresses,
                key_pair=key_pair,
            )
            
            if self.host is None:
                raise RuntimeError("Failed to create Libp2p host")
            
            # Get peer ID from host
            self.peer_id = await self._create_peer_id()
            logger.info(f"Libp2p host created with peer ID: {self.peer_id[:16]}...")
            
            # Set up stream handler
            await self._setup_stream_handler()
            
            # Start discovery
            if self.enable_mdns:
                await self._start_mdns_discovery()
            
            if self.enable_dht:
                await self._start_dht_discovery()
            
            # Connect to bootstrap peers
            if self.bootstrap_peers:
                await self._connect_bootstrap_peers()
            
            self.state = Libp2pTransportState.LISTENING
            self._running = True
            logger.info("Libp2p transport started")
        
        except Exception as e:
            logger.error(f"Failed to start Libp2p transport: {e}", exc_info=True)
            self.state = Libp2pTransportState.ERROR
            raise
    
    async def _create_peer_id(self) -> str:
        """Create Libp2p peer ID from node identity"""
        if not LIBP2P_AVAILABLE or self.host is None:
            # Fallback: use node ID as string
            return self.identity.get_node_id()
        
        try:
            # Get peer ID from host
            peer_id = self.host.get_id()
            peer_id_str = peer_id.to_string()
            logger.debug(f"Created Libp2p peer ID: {peer_id_str[:16]}...")
            return peer_id_str
        except Exception as e:
            logger.warning(f"Failed to get peer ID from host: {e}, using node ID")
            return self.identity.get_node_id()
    
    async def _setup_stream_handler(self) -> None:
        """Set up stream handler for incoming connections"""
        if not LIBP2P_AVAILABLE or self.host is None:
            logger.debug("Stream handler setup skipped (Libp2p not available)")
            return
        
        try:
            # Set up protocol handler for incoming streams
            # Protocol ID: /project-dawn/1.0.0
            protocol_id = "/project-dawn/1.0.0"
            
            # Register stream handler
            # py-libp2p API varies by version - try multiple patterns for compatibility
            async def handle_stream(stream: INetStream):
                """Handle incoming stream"""
                await self._handle_stream(stream)

            handler_registered = False
            
            # Try multiple API patterns for different py-libp2p versions
            # Pattern 1: Direct host method (newer versions)
            if hasattr(self.host, "set_stream_handler"):
                try:
                    self.host.set_stream_handler(protocol_id, handle_stream)
                    logger.debug("Stream handler registered on host (direct method)")
                    handler_registered = True
                except Exception as e:
                    logger.debug(f"Failed to register handler via host method: {e}")
            
            # Pattern 2: Network-level handler (older versions)
            if not handler_registered:
                network = self.host.get_network() if hasattr(self.host, "get_network") else None
                if network and hasattr(network, "set_stream_handler"):
                    try:
                        network.set_stream_handler(protocol_id, handle_stream)
                        logger.debug("Stream handler registered on network")
                        handler_registered = True
                    except Exception as e:
                        logger.debug(f"Failed to register handler via network method: {e}")
            
            # Pattern 3: Protocol handler (alternative API)
            if not handler_registered and hasattr(self.host, "set_protocol_handler"):
                try:
                    self.host.set_protocol_handler(protocol_id, handle_stream)
                    logger.debug("Stream handler registered via protocol handler")
                    handler_registered = True
                except Exception as e:
                    logger.debug(f"Failed to register handler via protocol method: {e}")
            
            if not handler_registered:
                logger.warning("Could not register stream handler - libp2p API may be incompatible")
        
        except Exception as e:
            logger.warning(f"Failed to set up stream handler: {e}")
    
    async def _start_mdns_discovery(self) -> None:
        """Start mDNS discovery"""
        if not LIBP2P_AVAILABLE or self.host is None:
            return
        try:
            from libp2p.discovery import mdns as libp2p_mdns  # type: ignore[reportMissingImports]
            service_cls = getattr(libp2p_mdns, "MDNSService", None) or getattr(libp2p_mdns, "MDNSDiscovery", None)
            if not service_cls:
                logger.warning("Libp2p mDNS discovery not available in this version")
                return
            self._mdns_service = service_cls(self.host, "project-dawn")
            if hasattr(self._mdns_service, "start"):
                await self._mdns_service.start()
            logger.info("mDNS discovery started (Libp2p)")
        except Exception as e:
            logger.warning(f"Failed to start mDNS discovery: {e}")
    
    async def _start_dht_discovery(self) -> None:
        """Start DHT discovery"""
        if not LIBP2P_AVAILABLE or self.host is None:
            return
        try:
            from libp2p.kademlia.dht import DHT  # type: ignore[reportMissingImports]
            self._dht = DHT(self.host)
            if hasattr(self._dht, "start"):
                await self._dht.start()
            logger.info("DHT discovery started (Libp2p)")
        except Exception as e:
            logger.warning(f"Failed to start DHT discovery: {e}")
    
    async def _connect_bootstrap_peers(self) -> None:
        """Connect to bootstrap peers"""
        if not LIBP2P_AVAILABLE or self.host is None:
            return
        
        for peer_addr in self.bootstrap_peers:
            try:
                success = await libp2p_connect(self.host, peer_addr)
                if success:
                    logger.info(f"Connected to bootstrap peer: {peer_addr}")
                else:
                    logger.warning(f"Failed to connect to bootstrap peer: {peer_addr}")
            except Exception as e:
                logger.warning(f"Error connecting to bootstrap peer {peer_addr}: {e}")
    
    async def connect_to_peer(self, peer_id: str, peer_address: Optional[str] = None) -> bool:
        """
        Connect to a specific peer
        
        Args:
            peer_id: Peer ID to connect to
            peer_address: Optional peer address (if not in DHT)
            
        Returns:
            True if connected successfully
        """
        if not LIBP2P_AVAILABLE or self.host is None:
            logger.error("Libp2p not available, cannot connect to peer")
            return False
        
        try:
            if peer_address:
                # Connect using provided address
                success = await libp2p_connect(self.host, peer_address, peer_id)
            else:
                # Try to find peer via DHT (if available)
                # For now, we need an address to connect
                logger.warning(f"No address provided for peer {peer_id[:16]}..., cannot connect")
                return False
            
            if success:
                logger.info(f"Connected to peer: {peer_id[:16]}...")
                
                # Open a stream for communication
                stream = await libp2p_open_stream(self.host, peer_id)
                if stream:
                    self.peer_streams[peer_id] = stream
                    asyncio.create_task(self._handle_stream(stream))
                
                if self.on_peer_connect:
                    await self.on_peer_connect(peer_id)
            
            return success
        
        except Exception as e:
            logger.error(f"Failed to connect to peer {peer_id}: {e}")
            return False
    
    async def send_to_peer(self, peer_id: str, message: str) -> bool:
        """
        Send message to peer
        
        Args:
            peer_id: Peer ID to send to
            message: JSON-RPC message as string
            
        Returns:
            True if sent successfully
        """
        if not LIBP2P_AVAILABLE:
            logger.error("Libp2p not available, cannot send message")
            return False
        
        if peer_id not in self.peer_streams:
            # Try to open a stream
            if self.host:
                stream = await libp2p_open_stream(self.host, peer_id)
                if stream:
                    self.peer_streams[peer_id] = stream
                    asyncio.create_task(self._handle_stream(stream))
                else:
                    logger.warning(f"Failed to open stream to {peer_id[:16]}...")
                    return False
            else:
                logger.error("Host not available, cannot send message")
                return False
        
        try:
            stream = self.peer_streams[peer_id]
            message_bytes = message.encode('utf-8')
            success = await write_stream_message(stream, message_bytes)
            
            if success:
                logger.debug(f"Sent message to peer {peer_id[:16]}... ({len(message_bytes)} bytes)")
            
            return success
        
        except Exception as e:
            logger.error(f"Failed to send message to peer {peer_id}: {e}")
            return False
    
    async def broadcast(self, message: str, exclude_peers: Optional[List[str]] = None) -> int:
        """
        Broadcast message to all connected peers
        
        Args:
            message: Message to broadcast
            exclude_peers: List of peer IDs to exclude
            
        Returns:
            Number of peers message was sent to
        """
        exclude_peers = exclude_peers or []
        sent_count = 0
        
        for peer_id in self.peer_streams.keys():
            if peer_id not in exclude_peers:
                if await self.send_to_peer(peer_id, message):
                    sent_count += 1
        
        return sent_count
    
    async def _handle_stream(self, stream: INetStream) -> None:
        """Handle incoming stream"""
        if stream is None:
            return
        
        try:
            # Get peer ID from stream
            # API varies by py-libp2p version - try multiple patterns for compatibility
            peer_id = None
            
            # Pattern 1: Direct muxed_conn access (common pattern)
            try:
                if hasattr(stream, 'muxed_conn') and stream.muxed_conn:
                    peer_id_obj = stream.muxed_conn.peer_id
                    peer_id = peer_id_obj.to_string() if hasattr(peer_id_obj, 'to_string') else str(peer_id_obj)
            except (AttributeError, TypeError):
                pass
            
            # Pattern 2: Direct peer_id attribute
            if not peer_id and hasattr(stream, 'peer_id'):
                try:
                    peer_id_obj = stream.peer_id
                    peer_id = peer_id_obj.to_string() if hasattr(peer_id_obj, 'to_string') else str(peer_id_obj)
                except (AttributeError, TypeError):
                    pass
            
            # Pattern 3: Connection peer_id
            if not peer_id and hasattr(stream, 'conn') and stream.conn:
                try:
                    if hasattr(stream.conn, 'peer_id'):
                        peer_id_obj = stream.conn.peer_id
                        peer_id = peer_id_obj.to_string() if hasattr(peer_id_obj, 'to_string') else str(peer_id_obj)
                except (AttributeError, TypeError):
                    pass
            
            # Fallback: use connection info if available
            if not peer_id:
                peer_id = f"peer_{id(stream)}"
            
            self.peer_streams[peer_id] = stream
            logger.info(f"New stream from peer: {peer_id[:16]}...")
            
            if self.on_peer_connect:
                await self.on_peer_connect(peer_id)
            
            # Read messages from stream
            while self._running:
                try:
                    # Read message with timeout
                    data = await read_stream_message(stream, timeout=1.0)
                    
                    if data is None:
                        # Timeout or end of stream
                        await asyncio.sleep(0.1)
                        continue
                    
                    # Decode message
                    try:
                        message = data.decode('utf-8')
                    except UnicodeDecodeError:
                        logger.warning(f"Failed to decode message from {peer_id[:16]}...")
                        continue
                    
                    # Handle message
                    if self.message_handler:
                        response = await self.message_handler(peer_id, message)
                        if response:
                            response_bytes = response.encode('utf-8')
                            await write_stream_message(stream, response_bytes)
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error reading from stream {peer_id[:16]}...: {e}")
                    break
        
        except Exception as e:
            logger.error(f"Error handling stream: {e}", exc_info=True)
        finally:
            if peer_id in self.peer_streams:
                del self.peer_streams[peer_id]
            
            if self.on_peer_disconnect:
                await self.on_peer_disconnect(peer_id)
    
    async def stop(self) -> None:
        """Stop Libp2p transport"""
        if self.state == Libp2pTransportState.DISCONNECTED:
            return
        
        logger.info("Stopping Libp2p transport...")
        self._running = False
        
        # Close all streams
        for peer_id, stream in list(self.peer_streams.items()):
            try:
                if stream and hasattr(stream, 'close'):
                    await stream.close()
                if self.on_peer_disconnect:
                    await self.on_peer_disconnect(peer_id)
            except Exception as e:
                logger.debug(f"Error closing stream for {peer_id[:16]}...: {e}")
        
        self.peer_streams.clear()
        
        # Stop host
        if self.host and hasattr(self.host, 'close'):
            try:
                await self.host.close()
            except Exception as e:
                logger.warning(f"Error closing host: {e}")
        
        self.host = None
        self.state = Libp2pTransportState.DISCONNECTED
        logger.info("Libp2p transport stopped")
    
    def get_peer_id(self) -> Optional[str]:
        """Get this node's peer ID"""
        if self.peer_id:
            return str(self.peer_id)
        elif self.host and LIBP2P_AVAILABLE:
            try:
                peer_id_obj = self.host.get_id()
                return peer_id_obj.to_string() if hasattr(peer_id_obj, 'to_string') else str(peer_id_obj)
            except Exception:
                pass
        return None
    
    def get_listen_addresses(self) -> List[str]:
        """Get addresses this node is listening on"""
        return self.listen_addresses.copy()
    
    def get_connected_peers(self) -> List[str]:
        """Get list of connected peer IDs"""
        return list(self.peer_streams.keys())


class Libp2pTransportAdapter:
    """
    Adapter to use Libp2p transport with existing MCP code
    
    Provides compatibility layer between Libp2p and existing WebSocket-based code.
    """
    
    def __init__(self, libp2p_transport: Libp2pTransport):
        """
        Initialize adapter
        
        Args:
            libp2p_transport: Libp2p transport instance
        """
        self.transport = libp2p_transport
        self._message_queue: Dict[str, asyncio.Queue] = {}  # peer_id -> message queue
    
    async def connect(self, peer_id: str) -> bool:
        """Connect to peer (adapter method)"""
        return await self.transport.connect_to_peer(peer_id)
    
    async def send(self, peer_id: str, message: str) -> bool:
        """Send message (adapter method)"""
        return await self.transport.send_to_peer(peer_id, message)
    
    async def receive(self, peer_id: str, timeout: float = 30.0) -> Optional[str]:
        """Receive message from peer (adapter method)"""
        if peer_id not in self._message_queue:
            self._message_queue[peer_id] = asyncio.Queue()
        
        try:
            return await asyncio.wait_for(self._message_queue[peer_id].get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
    
    def get_peer_id(self) -> Optional[str]:
        """Get this node's peer ID"""
        return self.transport.get_peer_id()
