"""
Peer Discovery System

Implements various peer discovery mechanisms:
- Bootstrap nodes (initial peer list)
- mDNS/Bonjour (local network discovery)
- Gossip protocol (peer announcements)
"""

import asyncio
import logging
import time
import json
from typing import List, Dict, Any, Optional, Callable, Set
from .peer import Peer
from .peer_registry import PeerRegistry
from .dht import DHT
from crypto import NodeIdentity

logger = logging.getLogger(__name__)

# Try to import zeroconf for mDNS
try:
    from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser, ServiceListener
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    logger.debug("zeroconf not available, mDNS discovery disabled")


class BootstrapDiscovery:
    """
    Bootstrap peer discovery
    
    Connects to a list of known bootstrap nodes to discover the network.
    """
    
    def __init__(self, bootstrap_nodes: List[str], peer_registry: PeerRegistry):
        """
        Initialize bootstrap discovery
        
        Args:
            bootstrap_nodes: List of bootstrap node addresses (e.g., ["ws://node1:8000", "ws://node2:8000"])
            peer_registry: Peer registry to update
        """
        self.bootstrap_nodes = bootstrap_nodes
        self.peer_registry = peer_registry
        logger.debug(f"BootstrapDiscovery initialized with {len(bootstrap_nodes)} nodes")
    
    async def discover(self) -> List[Peer]:
        """
        Discover peers via bootstrap nodes
        
        Returns:
            List of discovered peers
        """
        discovered_peers = []
        
        for bootstrap_address in self.bootstrap_nodes:
            try:
                # Try to connect and get peer list
                # In a real implementation, this would:
                # 1. Connect to bootstrap node
                # 2. Request peer list
                # 3. Add peers to registry
                
                # For now, create a peer entry for the bootstrap node itself
                # In production, bootstrap node would return list of peers
                peer = Peer(
                    node_id=f"bootstrap_{hash(bootstrap_address)}",
                    address=bootstrap_address,
                )
                self.peer_registry.add_peer(peer)
                discovered_peers.append(peer)
                
                logger.debug(f"Discovered bootstrap peer: {bootstrap_address}")
            
            except Exception as e:
                logger.warning(f"Failed to discover from bootstrap {bootstrap_address}: {e}")
        
        return discovered_peers


class MDNSDiscovery:
    """
    mDNS/Bonjour peer discovery
    
    Discovers peers on the local network using mDNS.
    """
    
    SERVICE_TYPE = "_projectdawn._tcp.local."
    
    def __init__(self, peer_registry: PeerRegistry, service_name: Optional[str] = None):
        """
        Initialize mDNS discovery
        
        Args:
            peer_registry: Peer registry to update
            service_name: Service name for this node (optional)
        """
        if not ZEROCONF_AVAILABLE:
            raise RuntimeError("zeroconf library not available for mDNS discovery")
        
        self.peer_registry = peer_registry
        self.service_name = service_name or "project-dawn-node"
        self.zeroconf: Optional[Zeroconf] = None
        self.browser: Optional[ServiceBrowser] = None
        self.listener: Optional[ServiceListener] = None
        
        logger.debug("MDNSDiscovery initialized")
    
    def start(self) -> None:
        """Start mDNS discovery"""
        if not ZEROCONF_AVAILABLE:
            logger.warning("mDNS discovery not available (zeroconf not installed)")
            return
        
        try:
            self.zeroconf = Zeroconf()
            
            class DiscoveryListener(ServiceListener):
                def __init__(self, registry: PeerRegistry):
                    self.registry = registry
                
                def add_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
                    info = zeroconf.get_service_info(service_type, name)
                    if info:
                        # Extract peer information from mDNS service
                        address = f"ws://{info.parsed_addresses()[0]}:{info.port}"
                        node_id = info.properties.get(b"node_id", b"unknown").decode('utf-8')
                        
                        peer = Peer(
                            node_id=node_id,
                            address=address,
                        )
                        self.registry.add_peer(peer)
                        logger.info(f"Discovered peer via mDNS: {node_id[:16]}... ({address})")
                
                def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
                    logger.debug(f"Service removed: {name}")
                
                def update_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
                    logger.debug(f"Service updated: {name}")
            
            self.listener = DiscoveryListener(self.peer_registry)
            self.browser = ServiceBrowser(self.zeroconf, self.SERVICE_TYPE, self.listener)
            
            logger.info("mDNS discovery started")
        
        except Exception as e:
            logger.error(f"Failed to start mDNS discovery: {e}", exc_info=True)
    
    def stop(self) -> None:
        """Stop mDNS discovery"""
        if self.browser:
            self.browser.cancel()
        if self.zeroconf:
            self.zeroconf.close()
        logger.info("mDNS discovery stopped")
    
    def register_service(self, node_id: str, address: str, port: int = 8000) -> None:
        """
        Register this node's service with mDNS
        
        Args:
            node_id: This node's ID
            address: This node's address
            port: This node's port
        """
        if not ZEROCONF_AVAILABLE or not self.zeroconf:
            return
        
        try:
            # Parse address
            host = address.replace("ws://", "").replace("wss://", "").split(":")[0]
            
            info = ServiceInfo(
                self.SERVICE_TYPE,
                f"{self.service_name}.{self.SERVICE_TYPE}",
                addresses=[host],
                port=port,
                properties={
                    b"node_id": node_id.encode('utf-8'),
                    b"address": address.encode('utf-8'),
                },
            )
            
            self.zeroconf.register_service(info)
            logger.info(f"Registered mDNS service: {node_id[:16]}...")
        
        except Exception as e:
            logger.error(f"Failed to register mDNS service: {e}", exc_info=True)


