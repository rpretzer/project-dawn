"""
P2P Node

Decentralized node that replaces the centralized Host.
Manages local agents and routes messages to/from peers.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional, List, Callable, Awaitable
from uuid import uuid4

from crypto import NodeIdentity
from mcp.server import MCPServer
from mcp.protocol import JSONRPCRequest, JSONRPCResponse
from mcp.encrypted_transport import EncryptedWebSocketServer, EncryptedWebSocketTransport
from .peer import Peer
from .peer_registry import PeerRegistry
from .discovery import PeerDiscovery
from .privacy import PrivacyLayer
from consensus import DistributedAgentRegistry
from llm.config import LLMConfig, load_config, save_config
from llm.ollama import list_models_async, chat_async
from security import TrustManager, PeerValidator, AuthManager, Permission, AuditLogger, AuditEventType
from metrics import register_metrics, get_metrics_collector
from resilience.rate_limit import RateLimiter, RateLimitConfig
from resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from resilience.errors import RateLimitError, CircuitBreakerOpenError, NetworkError

logger = logging.getLogger(__name__)


class P2PNode:
    """
    Decentralized P2P node
    
    Replaces the centralized Host with a peer-to-peer node.
    Each node can host multiple agents and route messages to peers.
    """
    
    def __init__(
        self,
        identity: NodeIdentity,
        address: str = "ws://localhost:8000",
        bootstrap_nodes: Optional[List[str]] = None,
        enable_encryption: bool = True,
        enable_privacy: bool = False,
        privacy_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize P2P node
        
        Args:
            identity: Node identity
            address: This node's address
            bootstrap_nodes: List of bootstrap node addresses
            enable_encryption: Enable encryption for connections
            enable_privacy: Enable privacy features (onion routing, padding, timing obfuscation)
            privacy_config: Privacy configuration dict
        """
        self.identity = identity
        self.node_id = identity.get_node_id()
        self.address = address
        self.enable_encryption = enable_encryption
        self.enable_privacy = enable_privacy
        
        # Initialize privacy layer if enabled
        if enable_privacy:
            privacy_config = privacy_config or {}
            self.privacy_layer = PrivacyLayer(
                identity=identity,
                enable_onion=privacy_config.get("onion_routing", True),
                enable_padding=privacy_config.get("message_padding", True),
                enable_timing_obfuscation=privacy_config.get("timing_obfuscation", True),
            )
        else:
            self.privacy_layer = None
        
        # Local agents: agent_id -> MCPServer
        self.agents: Dict[str, MCPServer] = {}
        
        # Coordination agent reference (for chat rooms and tasks)
        self.coordination_agent: Optional[Any] = None
        
        # Distributed agent registry
        self.agent_registry = DistributedAgentRegistry(self.node_id)
        
        # Security: Trust, authentication, and audit logging
        self.audit_logger = AuditLogger()
        self.trust_manager = TrustManager()
        self.auth_manager = AuthManager()
        self.peer_validator = PeerValidator(self.trust_manager, identity, self.audit_logger)
        
        # Metrics: Prometheus metrics collection
        self.metrics = register_metrics()
        
        # Peer registry and discovery (with validator)
        self.peer_registry = PeerRegistry(peer_validator=self.peer_validator)
        self.discovery = PeerDiscovery(
            self.peer_registry,
            bootstrap_nodes=bootstrap_nodes,
            enable_mdns=True,
            enable_gossip=True,
            enable_dht=False,  # DHT disabled by default (enable for large networks)
            identity=identity,
        )
        
        # Peer connections: node_id -> EncryptedWebSocketTransport
        self.peer_connections: Dict[str, EncryptedWebSocketTransport] = {}
        
        # Encrypted WebSocket server for incoming connections
        self.server: Optional[EncryptedWebSocketServer] = None
        
        # Message routing
        self.pending_requests: Dict[str, asyncio.Future] = {}  # request_id -> Future
        
        # Event handlers
        self.on_agent_registered: Optional[Callable[[str], None]] = None
        self.on_agent_unregistered: Optional[Callable[[str], None]] = None
        self.on_peer_connected: Optional[Callable[[Peer], None]] = None
        self.on_peer_disconnected: Optional[Callable[[Peer], None]] = None
        
        # Track start time for uptime calculation
        self.start_time: Optional[float] = None
        
        logger.info(f"P2PNode initialized: {self.node_id[:16]}...")
    
    async def start(self, host: str = "localhost", port: int = 8000) -> None:
        """
        Start the P2P node
        
        Args:
            host: Server host
            port: Server port
        """
        # Start encrypted WebSocket server (with trust manager for signature verification)
        self.server = EncryptedWebSocketServer(
            identity=self.identity,
            message_handler=self._handle_incoming_message,
            on_connect=self._on_client_connect,
            on_disconnect=self._on_client_disconnect,
            enable_encryption=self.enable_encryption,
            peer_registry=self.peer_registry,
        )
        # Inject trust manager and validator for signature verification
        self.server.trust_manager = self.trust_manager
        self.server.peer_validator = self.peer_validator
        
        # Start discovery
        await self.discovery.discover_bootstrap()
        self.discovery.start_mdns()
        
        # Register with mDNS (avoid blocking the event loop)
        await asyncio.to_thread(self.discovery.register_mdns_service, self.node_id, self.address, port)
        
        # Start gossip discovery
        self.discovery.start_gossip(self._broadcast_gossip_announcement)
        
        # Start DHT discovery if enabled
        dht = self.discovery.get_dht()
        if dht:
            self.discovery.start_dht(self._handle_dht_rpc)
        
        # Record start time for uptime calculation
        self.start_time = time.time()
        
        logger.info(f"P2PNode started on {host}:{port}")
        
        # Start server (this blocks)
        await self.server.start(host, port)
    
    async def stop(self) -> None:
        """Stop the P2P node"""
        # Stop discovery
        self.discovery.stop_gossip()
        self.discovery.stop_mdns()
        self.discovery.stop_dht()
        
        # Close peer connections
        for connection in list(self.peer_connections.values()):
            await connection.disconnect()
        self.peer_connections.clear()
        
        # Stop server
        if self.server:
            await self.server.stop()
        
        logger.info("P2PNode stopped")
    
    def register_agent(self, agent_id: str, agent_server: MCPServer, agent_instance: Optional[Any] = None) -> None:
        """
        Register a local agent
        
        Args:
            agent_id: Agent ID (unique within this node)
            agent_server: MCP server for the agent
            agent_instance: Optional agent instance (for accessing agent-specific methods)
        """
        self.agents[agent_id] = agent_server
        
        # Store coordination agent reference if it's a CoordinationAgent
        if agent_instance and hasattr(agent_instance, 'chat_rooms'):
            self.coordination_agent = agent_instance
        
        # Get agent capabilities
        tools = agent_server.tool_registry.list_tools()
        resources = agent_server.resource_registry.list_resources()
        prompts = agent_server.prompt_registry.list_prompts()
        
        # Register in distributed registry
        self.agent_registry.register_local_agent(
            agent_id=agent_id,
            name=agent_server.name,
            description=f"MCP agent: {agent_server.name}",
            tools=tools,
            resources=resources,
            prompts=prompts,
        )
        
        logger.info(f"Registered agent: {agent_id} (node: {self.node_id[:16]}...)")
        
        if self.on_agent_registered:
            self.on_agent_registered(agent_id)
    
    def unregister_agent(self, agent_id: str) -> None:
        """
        Unregister a local agent
        
        Args:
            agent_id: Agent ID
        """
        if agent_id in self.agents:
            del self.agents[agent_id]
            
            # Unregister from distributed registry
            self.agent_registry.unregister_local_agent(agent_id)
            
            logger.info(f"Unregistered agent: {agent_id}")
            
            if self.on_agent_unregistered:
                self.on_agent_unregistered(agent_id)
    
    def get_agent(self, agent_id: str) -> Optional[MCPServer]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[str]:
        """List all local agent IDs"""
        return list(self.agents.keys())
    
    async def connect_to_peer(self, peer: Peer) -> bool:
        """
        Connect to a peer
        
        Args:
            peer: Peer to connect to
            
        Returns:
            True if connected successfully, False otherwise
        """
        # Check if peer is trusted before connecting
        if not self.peer_validator.can_connect(peer.node_id):
            logger.warning(f"Cannot connect to untrusted peer: {peer.node_id[:16]}...")
            self.audit_logger.log_event(
                event_type=AuditEventType.CONNECTION_REJECTED,
                node_id=self.node_id,
                peer_node_id=peer.node_id,
                success=False,
                error="Peer not trusted",
            )
            return False
        
        if peer.node_id in self.peer_connections:
            logger.debug(f"Already connected to peer: {peer.node_id[:16]}...")
            return True
        
        try:
            # Create encrypted transport
            transport = EncryptedWebSocketTransport(
                url=peer.address,
                identity=self.identity,
                enable_encryption=self.enable_encryption,
            )
            
            # Connect
            await transport.connect()
            
            # Store connection
            self.peer_connections[peer.node_id] = transport
            peer.connected = True
            peer.record_connection_success()
            
            logger.info(f"Connected to peer: {peer.node_id[:16]}... ({peer.address})")
            
            # Record metrics
            self.metrics.record_peer_connection("success")
            self.metrics.update_peer_count(len(self.peer_connections))
            
            if self.on_peer_connected:
                self.on_peer_connected(peer)
            
            # Start receiving messages
            asyncio.create_task(self._receive_from_peer(peer.node_id, transport))
            
            return True
        
        except CircuitBreakerOpenError as e:
            logger.warning(f"Circuit breaker open for {peer.node_id[:16]}...: {e}")
            peer.record_connection_failure()
            self.metrics.record_peer_connection("failure")
            self.metrics.record_error("CircuitBreakerOpenError", "p2p_node")
            return False
        except (NetworkError, ConnectionError, TimeoutError) as e:
            logger.error(f"Network error connecting to peer {peer.node_id[:16]}...: {e}")
            peer.record_connection_failure()
            self.metrics.record_peer_connection("failure")
            self.metrics.record_error("NetworkError", "p2p_node")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to peer {peer.node_id[:16]}...: {e}")
            peer.record_connection_failure()
            self.metrics.record_peer_connection("failure")
            self.metrics.record_error("ConnectionError", "p2p_node")
            return False
    
    async def disconnect_from_peer(self, node_id: str) -> None:
        """Disconnect from a peer"""
        if node_id in self.peer_connections:
            transport = self.peer_connections.pop(node_id)
            await transport.disconnect()
            
            peer = self.peer_registry.get_peer(node_id)
            if peer:
                peer.connected = False
                if self.on_peer_disconnected:
                    self.on_peer_disconnected(peer)
            
            logger.info(f"Disconnected from peer: {node_id[:16]}...")
    
    async def _receive_from_peer(self, node_id: str, transport: EncryptedWebSocketTransport) -> None:
        """Receive messages from a peer"""
        try:
            while transport.is_connected:
                message = await transport.receive()
                if message:
                    await self._handle_peer_message(node_id, message)
        except Exception as e:
            logger.error(f"Error receiving from peer {node_id[:16]}...: {e}")
            await self.disconnect_from_peer(node_id)
    
    async def _handle_peer_message(self, sender_node_id: str, message: str) -> None:
        """Handle message from peer"""
        try:
            # Apply privacy layer if enabled (decrypt onion, unpad)
            message_bytes = message.encode('utf-8')
            
            if self.enable_privacy and self.privacy_layer:
                processed_message = await self.privacy_layer.receive_private_message(
                    message_bytes,
                    sender_node_id,
                )
                
                if processed_message is None:
                    # Message was forwarded (onion routing)
                    logger.debug(f"Message forwarded from {sender_node_id[:16]}...")
                    return
                
                message = processed_message.decode('utf-8', errors='ignore')
            
            # Parse JSON-RPC message
            data = json.loads(message)
            
            # Check if it's a response to our request
            if "id" in data and "result" in data:
                request_id = str(data["id"])
                if request_id in self.pending_requests:
                    future = self.pending_requests.pop(request_id)
                    if not future.done():
                        future.set_result(data)
                    return
            
            # Check if it's an error response
            if "id" in data and "error" in data:
                request_id = str(data["id"])
                if request_id in self.pending_requests:
                    future = self.pending_requests.pop(request_id)
                    if not future.done():
                        # Create error response
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": data.get("id"),
                            "error": data["error"],
                        }
                        future.set_result(error_response)
                    return
            
            # Otherwise, route to appropriate handler
            # This could be a request from the peer
            await self._route_message(data, sender_node_id)
        
        except Exception as e:
            logger.error(f"Error handling peer message: {e}", exc_info=True)
    
    async def _route_message(self, message: Dict[str, Any], sender_node_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Route message to appropriate handler
        
        Args:
            message: JSON-RPC message
            sender_node_id: Node ID of sender (if from peer)
            
        Returns:
            Response message or None
        """
        import time
        start_time = time.time()
        method = message.get("method", "")
        message_type = "request" if "id" in message else "notification"
        message_size = len(str(message).encode('utf-8'))
        
        try:
            # Authorization check for peer messages
            if sender_node_id and sender_node_id != self.node_id:
                # Check if peer is trusted
                if not self.peer_validator.can_connect(sender_node_id):
                    logger.warning(f"Rejected message from untrusted peer: {sender_node_id[:16]}...")
                    self.metrics.record_error("AuthorizationError", "message_routing")
                    
                    result = {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {
                            "code": -32001,
                            "message": "Unauthorized: peer not trusted",
                        }
                    }
                    
                    # Record metrics
                    latency = time.time() - start_time
                    self.metrics.record_message(message_type, "error", latency, message_size)
                    
                    return result
                
                # Check permissions for agent access
                if ":" in method and "/" in method:
                    # Extract agent_id from method
                    parts = method.split("/", 1)
                    target = parts[0]
                    if ":" in target:
                        _, agent_id = target.split(":", 1)
                        # Check if peer has permission to access agents
                        if not self.auth_manager.has_permission(sender_node_id, Permission.AGENT_EXECUTE):
                            logger.warning(f"Rejected agent access from {sender_node_id[:16]}... (no permission)")
                            self.metrics.record_error("PermissionError", "message_routing")
                            
                            result = {
                                "jsonrpc": "2.0",
                                "id": message.get("id"),
                                "error": {
                                    "code": -32001,
                                    "message": "Unauthorized: no permission to access agents",
                                }
                            }
                            
                            # Record metrics
                            latency = time.time() - start_time
                            self.metrics.record_message(message_type, "error", latency, message_size)
                            
                            return result
            
            # Handle node-level methods
            if method.startswith("node/"):
                result = await self._handle_node_method(method, message.get("params", {}))
                
                # Record metrics
                latency = time.time() - start_time
                status = "success" if result and "error" not in result else "error"
                self.metrics.record_message(message_type, status, latency, message_size)
                
                return result
            
            # Handle agent methods (format: node_id:agent_id/method)
            if ":" in method and "/" in method:
                parts = method.split("/", 1)
                target = parts[0]  # e.g., "node_id:agent_id"
                agent_method = parts[1]  # e.g., "tools/list" or "chat/message"
            
            if ":" in target:
                target_node_id, agent_id = target.split(":", 1)
                
                # Handle chat messages specially
                if agent_method == "chat/message":
                    params = message.get("params", {})
                    msg_content = params.get("message", "")
                    room_id = params.get("room_id", "main")
                    
                    if target_node_id == self.node_id:
                        return await self._handle_chat_message(agent_id, msg_content, room_id)
                    else:
                        # Route to remote agent
                        return await self._route_to_remote_agent(target_node_id, agent_id, agent_method, message)
                
                # Route to local agent
                if target_node_id == self.node_id:
                    return await self._route_to_local_agent(agent_id, agent_method, message.get("params", {}))
                
                # Route to remote peer
                else:
                    result = await self._route_to_remote_agent(target_node_id, agent_id, agent_method, message)
                    
                    # Record metrics
                    latency = time.time() - start_time
                    status = "success" if result and "error" not in result else "error"
                    self.metrics.record_message(message_type, status, latency, message_size)
                    
                    return result
            
            # Handle direct agent methods (format: agent_id/method)
            if "/" in method:
                parts = method.split("/", 1)
                agent_id = parts[0]
                agent_method = parts[1]
                
                if agent_method == "chat/message":
                    params = message.get("params", {})
                    msg_content = params.get("message", "")
                    room_id = params.get("room_id", "main")
                    result = await self._handle_chat_message(agent_id, msg_content, room_id)
                    
                    # Record metrics
                    latency = time.time() - start_time
                    status = "success" if result and "error" not in result else "error"
                    self.metrics.record_message(message_type, status, latency, message_size)
                    
                    return result
            
            # Default: try local agents
            result = await self._route_to_local_agent(None, method, message.get("params", {}))
            
            # Record metrics
            latency = time.time() - start_time
            status = "success" if result and "error" not in result else "error"
            self.metrics.record_message(message_type, status, latency, message_size)
            
            return result
        
        except Exception as e:
            # Record error metrics
            logger.error(f"Error routing message: {e}", exc_info=True)
            self.metrics.record_error("RoutingError", "message_routing")
            
            latency = time.time() - start_time
            self.metrics.record_message(message_type, "error", latency, message_size)
            
            # Return error response
            if "id" in message:
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}",
                    }
                }
            return None
    
    async def _handle_node_method(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle node-level methods"""
        if method == "llm_get_config":
            config = load_config()
            return {"jsonrpc": "2.0", "result": config.to_dict()}

        if method == "llm_set_config":
            config = load_config()
            config.provider = params.get("provider", config.provider)
            config.endpoint = params.get("endpoint", config.endpoint)
            config.model = params.get("model", config.model)
            config.system_prompt = params.get("system_prompt", config.system_prompt)
            save_config(config)
            return {"jsonrpc": "2.0", "result": config.to_dict()}

        if method == "llm_list_models":
            config = load_config()
            endpoint = params.get("endpoint", config.endpoint)
            models = await list_models_async(endpoint)
            return {"jsonrpc": "2.0", "result": {"models": models}}
        # Handle DHT methods
        if method == "dht_find_node":
            dht = self.discovery.get_dht()
            if dht:
                target_id = params.get("target_id")
                if target_id:
                    result = dht.handle_find_node(target_id)
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                    }
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "DHT not enabled"},
            }
        
        elif method == "dht_find_value":
            dht = self.discovery.get_dht()
            if dht:
                key = params.get("key")
                if key:
                    result = dht.handle_find_value(key)
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                    }
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "DHT not enabled"},
            }
        
        elif method == "dht_store":
            dht = self.discovery.get_dht()
            if dht:
                key = params.get("key")
                value = params.get("value")
                ttl = params.get("ttl", 3600.0)
                if key and value is not None:
                    result = dht.handle_store(key, value, ttl)
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                    }
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "DHT not enabled"},
            }
        
        elif method == "node/list_agents":
            # Return agents from distributed registry
            agents = self.agent_registry.list_agents()
            return {
                "jsonrpc": "2.0",
                "result": {
                    "agents": [agent.to_dict() for agent in agents]
                }
            }
        
        elif method == "node/create_agent":
            # Create a new agent
            try:
                agent_id = params.get("agent_id")
                agent_name = params.get("name", "UnnamedAgent")
                
                if not agent_id:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32602,
                            "message": "agent_id parameter required",
                        }
                    }
                
                if agent_id in self.agents:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32602,
                            "message": f"Agent {agent_id} already exists",
                        }
                    }
                
                # Create a new FirstAgent instance
                from agents import FirstAgent
                agent = FirstAgent(agent_id, agent_name)
                self.register_agent(agent_id, agent.server)
                
                logger.info(f"Created new agent: {agent_id} ({agent_name})")
                
                # Get agent from registry to return full info
                agent_info = self.agent_registry.get_agent(f"{self.node_id}:{agent_id}")
                
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "agent_id": agent_id,
                        "name": agent_name,
                        "status": "created",
                        "full_agent_id": f"{self.node_id}:{agent_id}",
                    }
                }
            except Exception as e:
                logger.error(f"Error creating agent: {e}", exc_info=True)
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Failed to create agent: {str(e)}",
                    }
                }
        
        elif method == "node/list_peers":
            peers = self.peer_registry.list_peers()
            return {
                "jsonrpc": "2.0",
                "result": {
                    "peers": [peer.to_dict() for peer in peers]
                }
            }
        
        elif method == "node/get_info":
            info = {
                "node_id": self.node_id,
                "address": self.address,
                "agents": list(self.agents.keys()),
                "peer_count": self.peer_registry.get_peer_count(),
            }
            
            # Add privacy info if enabled
            if self.enable_privacy and self.privacy_layer:
                info["privacy"] = self.privacy_layer.get_privacy_config()
            
            return {
                "jsonrpc": "2.0",
                "result": info,
            }
        
        elif method == "node/configure_privacy":
            """Configure privacy settings"""
            if not self.enable_privacy:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": "Privacy features not enabled",
                    }
                }
            
            if not self.privacy_layer:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": "Privacy layer not initialized",
                    }
                }
            
            # Update privacy configuration
            config = params.get("config", {})
            if "onion_routing" in config:
                self.privacy_layer.enable_onion = config["onion_routing"]
            if "message_padding" in config:
                self.privacy_layer.enable_padding = config["message_padding"]
            if "timing_obfuscation" in config:
                self.privacy_layer.enable_timing_obfuscation = config["timing_obfuscation"]
            
            return {
                "jsonrpc": "2.0",
                "result": {
                    "privacy_config": self.privacy_layer.get_privacy_config(),
                }
            }
        
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": "Method not found",
            }
        }
    
    async def _handle_chat_message(self, agent_id: str, message: str, room_id: str = "main") -> Dict[str, Any]:
        """
        Handle chat message from/to agent
        
        Args:
            agent_id: Agent ID
            message: Message content
            room_id: Chat room ID
            
        Returns:
            Response from agent
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Agent not found: {agent_id}",
                }
            }
        
        # Ensure room exists in coordination agent if available
        if self.coordination_agent:
            room = self.coordination_agent.ensure_room(room_id)
            # Add agent to room participants if not already there
            if agent_id not in room["participants"]:
                self.coordination_agent.add_participant(room_id, agent_id)
        
        response_text = ""
        config = load_config()
        if config.provider == "ollama" and config.model:
            try:
                response_text = await chat_async(
                    config.endpoint,
                    config.model,
                    [{"role": "user", "content": message}],
                    system_prompt=config.system_prompt,
                )
            except Exception as exc:
                logger.error(f"Ollama chat failed: {exc}", exc_info=True)
                response_text = "I couldn't reach the LLM backend. Please check the Ollama config."
        else:
            response_text = "I received your message, but no LLM is configured yet. Set a model in the LLM picker."
        
        logger.info(f"Agent {agent_id} received chat message in room {room_id}")
        
        return {
            "jsonrpc": "2.0",
            "result": {
                "response": response_text,
                "content": response_text,
                "agent_id": agent_id,
                "room_id": room_id,
            }
        }
    
    async def _route_to_local_agent(self, agent_id: Optional[str], method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Route message to local agent"""
        # If agent_id not specified, try first agent
        if agent_id is None:
            if not self.agents:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": "No agents available",
                    }
                }
            agent_id = list(self.agents.keys())[0]
        
        agent = self.agents.get(agent_id)
        if not agent:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Agent not found: {agent_id}",
                }
            }
        
        # Create JSON-RPC request as JSON string
        request_id = str(uuid4())
        request_json = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": request_id,
        })
        
        # Handle request via agent's handle_message
        try:
            response_json = await agent.handle_message(request_json)
            if response_json:
                return json.loads(response_json)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": None,
                }
        except Exception as e:
            logger.error(f"Error routing to agent {agent_id}: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e),
                }
            }
    
    async def _route_to_remote_agent(
        self,
        target_node_id: str,
        agent_id: str,
        method: str,
        original_message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Route message to remote agent via peer"""
        # Check if we're connected to the target node
        if target_node_id not in self.peer_connections:
            # Try to connect
            peer = self.peer_registry.get_peer(target_node_id)
            if not peer:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Peer not found: {target_node_id[:16]}...",
                    }
                }
            
            connected = await self.connect_to_peer(peer)
            if not connected:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Failed to connect to peer: {target_node_id[:16]}...",
                    }
                }
        
        # Forward message to peer
        transport = self.peer_connections[target_node_id]
        
        # Update method to include target
        message = original_message.copy()
        message["method"] = f"{target_node_id}:{agent_id}/{method}"
        
        # Send and wait for response
        request_id = message.get("id", str(uuid4()))
        message["id"] = request_id
        
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        try:
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            
            # Apply privacy layer if enabled
            if self.enable_privacy and self.privacy_layer:
                async def send_with_privacy(msg_bytes, target):
                    # Decode and send via transport
                    await transport.send(msg_bytes.decode('utf-8', errors='ignore'))
                
                await self.privacy_layer.send_private_message(
                    message_bytes,
                    target_node_id,
                    send_with_privacy,
                )
            else:
                await transport.send(message_json)
            
            # Wait for response (with timeout)
            response = await asyncio.wait_for(future, timeout=30.0)
            return response
        
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Request timeout",
                }
            }
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            logger.error(f"Error routing to remote agent: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e),
                }
            }
    
    async def _handle_incoming_message(self, message: str, client_id: Any) -> Optional[str]:
        """Handle incoming message from client (WebSocket)"""
        try:
            data = json.loads(message)
            request_id = data.get("id")
            response = await self._route_message(data)
            
            if response:
                # Ensure response has the request ID if it was in the request
                if request_id and "id" not in response:
                    response["id"] = request_id
                return json.dumps(response)
            
            # If no response, return error response
            return json.dumps({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "No response from server",
                }
            })
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in incoming message: {e}")
            return json.dumps({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error",
                }
            })
        except Exception as e:
            logger.error(f"Error handling incoming message: {e}", exc_info=True)
            return json.dumps({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                }
            })
    
    async def _on_client_connect(self, client_id: Any) -> None:
        """Handle client connection"""
        logger.debug(f"Client connected: {client_id}")
    
    async def _on_client_disconnect(self, client_id: Any) -> None:
        """Handle client disconnection"""
        logger.debug(f"Client disconnected: {client_id}")
    
    async def _broadcast_gossip_announcement(self, announcement: Dict[str, Any]) -> None:
        """Broadcast gossip announcement to connected peers"""
        message = json.dumps(announcement)
        
        for node_id, transport in list(self.peer_connections.items()):
            try:
                await transport.send(message)
            except Exception as e:
                logger.warning(f"Failed to send gossip to {node_id[:16]}...: {e}")
    
    async def _handle_dht_rpc(self, node_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle DHT RPC request from another node
        
        Args:
            node_id: Node ID of requester
            request: RPC request
            
        Returns:
            RPC response
        """
        method = request.get("method", "")
        params = request.get("params", {})
        
        # Route to appropriate handler
        if method == "dht_find_node":
            return await self._handle_node_method(method, params)
        elif method == "dht_find_value":
            return await self._handle_node_method(method, params)
        elif method == "dht_store":
            return await self._handle_node_method(method, params)
        else:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                }
            }
    
    async def call_agent(
        self,
        target: str,  # Format: "node_id:agent_id" or "agent_id" (local)
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Call an agent method
        
        Args:
            target: Agent target (node_id:agent_id or agent_id for local)
            method: Method name
            params: Method parameters
            
        Returns:
            Response from agent
        """
        # Parse target
        if ":" in target:
            node_id, agent_id = target.split(":", 1)
        else:
            node_id = self.node_id
            agent_id = target
        
        # Create request
        request = {
            "jsonrpc": "2.0",
            "method": f"{node_id}:{agent_id}/{method}",
            "params": params or {},
            "id": str(uuid4()),
        }
        
        # Route message
        response = await self._route_message(request)
        
        if not response:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "No response",
                }
            }
        
        return response
