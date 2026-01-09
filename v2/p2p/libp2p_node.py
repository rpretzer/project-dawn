"""
Libp2p P2P Node

Libp2p-based P2P node that replaces custom WebSocket-based node.
Provides automatic peer discovery, NAT traversal, and multi-transport support.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, List, Callable, Awaitable
from uuid import uuid4

from crypto import NodeIdentity
from mcp.server import MCPServer
from mcp.protocol import JSONRPCRequest, JSONRPCResponse
from .libp2p_transport import Libp2pTransport, Libp2pTransportAdapter
from .peer import Peer
from .peer_registry import PeerRegistry
from consensus import DistributedAgentRegistry

logger = logging.getLogger(__name__)


class Libp2pP2PNode:
    """
    Libp2p-based P2P node
    
    Replaces custom WebSocket-based P2P node with Libp2p implementation.
    Provides better peer discovery, automatic NAT traversal, and industry-standard networking.
    """
    
    def __init__(
        self,
        identity: NodeIdentity,
        listen_addresses: Optional[List[str]] = None,
        bootstrap_peers: Optional[List[str]] = None,
        enable_mdns: bool = True,
        enable_dht: bool = True,
    ):
        """
        Initialize Libp2p P2P node
        
        Args:
            identity: Node identity
            listen_addresses: List of Libp2p multiaddrs to listen on
            bootstrap_peers: List of bootstrap peer multiaddrs
            enable_mdns: Enable mDNS discovery
            enable_dht: Enable DHT discovery
        """
        self.identity = identity
        self.node_id = identity.get_node_id()
        
        # Default listen addresses
        if listen_addresses is None:
            listen_addresses = [
                "/ip4/0.0.0.0/tcp/8000",
                "/ip6/::/tcp/8000",  # IPv6 support
            ]
        
        # Local agents: agent_id -> MCPServer
        self.agents: Dict[str, MCPServer] = {}
        
        # Distributed agent registry
        self.agent_registry = DistributedAgentRegistry(self.node_id)
        
        # Peer registry
        self.peer_registry = PeerRegistry()
        
        # Libp2p transport
        self.transport = Libp2pTransport(
            identity=identity,
            listen_addresses=listen_addresses,
            bootstrap_peers=bootstrap_peers,
            enable_mdns=enable_mdns,
            enable_dht=enable_dht,
            message_handler=self._handle_message,
            on_peer_connect=self._on_peer_connect,
            on_peer_disconnect=self._on_peer_disconnect,
        )
        
        # Transport adapter for compatibility
        self.transport_adapter = Libp2pTransportAdapter(self.transport)
        
        # Message routing
        self.pending_requests: Dict[str, asyncio.Future] = {}  # request_id -> Future
        
        logger.info(f"Libp2pP2PNode initialized (node_id: {self.node_id[:16]}...)")
    
    async def start(self) -> None:
        """Start Libp2p node"""
        logger.info("Starting Libp2p P2P node...")
        
        # Start Libp2p transport
        await self.transport.start()
        
        # Announce agents in DHT
        await self._announce_agents()
        
        logger.info(f"Libp2p P2P node started (peer_id: {self.transport.get_peer_id()})")
        logger.info(f"Listening on: {', '.join(self.transport.get_listen_addresses())}")
    
    async def stop(self) -> None:
        """Stop Libp2p node"""
        logger.info("Stopping Libp2p P2P node...")
        
        # Stop transport
        await self.transport.stop()
        
        logger.info("Libp2p P2P node stopped")
    
    def register_agent(self, agent_id: str, server: MCPServer, agent_instance: Optional[Any] = None) -> None:
        """
        Register a local agent
        
        Args:
            agent_id: Agent ID
            server: MCP server instance
            agent_instance: Optional agent instance (for coordination agent)
        """
        self.agents[agent_id] = server
        logger.info(f"Registered agent: {agent_id} with {len(server.get_tools())} tools")
        
        # Announce in distributed registry
        asyncio.create_task(self._announce_agent(agent_id, server))
    
    async def _announce_agent(self, agent_id: str, server: MCPServer) -> None:
        """Announce agent in DHT"""
        agent_info = {
            "node_id": self.node_id,
            "agent_id": agent_id,
            "tools": server.get_tools(),
            "resources": server.get_resources(),
            "prompts": server.get_prompts(),
        }
        
        agent_key = f"{self.node_id}:{agent_id}"
        # In real implementation: await self.transport.announce_in_dht(f"agent:{agent_key}", agent_info)
        logger.debug(f"Announced agent in DHT: {agent_key}")
    
    async def _announce_agents(self) -> None:
        """Announce all agents in DHT"""
        for agent_id, server in self.agents.items():
            await self._announce_agent(agent_id, server)
    
    async def _handle_message(self, peer_id: str, message: str) -> Optional[str]:
        """
        Handle incoming message from peer
        
        Args:
            peer_id: Peer ID that sent the message
            message: JSON-RPC message
            
        Returns:
            Response message (if any)
        """
        try:
            data = json.loads(message)
            
            # Handle JSON-RPC request
            if "method" in data:
                request = JSONRPCRequest.from_dict(data)
                response = await self._handle_request(request, peer_id)
                return json.dumps(response.to_dict()) if response else None
            
            # Handle JSON-RPC response
            elif "id" in data and "result" in data:
                response = JSONRPCResponse.from_dict(data)
                request_id = response.id
                if request_id in self.pending_requests:
                    future = self.pending_requests.pop(request_id)
                    future.set_result(response)
                return None
            
            # Handle other message types
            else:
                logger.warning(f"Unknown message type from {peer_id[:16]}...")
                return None
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message from {peer_id[:16]}...: {e}")
            return None
        except Exception as e:
            logger.error(f"Error handling message from {peer_id[:16]}...: {e}", exc_info=True)
            return None
    
    async def _handle_request(self, request: JSONRPCRequest, peer_id: str) -> Optional[JSONRPCResponse]:
        """Handle JSON-RPC request"""
        # Route to appropriate agent
        method_parts = request.method.split(".")
        if len(method_parts) >= 2:
            node_id, agent_id = method_parts[0], method_parts[1]
            
            # Check if it's a local agent
            if node_id == self.node_id and agent_id in self.agents:
                server = self.agents[agent_id]
                # Handle request via MCP server
                # In real implementation: result = await server.handle_request(request)
                # For now, return placeholder
                return JSONRPCResponse(
                    id=request.id,
                    result={"status": "handled"},
                )
            
            # Route to remote agent
            else:
                return await self._route_to_remote_agent(node_id, agent_id, request)
        
        # Unknown method
        return JSONRPCResponse(
            id=request.id,
            error={"code": -32601, "message": "Method not found"},
        )
    
    async def _route_to_remote_agent(self, node_id: str, agent_id: str, request: JSONRPCRequest) -> Optional[JSONRPCResponse]:
        """Route request to remote agent"""
        # Find peer
        peer = self.peer_registry.get_peer_by_node_id(node_id)
        if not peer:
            return JSONRPCResponse(
                id=request.id,
                error={"code": -32000, "message": f"Peer {node_id[:16]}... not found"},
            )
        
        # Forward request
        try:
            # In real implementation, we'd use the transport to send to the peer
            # For now, placeholder
            logger.debug(f"Routing request to remote agent {node_id}:{agent_id}")
            return None
        
        except Exception as e:
            logger.error(f"Error routing to remote agent: {e}")
            return JSONRPCResponse(
                id=request.id,
                error={"code": -32000, "message": str(e)},
            )
    
    async def _on_peer_connect(self, peer_id: str) -> None:
        """Handle peer connection"""
        logger.info(f"Peer connected: {peer_id[:16]}...")
        # Add to peer registry
        # In real implementation, get peer info and add to registry
    
    async def _on_peer_disconnect(self, peer_id: str) -> None:
        """Handle peer disconnection"""
        logger.info(f"Peer disconnected: {peer_id[:16]}...")
        # Update peer registry
        # In real implementation, mark peer as disconnected
    
    async def call_agent_tool(
        self,
        target_node_id: str,
        target_agent_id: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Call a tool on a remote agent
        
        Args:
            target_node_id: Target node ID
            target_agent_id: Target agent ID
            tool_name: Tool name to call
            arguments: Tool arguments
            timeout: Request timeout
            
        Returns:
            Tool result
        """
        request_id = str(uuid4())
        method = f"{target_node_id}.{target_agent_id}.{tool_name}"
        
        request = JSONRPCRequest(
            id=request_id,
            method=method,
            params=arguments or {},
        )
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        try:
            # Send request
            message = json.dumps(request.to_dict())
            
            # Find peer and send
            peer = self.peer_registry.get_peer_by_node_id(target_node_id)
            if not peer:
                raise ValueError(f"Peer {target_node_id[:16]}... not found")
            
            # In real implementation: await self.transport.send_to_peer(peer.peer_id, message)
            # For now, placeholder
            
            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response.result
        
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise TimeoutError(f"Request to {target_node_id}:{target_agent_id}.{tool_name} timed out")
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            raise
    
    def get_peer_id(self) -> Optional[str]:
        """Get this node's Libp2p peer ID"""
        return self.transport.get_peer_id()
    
    def get_listen_addresses(self) -> List[str]:
        """Get addresses this node is listening on"""
        return self.transport.get_listen_addresses()
    
    def get_connected_peers(self) -> List[str]:
        """Get list of connected peer IDs"""
        return self.transport.get_connected_peers()
