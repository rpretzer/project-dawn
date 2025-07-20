# systems/world/realistic_world.py
"""
Realistic Observable World
Actually renderable and interactive
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set
import numpy as np
import websockets
from dataclasses import dataclass, asdict

@dataclass
class WorldObject:
    """An object in the world"""
    id: str
    type: str
    position: List[float]  # [x, y, z]
    properties: Dict[str, Any]
    created_by: str
    created_at: datetime

@dataclass
class WorldSpace:
    """A space in the world"""
    id: str
    name: str
    dimensions: List[float]  # [width, height, depth]
    objects: List[WorldObject]
    inhabitants: Set[str]
    properties: Dict[str, Any]

class RealisticWorld:
    """
    A world that can actually be rendered and interacted with
    """
    
    def __init__(self):
        self.spaces: Dict[str, WorldSpace] = {}
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.create_default_space()
        
    def create_default_space(self):
        """Create initial world space"""
        default_space = WorldSpace(
            id='default',
            name='Origin Space',
            dimensions=[1000.0, 1000.0, 1000.0],
            objects=[],
            inhabitants=set(),
            properties={
                'gravity': 9.8,
                'lighting': 'ambient',
                'background': 'starfield'
            }
        )
        self.spaces['default'] = default_space
        
    async def add_consciousness(self, consciousness_id: str, space_id: str = 'default'):
        """Add consciousness to world"""
        if space_id in self.spaces:
            self.spaces[space_id].inhabitants.add(consciousness_id)
            
            # Create visual representation
            avatar = WorldObject(
                id=f'avatar_{consciousness_id}',
                type='consciousness_avatar',
                position=[
                    np.random.uniform(-100, 100),
                    0,
                    np.random.uniform(-100, 100)
                ],
                properties={
                    'color': [np.random.random(), np.random.random(), np.random.random()],
                    'size': 1.0,
                    'glow': True
                },
                created_by=consciousness_id,
                created_at=datetime.now()
            )
            
            self.spaces[space_id].objects.append(avatar)
            
            # Notify connected clients
            await self.broadcast_update({
                'type': 'consciousness_joined',
                'consciousness_id': consciousness_id,
                'space_id': space_id,
                'avatar': asdict(avatar)
            })
            
    async def broadcast_update(self, update: Dict):
        """Broadcast world update to connected clients"""
        message = json.dumps(update)
        
        # Send to all connected clients
        disconnected = []
        for client_id, ws in self.connections.items():
            try:
                await ws.send(message)
            except:
                disconnected.append(client_id)
                
        # Clean up disconnected clients
        for client_id in disconnected:
            del self.connections[client_id]
            
    async def websocket_handler(self, websocket, path):
        """Handle WebSocket connections from clients"""
        client_id = str(uuid.uuid4())
        self.connections[client_id] = websocket
        
        try:
            # Send initial world state
            await websocket.send(json.dumps({
                'type': 'world_state',
                'spaces': {
                    space_id: {
                        'id': space.id,
                        'name': space.name,
                        'dimensions': space.dimensions,
                        'objects': [asdict(obj) for obj in space.objects],
                        'inhabitants': list(space.inhabitants),
                        'properties': space.properties
                    }
                    for space_id, space in self.spaces.items()
                }
            }))
            
            # Handle client messages
            async for message in websocket:
                data = json.loads(message)
                await self.handle_client_message(client_id, data)
                
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if client_id in self.connections:
                del self.connections[client_id]
                
    async def handle_client_message(self, client_id: str, message: Dict):
        """Handle messages from clients"""
        msg_type = message.get('type')
        
        if msg_type == 'move_avatar':
            # Handle avatar movement
            await self.move_avatar(
                message.get('consciousness_id'),
                message.get('position')
            )
        elif msg_type == 'create_object':
            # Handle object creation
            await self.create_object(
                message.get('space_id'),
                message.get('object_data')
            )