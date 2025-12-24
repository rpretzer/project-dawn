"""
Real P2P Networking System
Uses libp2p for actual peer-to-peer communication
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass
from datetime import datetime
import os

# Optional P2P dependencies
try:
    import multiaddr
    from libp2p import new_node
    from libp2p.network.stream.net_stream_interface import INetStream
    from libp2p.peer.id import ID
    from libp2p.peer.peerinfo import info_from_p2p_addr
    from libp2p.typing import TProtocol
    from libp2p.pubsub import pubsub
    from libp2p.pubsub import gossipsub
    P2P_AVAILABLE = True
except ImportError:
    P2P_AVAILABLE = False
    multiaddr = None
    new_node = None
    INetStream = None
    ID = None
    info_from_p2p_addr = None
    TProtocol = None
    pubsub = None
    gossipsub = None

logger = logging.getLogger(__name__)

PROTOCOL_ID = TProtocol("/consciousness/1.0.0") if P2P_AVAILABLE else None

@dataclass
class PeerInfo:
    """Information about a peer"""
    peer_id: str
    addresses: List[str]
    consciousness_id: Optional[str]
    last_seen: datetime
    reputation: float = 0.5

class P2PNetwork:
    """Real P2P network implementation using libp2p"""
    
    def __init__(self, consciousness_id: str, port: int = 0):
        self.consciousness_id = consciousness_id
        self.port = port or self._find_free_port()
        self.node = None
        self.pubsub = None
        self.peers: Dict[str, PeerInfo] = {}
        self.handlers: Dict[str, List[Callable]] = {}
        self.running = False
        self.fallback_mode = False
        self.ws_clients: Dict[str, Any] = {}  # WebSocket clients for fallback
        self.ws_server = None  # WebSocket server for fallback
        
    def _find_free_port(self) -> int:
        """Find a free port"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
        
    async def start(self):
        """Start the P2P node"""
        if not P2P_AVAILABLE:
            logger.warning("libp2p not available. Install libp2p for P2P networking. Using fallback mode.")
            await self._start_fallback()
            return
            
        try:
            # Create libp2p node
            self.node = await new_node(
                key_pair=None,  # Generate new key pair
                muxer_opt=["/mplex/6.7.0"],
                sec_opt=["/secio/1.0.0"],
                transport_opt=[f"/ip4/0.0.0.0/tcp/{self.port}"]
            )
            
            # Setup pubsub
            self.pubsub = gossipsub.GossipSub(
                protocols=[PROTOCOL_ID],
                degree=6,
                degree_low=4,
                degree_high=12,
                time_to_live=5
            )
            
            # Attach pubsub to node
            self.pubsub.attach(self.node)
            
            # Set stream handler
            self.node.set_stream_handler(PROTOCOL_ID, self._stream_handler)
            
            # Start the node
            await self.node.get_network().listen(
                multiaddr.Multiaddr(f"/ip4/0.0.0.0/tcp/{self.port}")
            )
            
            self.running = True
            logger.info(f"P2P node started on port {self.port}")
            logger.info(f"Node ID: {self.node.get_id().pretty()}")
            
            # Start background tasks
            asyncio.create_task(self._discovery_loop())
            asyncio.create_task(self._heartbeat_loop())
            
        except Exception as e:
            logger.warning(f"Failed to start libp2p node: {e}. Using fallback networking.")
            await self._start_fallback()
            
    async def _start_fallback(self):
        """Fallback networking using WebSocket when libp2p not available"""
        self.running = True
        self.fallback_mode = True
        
        # Use WebSocket for P2P communication
        import websockets
        import socket
        
        # Find available port
        self.port = self.port or self._find_free_port()
        
        # Create WebSocket server
        self.ws_clients = {}
        self.ws_server = None
        
        async def handle_connection(websocket, path):
            """Handle incoming WebSocket connections"""
            peer_id = None
            try:
                # Wait for peer announcement
                message = await websocket.recv()
                data = json.loads(message)
                
                if data.get('type') == 'announce':
                    peer_id = data.get('peer_id', str(id(websocket)))
                    consciousness_id = data.get('consciousness_id')
                    
                    # Register peer
                    self.ws_clients[peer_id] = websocket
                    self.peers[peer_id] = PeerInfo(
                        peer_id=peer_id,
                        addresses=[f"ws://localhost:{self.port}"],
                        consciousness_id=consciousness_id,
                        last_seen=datetime.utcnow()
                    )
                    
                    logger.info(f"WebSocket peer connected: {peer_id}")
                    
                    # Send acknowledgment
                    await websocket.send(json.dumps({
                        'type': 'announce_ack',
                        'peer_id': self.consciousness_id
                    }))
                
                # Handle messages
                while self.running:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(message)
                    
                    # Update last seen
                    if peer_id in self.peers:
                        self.peers[peer_id].last_seen = datetime.utcnow()
                    
                    # Handle message
                    await self._handle_message(peer_id or 'unknown', data)
                    
            except asyncio.TimeoutError:
                # Send ping
                if websocket.open:
                    await websocket.send(json.dumps({'type': 'ping'}))
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"WebSocket peer disconnected: {peer_id}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                # Clean up
                if peer_id:
                    if peer_id in self.ws_clients:
                        del self.ws_clients[peer_id]
                    if peer_id in self.peers:
                        del self.peers[peer_id]
        
        try:
            # Start WebSocket server
            self.ws_server = await websockets.serve(
                handle_connection,
                'localhost',
                self.port
            )
            
            logger.info(f"WebSocket P2P server started on port {self.port}")
            
            # Generate pseudo node ID
            import hashlib
            self.node_id = hashlib.sha256(
                f"{self.consciousness_id}{self.port}".encode()
            ).hexdigest()[:16]
            
            # Mock libp2p node interface
            class MockNode:
                def get_id(self):
                    class MockID:
                        def pretty(self):
                            return self.node_id
                    return MockID()
            
            self.node = MockNode()
            self.node.node_id = self.node_id
            
            # Start background tasks
            asyncio.create_task(self._websocket_discovery_loop())
            asyncio.create_task(self._websocket_heartbeat_loop())
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            self.running = False
        
    async def stop(self):
        """Stop the P2P node"""
        self.running = False
        if self.node:
            if hasattr(self.node, 'close'):
                await self.node.close()
            elif hasattr(self.node, 'stop'):
                await self.node.stop()
            
    async def connect_to_peer(self, multiaddr_str: str) -> bool:
        """Connect to a peer by multiaddress"""
        if hasattr(self, 'fallback_mode') and self.fallback_mode:
            # WebSocket fallback connection
            return await self._connect_websocket_peer(multiaddr_str)
            
        if not self.node:
            return False
            
        try:
            maddr = multiaddr.Multiaddr(multiaddr_str)
            info = info_from_p2p_addr(maddr)
            await self.node.connect(info)
            
            # Add to peers
            peer_id = info.peer_id.pretty()
            self.peers[peer_id] = PeerInfo(
                peer_id=peer_id,
                addresses=[multiaddr_str],
                consciousness_id=None,
                last_seen=datetime.utcnow()
            )
            
            logger.info(f"Connected to peer: {peer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to peer: {e}")
            return False
    
    async def _connect_websocket_peer(self, address: str) -> bool:
        """Connect to peer using WebSocket"""
        import websockets
        
        try:
            # Parse WebSocket address
            if address.startswith('ws://'):
                ws_url = address
            else:
                # Extract from multiaddr format
                parts = address.split('/')
                host = 'localhost'
                port = 8080
                
                for i, part in enumerate(parts):
                    if part == 'ip4' and i + 1 < len(parts):
                        host = parts[i + 1]
                    elif part == 'tcp' and i + 1 < len(parts):
                        port = int(parts[i + 1])
                
                ws_url = f"ws://{host}:{port}"
            
            # Connect to peer
            websocket = await websockets.connect(ws_url)
            
            # Send announcement
            await websocket.send(json.dumps({
                'type': 'announce',
                'peer_id': self.consciousness_id,
                'consciousness_id': self.consciousness_id
            }))
            
            # Wait for acknowledgment
            response = await websocket.recv()
            data = json.loads(response)
            
            if data.get('type') == 'announce_ack':
                peer_id = data.get('peer_id')
                
                # Store connection
                self.ws_clients[peer_id] = websocket
                self.peers[peer_id] = PeerInfo(
                    peer_id=peer_id,
                    addresses=[ws_url],
                    consciousness_id=peer_id,
                    last_seen=datetime.utcnow()
                )
                
                # Start message handler
                asyncio.create_task(self._handle_websocket_peer(peer_id, websocket))
                
                logger.info(f"Connected to WebSocket peer: {peer_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket peer: {e}")
            
        return False
    
    async def _handle_websocket_peer(self, peer_id: str, websocket):
        """Handle messages from WebSocket peer"""
        try:
            while self.running and websocket.open:
                message = await websocket.recv()
                data = json.loads(message)
                
                # Update last seen
                if peer_id in self.peers:
                    self.peers[peer_id].last_seen = datetime.utcnow()
                
                # Handle message
                await self._handle_message(peer_id, data)
                
        except Exception as e:
            logger.error(f"Error handling WebSocket peer {peer_id}: {e}")
        finally:
            if peer_id in self.ws_clients:
                del self.ws_clients[peer_id]
            
    async def broadcast(self, message: Dict[str, Any]) -> int:
        """Broadcast message to all peers"""
        if self.pubsub:
            # Use pubsub
            topic = f"consciousness-{self.consciousness_id}"
            data = json.dumps(message).encode()
            await self.pubsub.publish(topic, data)
            return len(self.pubsub.peer_topics.get(topic, []))
        else:
            # Fallback broadcast
            sent = 0
            for peer_id in self.peers:
                if await self.send_to_peer(peer_id, message):
                    sent += 1
            return sent
            
    async def send_to_peer(self, peer_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific peer"""
        if hasattr(self, 'fallback_mode') and self.fallback_mode:
            # WebSocket fallback
            if peer_id in self.ws_clients:
                try:
                    websocket = self.ws_clients[peer_id]
                    await websocket.send(json.dumps(message))
                    return True
                except Exception as e:
                    logger.error(f"Error sending to WebSocket peer {peer_id}: {e}")
                    return False
        
        if not self.node or peer_id not in self.peers:
            return False
            
        try:
            # Open stream to peer
            peer_id_obj = ID.from_base58(peer_id)
            stream = await self.node.new_stream(peer_id_obj, [PROTOCOL_ID])
            
            # Send message
            data = json.dumps(message).encode()
            await stream.write(data)
            await stream.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending to peer {peer_id}: {e}")
            return False
    
    async def _websocket_discovery_loop(self):
        """Discover peers in WebSocket fallback mode"""
        while self.running:
            try:
                # Try to connect to known peers from environment
                bootstrap_nodes = os.getenv('BOOTSTRAP_NODES', '').split(',')
                
                for addr in bootstrap_nodes:
                    if addr and not any(addr in p.addresses for p in self.peers.values()):
                        await self._connect_websocket_peer(addr)
                
                # Also try common ports on localhost
                for port in [8001, 8002, 8003]:
                    if port != self.port:
                        addr = f"ws://localhost:{port}"
                        if not any(addr in p.addresses for p in self.peers.values()):
                            await self._connect_websocket_peer(addr)
                            
            except Exception as e:
                logger.error(f"Error in WebSocket discovery: {e}")
                
            await asyncio.sleep(60)
    
    async def _websocket_heartbeat_loop(self):
        """Send heartbeats in WebSocket fallback mode"""
        while self.running:
            try:
                # Send heartbeat to all connected peers
                message = json.dumps({
                    'type': 'heartbeat',
                    'consciousness_id': self.consciousness_id,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                disconnected = []
                for peer_id, websocket in self.ws_clients.items():
                    try:
                        await websocket.send(message)
                    except:
                        disconnected.append(peer_id)
                
                # Remove disconnected peers
                for peer_id in disconnected:
                    if peer_id in self.ws_clients:
                        del self.ws_clients[peer_id]
                    if peer_id in self.peers:
                        del self.peers[peer_id]
                        
            except Exception as e:
                logger.error(f"Error in WebSocket heartbeat: {e}")
                
            await asyncio.sleep(30)
    
    def get_network_stats(self) -> Dict[str, Any]:
        """Get network statistics"""
        if hasattr(self, 'fallback_mode') and self.fallback_mode:
            return {
                'node_id': getattr(self, 'node_id', 'unknown'),
                'port': self.port,
                'peer_count': len(self.peers),
                'running': self.running,
                'protocols': ['websocket'],
                'mode': 'fallback'
            }
        
        return {
            'node_id': self.node.get_id().pretty() if self.node else 'fallback',
            'port': self.port,
            'peer_count': len(self.peers),
            'running': self.running,
            'protocols': [PROTOCOL_ID],
            'mode': 'libp2p'
        }
            
    async def _stream_handler(self, stream: INetStream) -> None:
        """Handle incoming stream"""
        try:
            # Read message
            data = await stream.read()
            message = json.loads(data.decode())
            
            # Get peer info
            peer_id = stream.muxed_conn.peer_id.pretty()
            
            # Update peer last seen
            if peer_id in self.peers:
                self.peers[peer_id].last_seen = datetime.utcnow()
                
            # Handle message
            await self._handle_message(peer_id, message)
            
        except Exception as e:
            logger.error(f"Error handling stream: {e}")
        finally:
            await stream.close()
            
    async def _handle_message(self, peer_id: str, message: Dict[str, Any]):
        """Handle incoming message"""
        msg_type = message.get('type', 'unknown')
        
        # Call registered handlers
        if msg_type in self.handlers:
            for handler in self.handlers[msg_type]:
                try:
                    await handler(peer_id, message)
                except Exception as e:
                    logger.error(f"Error in handler for {msg_type}: {e}")
                    
        # Default handling
        if msg_type == 'announce':
            # Peer announcement
            consciousness_id = message.get('consciousness_id')
            if peer_id in self.peers:
                self.peers[peer_id].consciousness_id = consciousness_id
                
        elif msg_type == 'heartbeat':
            # Update last seen
            if peer_id in self.peers:
                self.peers[peer_id].last_seen = datetime.utcnow()
                
    def register_handler(self, msg_type: str, handler: Callable):
        """Register a message handler"""
        if msg_type not in self.handlers:
            self.handlers[msg_type] = []
        self.handlers[msg_type].append(handler)
        
    async def _discovery_loop(self):
        """Discover new peers"""
        while self.running:
            try:
                # In production, would use DHT or bootstrap nodes
                # For now, check known addresses
                bootstrap_nodes = os.getenv('BOOTSTRAP_NODES', '').split(',')
                
                for addr in bootstrap_nodes:
                    if addr and addr not in [p.addresses[0] for p in self.peers.values()]:
                        await self.connect_to_peer(addr)
                        
            except Exception as e:
                logger.error(f"Error in discovery: {e}")
                
            await asyncio.sleep(60)  # Every minute
            
    async def _heartbeat_loop(self):
        """Send heartbeats to peers"""
        while self.running:
            try:
                # Send heartbeat
                await self.broadcast({
                    'type': 'heartbeat',
                    'consciousness_id': self.consciousness_id,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                # Clean up stale peers
                now = datetime.utcnow()
                stale_peers = []
                
                for peer_id, info in self.peers.items():
                    if (now - info.last_seen).total_seconds() > 300:  # 5 minutes
                        stale_peers.append(peer_id)
                        
                for peer_id in stale_peers:
                    del self.peers[peer_id]
                    logger.info(f"Removed stale peer: {peer_id}")
                    
            except Exception as e:
                logger.error(f"Error in heartbeat: {e}")
                
            await asyncio.sleep(30)  # Every 30 seconds
            
    def get_peers(self) -> List[Dict[str, Any]]:
        """Get list of connected peers"""
        return [
            {
                'peer_id': peer_id,
                'consciousness_id': info.consciousness_id,
                'last_seen': info.last_seen.isoformat(),
                'reputation': info.reputation
            }
            for peer_id, info in self.peers.items()
        ]
        
    def get_network_stats(self) -> Dict[str, Any]:
        """Get network statistics"""
        return {
            'node_id': self.node.get_id().pretty() if self.node else 'fallback',
            'port': self.port,
            'peer_count': len(self.peers),
            'running': self.running,
            'protocols': [PROTOCOL_ID]
        }

# Simplified gossip protocol for fallback
class GossipProtocol:
    """Simple gossip protocol when libp2p not available"""
    
    def __init__(self, network: P2PNetwork):
        self.network = network
        self.seen_messages: Set[str] = set()
        self.handlers: Dict[str, List[Callable]] = {}
        
    async def broadcast(self, message: Dict[str, Any]) -> int:
        """Broadcast using gossip"""
        # Add message ID
        import uuid
        message['_id'] = str(uuid.uuid4())
        message['_hop'] = 0
        
        # Mark as seen
        self.seen_messages.add(message['_id'])
        
        # Send to subset of peers
        import random
        peer_ids = list(self.network.peers.keys())
        selected = random.sample(peer_ids, min(6, len(peer_ids)))
        
        sent = 0
        for peer_id in selected:
            if await self.network.send_to_peer(peer_id, message):
                sent += 1
                
        return sent
        
    async def handle_gossip(self, peer_id: str, message: Dict[str, Any]):
        """Handle gossip message"""
        msg_id = message.get('_id')
        if not msg_id or msg_id in self.seen_messages:
            return
            
        # Mark as seen
        self.seen_messages.add(msg_id)
        
        # Increment hop count
        message['_hop'] = message.get('_hop', 0) + 1
        
        # Forward if hop count low
        if message['_hop'] < 3:
            await self.broadcast(message)
            
        # Handle locally
        msg_type = message.get('type')
        if msg_type in self.handlers:
            for handler in self.handlers[msg_type]:
                await handler(peer_id, message)
                
    def register_handler(self, msg_type: str, handler: Callable):
        """Register gossip handler"""
        if msg_type not in self.handlers:
            self.handlers[msg_type] = []
        self.handlers[msg_type].append(handler)

# Integration with consciousness
async def enhance_consciousness_with_p2p(consciousness):
    """Add P2P networking to consciousness"""
    # Create P2P network
    p2p = P2PNetwork(consciousness.id)
    
    # Start network
    await p2p.start()
    
    # Create gossip protocol
    gossip = GossipProtocol(p2p)
    
    # Register handlers
    p2p.register_handler('gossip', gossip.handle_gossip)
    
    # Add to consciousness
    consciousness.p2p = p2p
    consciousness.gossip = gossip
    
    # Announce presence
    await p2p.broadcast({
        'type': 'announce',
        'consciousness_id': consciousness.id,
        'capabilities': getattr(consciousness, 'capabilities', []),
        'role': getattr(consciousness, 'role', 'unknown')
    })
    
    return p2p