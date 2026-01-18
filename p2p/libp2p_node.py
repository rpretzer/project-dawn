"""
Libp2p P2P Node

Libp2p-based P2P node that replaces custom WebSocket-based node.
Provides automatic peer discovery, NAT traversal, and multi-transport support.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, List
from uuid import uuid4

from crypto import NodeIdentity
from mcp.server import MCPServer
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
        self.peer_id: Optional[str] = None
        
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

        # Align node_id with Libp2p peer_id for routing
        self.peer_id = self.transport.get_peer_id()
        if self.peer_id and self.peer_id != self.node_id:
            self._sync_node_id(self.peer_id)
        
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

        tools = server.tool_registry.list_tools()
        resources = server.resource_registry.list_resources()
        prompts = server.prompt_registry.list_prompts()

        self.agent_registry.register_local_agent(
            agent_id=agent_id,
            name=server.name,
            description=f"MCP agent: {server.name}",
            tools=tools,
            resources=resources,
            prompts=prompts,
        )

        logger.info(f"Registered agent: {agent_id} with {len(tools)} tools")

        # Announce in distributed registry / DHT
        asyncio.create_task(self._announce_agent(agent_id, server))
    
    async def _announce_agent(self, agent_id: str, server: MCPServer) -> None:
        """Announce agent in DHT"""
        # TODO: Announce agent to DHT
        pass
    
    async def _announce_agents(self) -> None:
        """Announce all agents in DHT"""
        for agent_id, server in self.agents.items():
            await self._announce_agent(agent_id, server)

    def _sync_node_id(self, new_node_id: str) -> None:
        """Update node_id to match Libp2p peer ID and refresh registries."""
        old_node_id = self.node_id
        self.node_id = new_node_id
        self.agent_registry = DistributedAgentRegistry(self.node_id)

        for agent_id, server in self.agents.items():
            tools = server.tool_registry.list_tools()
            resources = server.resource_registry.list_resources()
            prompts = server.prompt_registry.list_prompts()
            self.agent_registry.register_local_agent(
                agent_id=agent_id,
                name=server.name,
                description=f"MCP agent: {server.name}",
                tools=tools,
                resources=resources,
                prompts=prompts,
            )

        logger.info(f"Updated node_id from {old_node_id[:16]}... to {new_node_id[:16]}...")
    
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

            if "id" in data and ("result" in data or "error" in data):
                request_id = str(data.get("id"))
                future = self.pending_requests.pop(request_id, None)
                if future and not future.done():
                    future.set_result(data)
                return None

            if "method" not in data:
                logger.warning(f"Unknown message type from {peer_id[:16]}...")
                return None

            response = await self._route_message(data, peer_id)
            if response is None:
                return None
            return json.dumps(response)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message from {peer_id[:16]}...: {e}")
            return None
        except Exception as e:
            logger.error(f"Error handling message from {peer_id[:16]}...: {e}", exc_info=True)
            return None

    async def _route_message(self, message: Dict[str, Any], sender_peer_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Route a JSON-RPC message to the appropriate handler."""
        method = message.get("method", "")

        if method.startswith("node/"):
            return await self._handle_node_method(method, message.get("params", {}))

        if ":" in method and "/" in method:
            target, agent_method = method.split("/", 1)
            target_node_id, agent_id = target.split(":", 1)
            if target_node_id == self.node_id:
                return await self._route_to_local_agent(agent_id, agent_method, message.get("params", {}))
            return await self._route_to_remote_agent(target_node_id, agent_id, agent_method, message)

        if "/" in method:
            agent_id, agent_method = method.split("/", 1)
            return await self._route_to_local_agent(agent_id, agent_method, message.get("params", {}))

        return await self._route_to_local_agent(None, method, message.get("params", {}))

    async def _handle_node_method(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle node-level methods."""
        if method == "node/list_agents":
            agents = self.agent_registry.list_agents()
            return {
                "jsonrpc": "2.0",
                "result": {"agents": [agent.to_dict() for agent in agents]},
            }

        if method == "node/list_peers":
            peers = self.peer_registry.list_peers()
            return {
                "jsonrpc": "2.0",
                "result": {"peers": [peer.to_dict() for peer in peers]},
            }

        if method == "node/get_info":
            return {
                "jsonrpc": "2.0",
                "result": {
                    "node_id": self.node_id,
                    "peer_id": self.transport.get_peer_id(),
                    "agents": list(self.agents.keys()),
                    "peer_count": self.peer_registry.get_peer_count(),
                },
            }

        return {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "Method not found"},
        }

    async def _route_to_local_agent(self, agent_id: Optional[str], method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Route a message to a local agent."""
        if agent_id is None:
            if not self.agents:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": "No agents available"},
                }
            agent_id = list(self.agents.keys())[0]

        agent = self.agents.get(agent_id)
        if not agent:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Agent not found: {agent_id}"},
            }

        request_id = str(uuid4())
        request_json = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": request_id,
        })

        try:
            response_json = await agent.handle_message(request_json)
            if response_json:
                return json.loads(response_json)
            return {"jsonrpc": "2.0", "id": request_id, "result": None}
        except Exception as e:
            logger.error(f"Error routing to agent {agent_id}: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
            }

    async def _route_to_remote_agent(
        self,
        target_node_id: str,
        agent_id: str,
        method: str,
        original_message: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Route message to remote agent via Libp2p."""
        peer = self.peer_registry.get_peer(target_node_id)
        if not peer:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Peer not found: {target_node_id[:16]}..."},
            }

        peer_id = peer.peer_id or peer.node_id
        if peer_id not in self.transport.get_connected_peers():
            connected = await self.transport.connect_to_peer(peer_id, peer.address)
            if not connected:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": f"Failed to connect to peer: {target_node_id[:16]}..."},
                }

        message = original_message.copy()
        message["method"] = f"{target_node_id}:{agent_id}/{method}"
        request_id = str(message.get("id") or uuid4())
        message["id"] = request_id

        future = asyncio.Future()
        self.pending_requests[request_id] = future

        try:
            await self.transport.send_to_peer(peer_id, json.dumps(message))
            return await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": "Remote request timed out"},
            }
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            logger.error(f"Error routing to remote agent: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
            }
    
    async def _on_peer_connect(self, peer_id: str) -> None:
        """Handle peer connection"""
        logger.info(f"Peer connected: {peer_id[:16]}...")
        peer = self.peer_registry.get_peer(peer_id)
        if peer is None:
            peer = Peer(node_id=peer_id, address=peer_id, peer_id=peer_id, connected=True)
            self.peer_registry.add_peer(peer)
        else:
            peer.connected = True
            self.peer_registry.update_peer_activity(peer_id)
    
    async def _on_peer_disconnect(self, peer_id: str) -> None:
        """Handle peer disconnection"""
        logger.info(f"Peer disconnected: {peer_id[:16]}...")
        peer = self.peer_registry.get_peer(peer_id)
        if peer:
            peer.connected = False
            self.peer_registry.update_peer_activity(peer_id)

    def add_peer(self, node_id: str, address: str, peer_id: Optional[str] = None) -> None:
        """Add a peer to the registry."""
        peer = Peer(
            node_id=node_id,
            address=address,
            peer_id=peer_id or node_id,
            connected=False,
        )
        self.peer_registry.add_peer(peer)
    
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
        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": f"{target_node_id}:{target_agent_id}/tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
        }

        future = asyncio.Future()
        self.pending_requests[request_id] = future

        peer = self.peer_registry.get_peer(target_node_id)
        if not peer:
            self.pending_requests.pop(request_id, None)
            raise ValueError(f"Peer {target_node_id[:16]}... not found")

        peer_id = peer.peer_id or peer.node_id
        if peer_id not in self.transport.get_connected_peers():
            connected = await self.transport.connect_to_peer(peer_id, peer.address)
            if not connected:
                self.pending_requests.pop(request_id, None)
                raise ConnectionError(f"Failed to connect to peer {target_node_id[:16]}...")

        try:
            await self.transport.send_to_peer(peer_id, json.dumps(message))
            response = await asyncio.wait_for(future, timeout=timeout)
            return response.get("result")
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise TimeoutError(f"Request to {target_node_id}:{target_agent_id}.{tool_name} timed out")
        except Exception:
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
