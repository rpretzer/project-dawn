"""
MCP Host Implementation

Central coordinator that manages MCP clients, routes messages,
and coordinates AI integration.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Callable, Awaitable
from .event_bus import EventBus, Event, EventType
from mcp.server import MCPServer
from mcp.client import MCPClient
from mcp.transport import WebSocketServer, WEBSOCKETS_AVAILABLE

logger = logging.getLogger(__name__)


class ClientSession:
    """Represents a client session"""
    
    def __init__(self, client_id: str, client_type: str = "client"):
        self.client_id = client_id
        self.client_type = client_type  # "client", "server", "agent"
        self.connected_at: Optional[float] = None
        self.last_activity: Optional[float] = None
        self.metadata: Dict[str, Any] = {}
    
    def update_activity(self):
        """Update last activity timestamp"""
        import time
        self.last_activity = time.time()


class MCPHost:
    """
    MCP Host
    
    Manages multiple client instances, controls client connections,
    enforces security policies, and coordinates AI integration.
    """
    
    def __init__(self, name: str = "mcp-host"):
        """
        Initialize MCP Host
        
        Args:
            name: Host name
        """
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("websockets library required for MCP Host")
        
        self.name = name
        self.event_bus = EventBus()
        self.sessions: Dict[str, ClientSession] = {}
        self.servers: Dict[str, MCPServer] = {}
        self.clients: Dict[str, MCPClient] = {}
        self.ws_server: Optional[WebSocketServer] = None
        self.message_router: Dict[str, str] = {}  # client_id -> server_id
        
        # Subscribe to events to broadcast to clients
        self.event_bus.subscribe_all(self._handle_event)
        
        logger.info(f"MCP Host '{name}' initialized")
    
    async def start(self, host: str = "localhost", port: int = 8000) -> None:
        """
        Start MCP Host
        
        Args:
            host: Host address
            port: Port number
        """
        # Create WebSocket server
        self.ws_server = WebSocketServer(
            message_handler=self._handle_client_message,
            on_connect=self._on_client_connect,
            on_disconnect=self._on_client_disconnect,
        )
        
        logger.info(f"Starting MCP Host on {host}:{port}")
        
        # Start WebSocket server
        await self.ws_server.start(host=host, port=port)
    
    async def stop(self) -> None:
        """Stop MCP Host"""
        logger.info("Stopping MCP Host...")
        
        # Stop WebSocket server
        if self.ws_server:
            await self.ws_server.stop()
        
        # Disconnect all clients
        for client_id in list(self.clients.keys()):
            await self.disconnect_client(client_id)
        
        # Clear sessions
        self.sessions.clear()
        self.servers.clear()
        self.clients.clear()
        
        logger.info("MCP Host stopped")
    
    async def _on_client_connect(self, client_id: Any) -> None:
        """Called when client connects"""
        session_id = str(uuid.uuid4())
        session = ClientSession(client_id=session_id, client_type="client")
        import time
        session.connected_at = time.time()
        session.update_activity()
        
        self.sessions[session_id] = session
        self.message_router[str(client_id)] = session_id
        
        logger.info(f"Client connected: {session_id} (internal ID: {client_id})")
        
        # Publish connection event
        await self.event_bus.publish_event(
            EventType.CONNECTION,
            source=self.name,
            data={
                "client_id": session_id,
                "internal_id": str(client_id),
            },
            event_id=session_id,
        )
        
        # Broadcast connection event to all clients
        await self._broadcast_event({
            "type": "event",
            "data": {
                "type": "connection",
                "source": self.name,
                "data": {
                    "client_id": session_id,
                }
            }
        })
    
    async def _on_client_disconnect(self, client_id: Any) -> None:
        """Called when client disconnects"""
        session_id = self.message_router.pop(str(client_id), None)
        
        if session_id and session_id in self.sessions:
            session = self.sessions.pop(session_id)
            
            if session_id in self.clients:
                del self.clients[session_id]
            if session_id in self.servers:
                del self.servers[session_id]
            
            logger.info(f"Client disconnected: {session_id}")
            
            # Publish disconnection event
            await self.event_bus.publish_event(
                EventType.DISCONNECTION,
                source=self.name,
                data={
                    "client_id": session_id,
                    "internal_id": str(client_id),
                },
                event_id=session_id,
            )
            
            # Broadcast disconnection event to all clients
            await self._broadcast_event({
                "type": "event",
                "data": {
                    "type": "disconnection",
                    "source": self.name,
                    "data": {
                        "client_id": session_id,
                    }
                }
            })
    
    async def _handle_client_message(self, message: str, client_id: Any) -> Optional[str]:
        """
        Handle message from client (frontend or other client)
        
        Args:
            message: JSON-RPC message
            client_id: Internal client ID
            
        Returns:
            Response message or None
        """
        session_id = self.message_router.get(str(client_id))
        if not session_id:
            logger.warning(f"Message from unknown client: {client_id}")
            return None
        
        session = self.sessions.get(session_id)
        if session:
            session.update_activity()
        
        # Try to parse as JSON-RPC request
        try:
            from mcp.protocol import JSONRPCRequest, JSONRPCResponse, JSONRPCError
            request = JSONRPCRequest.from_json(message)
            
            # Handle host-level methods (for frontend clients)
            if request.method.startswith("host/"):
                return await self._handle_host_method(request, session_id)
            
            # Route to appropriate server
            if session_id in self.servers:
                # Client is actually a server, handle directly
                server = self.servers[session_id]
                response = await server.handle_message(message)
                return response
            
            # For frontend clients, route tool calls to servers
            if request.method == "tools/call":
                return await self._handle_tool_call(request, session_id)
            elif request.method == "tools/list":
                return await self._handle_tools_list(request, session_id)
            
            # Unknown method
            error = JSONRPCError.method_not_found(request.method)
            return JSONRPCResponse.error_response(request.id, error).to_json()
        
        except Exception as e:
            logger.error(f"Error handling message from {session_id}: {e}", exc_info=True)
            from mcp.protocol import JSONRPCResponse, JSONRPCError
            error = JSONRPCError.internal_error(str(e))
            return JSONRPCResponse.error_response(None, error).to_json()
    
    async def _handle_host_method(self, request, session_id: str) -> Optional[str]:
        """Handle host-level methods"""
        from mcp.protocol import JSONRPCResponse, JSONRPCError
        
        if request.method == "host/list_servers":
            # Return list of registered servers (agents)
            servers_list = []
            for server_id, server in self.servers.items():
                session = self.sessions.get(server_id)
                servers_list.append({
                    "server_id": server_id,
                    "name": session.metadata.get("name", server_id) if session else server_id,
                    "tools": server.get_tools(),
                    "connected_at": session.connected_at if session else None,
                })
            
            return JSONRPCResponse.success(request.id, {"servers": servers_list}).to_json()
        
        elif request.method == "host/list_tools":
            # Return all tools from all servers
            all_tools = []
            for server_id, server in self.servers.items():
                tools = server.get_tools()
                for tool in tools:
                    tool_with_server = tool.copy()
                    tool_with_server["server_id"] = server_id
                    all_tools.append(tool_with_server)
            
            return JSONRPCResponse.success(request.id, {"tools": all_tools}).to_json()
        
        elif request.method == "host/subscribe_events":
            # Subscribe to events (client will receive notifications)
            # This is handled by the event bus automatically
            return JSONRPCResponse.success(request.id, {"subscribed": True}).to_json()
        
        else:
            error = JSONRPCError.method_not_found(request.method)
            return JSONRPCResponse.error_response(request.id, error).to_json()
    
    async def _handle_tools_list(self, request, session_id: str) -> str:
        """Handle tools/list request - return all tools from all servers"""
        from mcp.protocol import JSONRPCResponse
        
        all_tools = []
        for server_id, server in self.servers.items():
            tools = server.get_tools()
            for tool in tools:
                tool_with_server = tool.copy()
                tool_with_server["server_id"] = server_id
                all_tools.append(tool_with_server)
        
        return JSONRPCResponse.success(request.id, {"tools": all_tools}).to_json()
    
    async def _handle_tool_call(self, request, session_id: str) -> str:
        """Handle tools/call request - route to appropriate server"""
        from mcp.protocol import JSONRPCResponse, JSONRPCError
        
        params = request.params if isinstance(request.params, dict) else {}
        tool_name = params.get("name")
        server_id = params.get("server_id")  # Optional: specific server
        
        if not tool_name:
            error = JSONRPCError.invalid_params("Missing 'name' parameter")
            return JSONRPCResponse.error_response(request.id, error).to_json()
        
        # Find server with this tool
        target_server = None
        if server_id and server_id in self.servers:
            server = self.servers[server_id]
            if server.has_tool(tool_name):
                target_server = server
        else:
            # Search all servers
            for sid, server in self.servers.items():
                if server.has_tool(tool_name):
                    target_server = server
                    server_id = sid
                    break
        
        if not target_server:
            error = JSONRPCError.method_not_found(f"Tool '{tool_name}' not found")
            return JSONRPCResponse.error_response(request.id, error).to_json()
        
        # Call tool
        try:
            arguments = params.get("arguments", {})
            response = await target_server._handle_tools_call(tool_name, arguments)
            
            # Publish tool called event (will be broadcast via _handle_event)
            await self.event_bus.publish_event(
                EventType.TOOL_CALLED,
                source=self.name,
                data={
                    "tool_name": tool_name,
                    "server_id": server_id,
                    "client_id": session_id,
                    "arguments": arguments,
                }
            )
            
            # Wrap in JSON-RPC response
            return JSONRPCResponse.success(request.id, response).to_json()
        
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}", exc_info=True)
            error = JSONRPCError.internal_error(str(e))
            return JSONRPCResponse.error_response(request.id, error).to_json()
    
    async def _handle_resources_list(self, request, session_id: str) -> str:
        """Handle resources/list request - return all resources from all servers"""
        from mcp.protocol import JSONRPCResponse
        
        all_resources = []
        for server_id, server in self.servers.items():
            resources = server.get_resources()
            for resource in resources:
                resource_with_server = resource.copy()
                resource_with_server["server_id"] = server_id
                all_resources.append(resource_with_server)
        
        return JSONRPCResponse.success(request.id, {"resources": all_resources}).to_json()
    
    async def _handle_resource_read(self, request, session_id: str) -> str:
        """Handle resources/read request - route to appropriate server"""
        from mcp.protocol import JSONRPCResponse, JSONRPCError
        
        params = request.params if isinstance(request.params, dict) else {}
        uri = params.get("uri")
        server_id = params.get("server_id")  # Optional: specific server
        
        if not uri:
            error = JSONRPCError.invalid_params("Missing 'uri' parameter")
            return JSONRPCResponse.error_response(request.id, error).to_json()
        
        # Find server with this resource
        target_server = None
        if server_id and server_id in self.servers:
            server = self.servers[server_id]
            if server.has_resource(uri):
                target_server = server
        else:
            # Search all servers
            for sid, server in self.servers.items():
                if server.has_resource(uri):
                    target_server = server
                    server_id = sid
                    break
        
        if not target_server:
            error = JSONRPCError.method_not_found(f"Resource '{uri}' not found")
            return JSONRPCResponse.error_response(request.id, error).to_json()
        
        # Read resource
        try:
            response = await target_server._handle_resources_read(params)
            return JSONRPCResponse.success(request.id, response).to_json()
        
        except Exception as e:
            logger.error(f"Error reading resource '{uri}': {e}", exc_info=True)
            error = JSONRPCError.internal_error(str(e))
            return JSONRPCResponse.error_response(request.id, error).to_json()
    
    async def _handle_prompts_list(self, request, session_id: str) -> str:
        """Handle prompts/list request - return all prompts from all servers"""
        from mcp.protocol import JSONRPCResponse
        
        all_prompts = []
        for server_id, server in self.servers.items():
            prompts = server.get_prompts()
            for prompt in prompts:
                prompt_with_server = prompt.copy()
                prompt_with_server["server_id"] = server_id
                all_prompts.append(prompt_with_server)
        
        return JSONRPCResponse.success(request.id, {"prompts": all_prompts}).to_json()
    
    async def _handle_prompt_get(self, request, session_id: str) -> str:
        """Handle prompts/get request - route to appropriate server"""
        from mcp.protocol import JSONRPCResponse, JSONRPCError
        
        params = request.params if isinstance(request.params, dict) else {}
        name = params.get("name")
        server_id = params.get("server_id")  # Optional: specific server
        
        if not name:
            error = JSONRPCError.invalid_params("Missing 'name' parameter")
            return JSONRPCResponse.error_response(request.id, error).to_json()
        
        # Find server with this prompt
        target_server = None
        if server_id and server_id in self.servers:
            server = self.servers[server_id]
            if server.has_prompt(name):
                target_server = server
        else:
            # Search all servers
            for sid, server in self.servers.items():
                if server.has_prompt(name):
                    target_server = server
                    server_id = sid
                    break
        
        if not target_server:
            error = JSONRPCError.method_not_found(f"Prompt '{name}' not found")
            return JSONRPCResponse.error_response(request.id, error).to_json()
        
        # Get prompt
        try:
            response = await target_server._handle_prompts_get(params)
            return JSONRPCResponse.success(request.id, response).to_json()
        
        except Exception as e:
            logger.error(f"Error getting prompt '{name}': {e}", exc_info=True)
            error = JSONRPCError.internal_error(str(e))
            return JSONRPCResponse.error_response(request.id, error).to_json()
    
    async def _handle_event(self, event: Event) -> None:
        """Handle events from event bus and broadcast to clients"""
        # Broadcast event to all connected clients
        await self._broadcast_event({
            "type": "event",
            "data": {
                "type": event.type.value,
                "source": event.source,
                "data": event.data,
                "timestamp": event.timestamp,
                "id": event.id,
            }
        })
    
    async def register_server(self, server_id: str, server: MCPServer) -> None:
        """
        Register an MCP server with the host
        
        Args:
            server_id: Server identifier
            server: MCP server instance
        """
        self.servers[server_id] = server
        
        # Create session for server
        session = ClientSession(client_id=server_id, client_type="server")
        import time
        session.connected_at = time.time()
        session.metadata["name"] = server.name if hasattr(server, 'name') else server_id
        self.sessions[server_id] = session
        
        logger.info(f"Server registered: {server_id}")
        
        # Publish event
        await self.event_bus.publish_event(
            EventType.STATE_CHANGED,
            source=self.name,
            data={
                "action": "server_registered",
                "server_id": server_id,
                "tools": server.get_tools(),
            },
        )
        
        # Broadcast event to all connected clients
        await self._broadcast_event({
            "type": "event",
            "data": {
                "type": "state_changed",
                "source": self.name,
                "data": {
                    "action": "server_registered",
                    "server_id": server_id,
                    "tools": server.get_tools(),
                }
            }
        })
    
    async def unregister_server(self, server_id: str) -> None:
        """
        Unregister an MCP server
        
        Args:
            server_id: Server identifier
        """
        if server_id in self.servers:
            del self.servers[server_id]
        
        if server_id in self.sessions:
            del self.sessions[server_id]
        
        logger.info(f"Server unregistered: {server_id}")
        
        # Publish event
        await self.event_bus.publish_event(
            EventType.STATE_CHANGED,
            source=self.name,
            data={
                "action": "server_unregistered",
                "server_id": server_id,
            },
        )
    
    async def register_client(self, client_id: str, client: MCPClient) -> None:
        """
        Register an MCP client with the host
        
        Args:
            client_id: Client identifier
            client: MCP client instance
        """
        self.clients[client_id] = client
        
        # Create session for client
        session = ClientSession(client_id=client_id, client_type="client")
        import time
        session.connected_at = time.time()
        self.sessions[client_id] = session
        
        logger.info(f"Client registered: {client_id}")
        
        # Publish event
        await self.event_bus.publish_event(
            EventType.STATE_CHANGED,
            source=self.name,
            data={
                "action": "client_registered",
                "client_id": client_id,
            },
        )
    
    async def disconnect_client(self, client_id: str) -> None:
        """Disconnect a client"""
        if client_id in self.clients:
            client = self.clients[client_id]
            await client.disconnect()
            del self.clients[client_id]
        
        if client_id in self.sessions:
            del self.sessions[client_id]
        
        logger.info(f"Client disconnected: {client_id}")
    
    def list_servers(self) -> List[str]:
        """List all registered servers"""
        return list(self.servers.keys())
    
    def list_clients(self) -> List[str]:
        """List all registered clients"""
        return list(self.clients.keys())
    
    def get_server(self, server_id: str) -> Optional[MCPServer]:
        """Get a server by ID"""
        return self.servers.get(server_id)
    
    def get_client(self, client_id: str) -> Optional[MCPClient]:
        """Get a client by ID"""
        return self.clients.get(client_id)
    
    def get_session(self, session_id: str) -> Optional[ClientSession]:
        """Get a session by ID"""
        return self.sessions.get(session_id)
    
    async def broadcast_event(self, event: Event) -> None:
        """Broadcast event to all subscribers"""
        await self.event_bus.publish(event)
    
    async def broadcast_message(self, message: str) -> None:
        """Broadcast message to all connected clients"""
        if self.ws_server:
            await self.ws_server.broadcast(message)
    
    async def _broadcast_event(self, event: Dict[str, Any]) -> None:
        """Broadcast event to all connected frontend clients"""
        message = json.dumps(event)
        await self.broadcast_message(message)

