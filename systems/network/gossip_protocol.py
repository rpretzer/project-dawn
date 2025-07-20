# systems/network/gossip_protocol.py
"""
Production-ready Gossip Protocol for Distributed Coordination
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Set, Optional, Any, Callable
from dataclasses import dataclass, field
import aiohttp
import websockets

logger = logging.getLogger(__name__)

@dataclass
class GossipMessage:
    """Message propagated through gossip protocol"""
    id: str
    type: str
    data: Dict[str, Any]
    origin: str
    timestamp: float = field(default_factory=time.time)
    hops: int = 0
    ttl: int = 5  # Reduced for production
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'type': self.type,
            'data': self.data,
            'origin': self.origin,
            'timestamp': self.timestamp,
            'hops': self.hops,
            'ttl': self.ttl
        }

class ProductionGossipProtocol:
    """
    Production-ready gossip protocol implementation
    """
    
    def __init__(self, consciousness_id: str, port: int = 8888):
        self.consciousness_id = consciousness_id
        self.port = port
        
        # Peer management
        self.peers: Dict[str, str] = {}  # peer_id -> websocket_url
        self.active_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        
        # Message tracking
        self.seen_messages: Set[str] = set()
        self.message_handlers: Dict[str, List[Callable]] = {}
        
        # Protocol settings
        self.fanout = 3
        self.gossip_interval = 5.0
        self.max_message_age = 300  # 5 minutes
        
        # Server
        self.server = None
        self.running = False
        
    async def start(self):
        """Start gossip protocol server and client"""
        self.running = True
        
        # Start WebSocket server
        self.server = await websockets.serve(
            self.handle_peer_connection,
            'localhost',
            self.port
        )
        
        logger.info(f"Gossip protocol started on port {self.port}")
        
        # Start background tasks
        asyncio.create_task(self._gossip_loop())
        asyncio.create_task(self._cleanup_loop())
        
    async def stop(self):
        """Stop gossip protocol"""
        self.running = False
        
        # Close connections
        for ws in self.active_connections.values():
            await ws.close()
            
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
    async def handle_peer_connection(self, websocket, path):
        """Handle incoming peer connection"""
        peer_id = None
        try:
            # Wait for peer identification
            message = await websocket.recv()
            data = json.loads(message)
            
            if data.get('type') == 'identify':
                peer_id = data.get('peer_id')
                if peer_id:
                    self.active_connections[peer_id] = websocket
                    logger.info(f"Peer {peer_id} connected")
                    
                    # Send acknowledgment
                    await websocket.send(json.dumps({
                        'type': 'identify_ack',
                        'peer_id': self.consciousness_id
                    }))
                    
            # Handle messages
            async for message in websocket:
                await self._handle_message(message, peer_id)
                
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if peer_id and peer_id in self.active_connections:
                del self.active_connections[peer_id]
                logger.info(f"Peer {peer_id} disconnected")
                
    async def add_peer(self, peer_id: str, websocket_url: str):
        """Add a peer to the network"""
        self.peers[peer_id] = websocket_url
        
        # Try to connect
        await self._connect_to_peer(peer_id, websocket_url)
        
    async def _connect_to_peer(self, peer_id: str, url: str):
        """Establish connection to peer"""
        try:
            ws = await websockets.connect(url)
            
            # Send identification
            await ws.send(json.dumps({
                'type': 'identify',
                'peer_id': self.consciousness_id
            }))
            
            # Wait for acknowledgment
            response = await ws.recv()
            data = json.loads(response)
            
            if data.get('type') == 'identify_ack':
                self.active_connections[peer_id] = ws
                
                # Start listening for messages
                asyncio.create_task(self._listen_to_peer(peer_id, ws))
                
        except Exception as e:
            logger.error(f"Failed to connect to peer {peer_id}: {e}")
            
    async def _listen_to_peer(self, peer_id: str, websocket):
        """Listen for messages from peer"""
        try:
            async for message in websocket:
                await self._handle_message(message, peer_id)
        except websockets.exceptions.ConnectionClosed:
            if peer_id in self.active_connections:
                del self.active_connections[peer_id]
                
    async def broadcast(self, message_type: str, data: Dict[str, Any]):
        """Broadcast message to network"""
        message = GossipMessage(
            id=f"{self.consciousness_id}:{time.time()}",
            type=message_type,
            data=data,
            origin=self.consciousness_id
        )
        
        # Mark as seen
        self.seen_messages.add(message.id)
        
        # Handle locally
        await self._process_message(message)
        
        # Gossip to peers
        await self._gossip_message(message)
        
    async def _handle_message(self, raw_message: str, sender_id: str):
        """Handle incoming message"""
        try:
            data = json.loads(raw_message)
            
            # Skip identification messages
            if data.get('type') in ['identify', 'identify_ack']:
                return
                
            message = GossipMessage(**data)
            
            # Check if already seen
            if message.id in self.seen_messages:
                return
                
            # Mark as seen
            self.seen_messages.add(message.id)
            
            # Process message
            await self._process_message(message)
            
            # Continue gossiping if TTL allows
            if message.hops < message.ttl:
                message.hops += 1
                await self._gossip_message(message)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            
    async def _process_message(self, message: GossipMessage):
        """Process message locally"""
        handlers = self.message_handlers.get(message.type, [])
        
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Handler error: {e}")
                
    async def _gossip_message(self, message: GossipMessage):
        """Gossip message to random peers"""
        if not self.active_connections:
            return
            
        # Select random peers
        peer_ids = list(self.active_connections.keys())
        selected = peer_ids[:self.fanout] if len(peer_ids) <= self.fanout else \
                   [peer_ids[i] for i in range(self.fanout)]
                   
        # Send to selected peers
        for peer_id in selected:
            if peer_id != message.origin:  # Don't send back to origin
                ws = self.active_connections.get(peer_id)
                if ws:
                    try:
                        await ws.send(json.dumps(message.to_dict()))
                    except:
                        # Remove failed connection
                        del self.active_connections[peer_id]
                        
    async def _gossip_loop(self):
        """Periodic gossip of recent messages"""
        while self.running:
            await asyncio.sleep(self.gossip_interval)
            # Could re-gossip important messages here
            
    async def _cleanup_loop(self):
        """Clean up old messages"""
        while self.running:
            await asyncio.sleep(60)  # Every minute
            
            # Remove old message IDs
            current_time = time.time()
            self.seen_messages = {
                msg_id for msg_id in self.seen_messages
                if current_time - float(msg_id.split(':')[1]) < self.max_message_age
            }
            
    def on(self, message_type: str, handler: Callable):
        """Register message handler"""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)