class GossipDiscovery:
    """
    Gossip protocol for peer discovery
    
    Peers periodically announce themselves and share peer lists.
    """
    
    def __init__(
        self,
        peer_registry: PeerRegistry,
        announce_interval: float = 60.0,
        max_peers_to_share: int = 10,
    ):
        """
        Initialize gossip discovery
        
        Args:
            peer_registry: Peer registry to update
            announce_interval: Seconds between announcements (default 60s)
            max_peers_to_share: Maximum number of peers to share per announcement
        """
        self.peer_registry = peer_registry
        self.announce_interval = announce_interval
        self.max_peers_to_share = max_peers_to_share
        self.running = False
        self._announce_task: Optional[asyncio.Task] = None
        
        logger.debug("GossipDiscovery initialized")
    
    def start(self, announce_callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """
        Start gossip discovery
        
        Args:
            announce_callback: Callback to send announcements to peers
        """
        if self.running:
            logger.warning("Gossip discovery already running")
            return
        
        self.running = True
        self._announce_task = asyncio.create_task(self._announce_loop(announce_callback))
        logger.info("Gossip discovery started")
    
    def stop(self) -> None:
        """Stop gossip discovery"""
        self.running = False
        if self._announce_task:
            self._announce_task.cancel()
        logger.info("Gossip discovery stopped")
    
    async def _announce_loop(self, announce_callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Periodically announce this node and share peer list"""
        while self.running:
            try:
                # Create announcement
                announcement = self._create_announcement()
                
                # Send announcement
                await announce_callback(announcement)
                
                # Wait for next interval
                await asyncio.sleep(self.announce_interval)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in gossip announcement: {e}", exc_info=True)
                await asyncio.sleep(self.announce_interval)
    
    def _create_announcement(self) -> Dict[str, Any]:
        """Create gossip announcement"""
        # Get some peers to share (not all, to avoid flooding)
        peers_to_share = self.peer_registry.list_alive_peers()[:self.max_peers_to_share]
        
        return {
            "type": "gossip_announcement",
            "timestamp": time.time(),
            "peers": [peer.to_dict() for peer in peers_to_share],
        }
    
    def handle_announcement(self, announcement: Dict[str, Any], sender_node_id: str) -> None:
        """
        Handle received gossip announcement
        
        Args:
            announcement: Announcement message
            sender_node_id: Node ID of sender
        """
        try:
            if announcement.get("type") != "gossip_announcement":
                return
            
            peers_data = announcement.get("peers", [])
            
            for peer_data in peers_data:
                # Don't add ourselves
                if peer_data["node_id"] == sender_node_id:
                    continue
                
                # Create or update peer
                peer = Peer.from_dict(peer_data)
                self.peer_registry.add_peer(peer)
            
            logger.debug(f"Processed gossip announcement from {sender_node_id[:16]}... ({len(peers_data)} peers)")
        
        except Exception as e:
            logger.error(f"Error handling gossip announcement: {e}", exc_info=True)


class DHTDiscovery:
    """
    DHT-based peer discovery
    
    Uses Distributed Hash Table for efficient peer discovery in large networks.
    """
    
    def __init__(
        self,
        dht: DHT,
        peer_registry: PeerRegistry,
        identity: NodeIdentity,
    ):
        """
        Initialize DHT discovery
        
        Args:
            dht: DHT instance
            peer_registry: Peer registry to update
            identity: Node identity
        """
        self.dht = dht
        self.peer_registry = peer_registry
        self.identity = identity
        self.running = False
        self._discover_task: Optional[asyncio.Task] = None
        
        logger.debug("DHTDiscovery initialized")
    
    def start(self, rpc_handler: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> None:
        """
        Start DHT discovery
        
        Args:
            rpc_handler: Handler for DHT RPC calls
        """
        if self.running:
            logger.warning("DHT discovery already running")
            return
        
        self.dht.rpc_handler = rpc_handler
        self.running = True
        self._discover_task = asyncio.create_task(self._discover_loop())
        logger.info("DHT discovery started")
    
    def stop(self) -> None:
        """Stop DHT discovery"""
        self.running = False
        if self._discover_task:
            self._discover_task.cancel()
        logger.info("DHT discovery stopped")
    
    async def _discover_loop(self) -> None:
        """Periodically discover peers via DHT"""
        while self.running:
            try:
                # Find random nodes to discover network
                # Use our own node ID as a starting point, then explore
                await self.discover_peers()
                
                # Wait before next discovery round
                await asyncio.sleep(300)  # Every 5 minutes
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in DHT discovery: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def discover_peers(self, target_id: Optional[str] = None) -> List[Peer]:
        """
        Discover peers via DHT
        
        Args:
            target_id: Optional target node ID to find. If None, finds random nodes.
            
        Returns:
            List of discovered peers
        """
        if not target_id:
            # Find nodes close to random IDs to explore network
            import random
            random_id = ''.join(random.choices('0123456789abcdef', k=64))
            target_id = random_id
        
        try:
            nodes = await self.dht.find_node(target_id)
            discovered = []
            
            for dht_node in nodes:
                # Add to peer registry
                peer = Peer(
                    node_id=dht_node.node_id,
                    address=dht_node.address,
                )
                self.peer_registry.add_peer(peer)
                discovered.append(peer)
                
                # Also add to DHT (if not already there)
                self.dht.add_node(dht_node.node_id, dht_node.address)
            
            logger.info(f"Discovered {len(discovered)} peers via DHT")
            return discovered
        
        except Exception as e:
            logger.error(f"Error discovering peers via DHT: {e}", exc_info=True)
            return []
    
    async def discover_agent(self, agent_key: str) -> Optional[Dict[str, Any]]:
        """
        Discover an agent via DHT
        
        Args:
            agent_key: Agent key (e.g., "node_id:agent_id")
            
        Returns:
            Agent information if found
        """
        try:
            value = await self.dht.find_value(f"agent:{agent_key}")
            if value:
                logger.info(f"Found agent via DHT: {agent_key}")
                return value
        except Exception as e:
            logger.error(f"Error discovering agent via DHT: {e}", exc_info=True)
        
        return None
    
    async def announce_agent(self, agent_key: str, agent_info: Dict[str, Any], ttl: float = 3600.0) -> bool:
        """
        Announce an agent in the DHT
        
        Args:
            agent_key: Agent key (e.g., "node_id:agent_id")
            agent_info: Agent information
            ttl: Time to live in seconds
            
        Returns:
            True if announced successfully
        """
        try:
            success = await self.dht.store(f"agent:{agent_key}", agent_info, ttl)
            if success:
                logger.info(f"Announced agent in DHT: {agent_key}")
            return success
        except Exception as e:
            logger.error(f"Error announcing agent in DHT: {e}", exc_info=True)
            return False


class PeerDiscovery:
    """
    Unified peer discovery system
    
    Combines multiple discovery mechanisms.
    """
    
    def __init__(
        self,
        peer_registry: PeerRegistry,
        bootstrap_nodes: Optional[List[str]] = None,
        enable_mdns: bool = True,
        enable_gossip: bool = True,
        enable_dht: bool = False,
        identity: Optional[NodeIdentity] = None,
    ):
        """
        Initialize peer discovery
        
        Args:
            peer_registry: Peer registry to update
            bootstrap_nodes: List of bootstrap node addresses
            enable_mdns: Enable mDNS discovery
            enable_gossip: Enable gossip discovery
            enable_dht: Enable DHT discovery (for large networks)
            identity: Node identity (required for DHT)
        """
        self.peer_registry = peer_registry
        
        # Initialize discovery mechanisms
        self.bootstrap = BootstrapDiscovery(bootstrap_nodes or [], peer_registry) if bootstrap_nodes else None
        self.mdns: Optional[MDNSDiscovery] = None
        self.gossip: Optional[GossipDiscovery] = None
        self.dht: Optional[DHT] = None
        self.dht_discovery: Optional[DHTDiscovery] = None
        
        if enable_mdns and ZEROCONF_AVAILABLE:
            try:
                self.mdns = MDNSDiscovery(peer_registry)
            except Exception as e:
                logger.warning(f"Failed to initialize mDNS discovery: {e}")
        
        if enable_gossip:
            self.gossip = GossipDiscovery(peer_registry)
        
        if enable_dht:
            if not identity:
                logger.warning("DHT requires node identity, disabling DHT")
            else:
                try:
                    self.dht = DHT(identity)
                    self.dht_discovery = DHTDiscovery(self.dht, peer_registry, identity)
                    logger.info("DHT discovery initialized")
                except Exception as e:
                    logger.warning(f"Failed to initialize DHT discovery: {e}")
        
        logger.info("PeerDiscovery initialized")
    
    async def discover_bootstrap(self) -> List[Peer]:
        """Discover peers via bootstrap nodes"""
        if self.bootstrap:
            return await self.bootstrap.discover()
        return []
    
    def start_mdns(self) -> None:
        """Start mDNS discovery"""
        if self.mdns:
            self.mdns.start()
    
    def stop_mdns(self) -> None:
        """Stop mDNS discovery"""
        if self.mdns:
            self.mdns.stop()
    
    def start_gossip(self, announce_callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Start gossip discovery"""
        if self.gossip:
            self.gossip.start(announce_callback)
    
    def stop_gossip(self) -> None:
        """Stop gossip discovery"""
        if self.gossip:
            self.gossip.stop()
    
    def handle_gossip_announcement(self, announcement: Dict[str, Any], sender_node_id: str) -> None:
        """Handle gossip announcement"""
        if self.gossip:
            self.gossip.handle_announcement(announcement, sender_node_id)
    
    def register_mdns_service(self, node_id: str, address: str, port: int = 8000) -> None:
        """Register this node with mDNS"""
        if self.mdns:
            self.mdns.register_service(node_id, address, port)
    
    def start_dht(self, rpc_handler: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> None:
        """Start DHT discovery"""
        if self.dht_discovery:
            self.dht_discovery.start(rpc_handler)
    
    def stop_dht(self) -> None:
        """Stop DHT discovery"""
        if self.dht_discovery:
            self.dht_discovery.stop()
    
    async def discover_peers_dht(self, target_id: Optional[str] = None) -> List[Peer]:
        """Discover peers via DHT"""
        if self.dht_discovery:
            return await self.dht_discovery.discover_peers(target_id)
        return []
    
    async def discover_agent_dht(self, agent_key: str) -> Optional[Dict[str, Any]]:
        """Discover an agent via DHT"""
        if self.dht_discovery:
            return await self.dht_discovery.discover_agent(agent_key)
        return None
    
    async def announce_agent_dht(self, agent_key: str, agent_info: Dict[str, Any], ttl: float = 3600.0) -> bool:
        """Announce an agent in the DHT"""
        if self.dht_discovery:
            return await self.dht_discovery.announce_agent(agent_key, agent_info, ttl)
        return False
    
    def get_dht(self) -> Optional[DHT]:
        """Get DHT instance"""
        return self.dht

