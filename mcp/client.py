"""
MCP Client Implementation

Client that connects to MCP servers and calls tools.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from .protocol import JSONRPCRequest, JSONRPCResponse
from .transport import WebSocketTransport

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP Client
    
    Connects to MCP servers and calls tools.
    """
    
    def __init__(self, name: str = "mcp-client"):
        """
        Initialize MCP client
        
        Args:
            name: Client name
        """
        self.name = name
        self.transport: Optional[WebSocketTransport] = None
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.resources: Dict[str, Dict[str, Any]] = {}
        self.prompts: Dict[str, Dict[str, Any]] = {}
        self._request_id = 0
        self._pending_requests: Dict[Any, asyncio.Future] = {}
        
        logger.info(f"MCP Client '{name}' initialized")
    
    async def connect(self, uri: str, **kwargs) -> None:
        """
        Connect to MCP server
        
        Args:
            uri: WebSocket URI
            **kwargs: Additional connection arguments
        """
        self.transport = WebSocketTransport(
            message_handler=self._handle_message,
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
            on_error=self._on_error,
        )
        
        # Start connection
        await self.transport.connect(uri, **kwargs)
    
    async def disconnect(self) -> None:
        """Disconnect from MCP server"""
        if self.transport:
            await self.transport.disconnect()
            self.transport = None
    
    @property
    def is_connected(self) -> bool:
        """Check if connected"""
        return self.transport is not None and self.transport.is_connected
    
    async def _on_connect(self) -> None:
        """Called when connected"""
        logger.info(f"Client '{self.name}' connected")
        # Discover tools on connection
        await self.discover_tools()
    
    async def _on_disconnect(self) -> None:
        """Called when disconnected"""
        logger.info(f"Client '{self.name}' disconnected")
        self.tools.clear()
        self.resources.clear()
        self.prompts.clear()
        # Cancel pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
    
    async def _on_error(self, error: Exception) -> None:
        """Called on error"""
        logger.error(f"Client '{self.name}' error: {error}")
    
    async def _handle_message(self, message: str) -> Optional[str]:
        """
        Handle incoming message
        
        Args:
            message: JSON-RPC message
            
        Returns:
            Response or None
        """
        try:
            response = JSONRPCResponse.from_json(message)
            
            # Find pending request
            if response.id in self._pending_requests:
                future = self._pending_requests.pop(response.id)
                if not future.done():
                    if response.error:
                        future.set_exception(Exception(f"{response.error.message}: {response.error.data}"))
                    else:
                        future.set_result(response.result)
            
            return None  # Client doesn't send response to server
        
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return None
    
    def _next_request_id(self) -> str:
        """Get next request ID"""
        self._request_id += 1
        return str(self._request_id)
    
    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Send JSON-RPC request and wait for response
        
        Args:
            method: Method name
            params: Parameters
            
        Returns:
            Response result
        """
        if not self.is_connected:
            raise RuntimeError("Not connected")
        
        request_id = self._next_request_id()
        request = JSONRPCRequest(method=method, params=params or {}, id=request_id)
        
        # Create future for response
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        try:
            # Send request
            await self.transport.send(request.to_json())
            
            # Wait for response (with timeout)
            try:
                result = await asyncio.wait_for(future, timeout=30.0)
                return result
            except asyncio.TimeoutError:
                self._pending_requests.pop(request_id, None)
                raise TimeoutError(f"Request '{method}' timed out")
        
        except Exception:
            self._pending_requests.pop(request_id, None)
            raise
    
    async def discover_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover available tools from server
        
        Returns:
            Dictionary mapping tool names to tool definitions
        """
        try:
            response = await self._send_request("tools/list")
            tools_list = response.get("tools", [])
            
            self.tools = {}
            for tool in tools_list:
                self.tools[tool["name"]] = tool
            
            logger.info(f"Client '{self.name}' discovered {len(self.tools)} tools")
            return self.tools
        
        except Exception as e:
            logger.error(f"Error discovering tools: {e}")
            return {}
    
    async def discover_resources(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover available resources from server
        
        Returns:
            Dictionary mapping resource URIs to resource definitions
        """
        try:
            response = await self._send_request("resources/list")
            resources_list = response.get("resources", [])
            
            self.resources = {}
            for resource in resources_list:
                self.resources[resource["uri"]] = resource
            
            logger.info(f"Client '{self.name}' discovered {len(self.resources)} resources")
            return self.resources
        
        except Exception as e:
            logger.error(f"Error discovering resources: {e}")
            return {}
    
    async def discover_prompts(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover available prompts from server
        
        Returns:
            Dictionary mapping prompt names to prompt definitions
        """
        try:
            response = await self._send_request("prompts/list")
            prompts_list = response.get("prompts", [])
            
            self.prompts = {}
            for prompt in prompts_list:
                self.prompts[prompt["name"]] = prompt
            
            logger.info(f"Client '{self.name}' discovered {len(self.prompts)} prompts")
            return self.prompts
        
        except Exception as e:
            logger.error(f"Error discovering prompts: {e}")
            return {}
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools
        
        Returns:
            List of tool definitions
        """
        return list(self.tools.values())
    
    def has_tool(self, name: str) -> bool:
        """Check if tool exists"""
        return name in self.tools
    
    def list_resources(self) -> List[Dict[str, Any]]:
        """
        List available resources
        
        Returns:
            List of resource definitions
        """
        return list(self.resources.values())
    
    def has_resource(self, uri: str) -> bool:
        """Check if resource exists"""
        return uri in self.resources
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """
        List available prompts
        
        Returns:
            List of prompt definitions
        """
        return list(self.prompts.values())
    
    def has_prompt(self, name: str) -> bool:
        """Check if prompt exists"""
        return name in self.prompts
    
    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """
        Call a tool on the server
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        if not self.is_connected:
            raise RuntimeError("Not connected")
        
        if not self.has_tool(name):
            # Try to discover tools first
            await self.discover_tools()
            if not self.has_tool(name):
                raise KeyError(f"Tool '{name}' not found")
        
        try:
            response = await self._send_request(
                "tools/call",
                params={
                    "name": name,
                    "arguments": arguments or {},
                }
            )
            
            # Handle tool response
            if response.get("isError", False):
                content = response.get("content", [])
                error_msg = ""
                for item in content:
                    if item.get("type") == "text":
                        error_msg = item.get("text", "")
                        break
                raise Exception(f"Tool '{name}' error: {error_msg}")
            
            # Extract result from content
            content = response.get("content", [])
            if content:
                for item in content:
                    if item.get("type") == "text":
                        return item.get("text", "")
            
            return response
        
        except Exception as e:
            logger.error(f"Error calling tool '{name}': {e}")
            raise
    
    async def read_resource(self, uri: str, **kwargs) -> Any:
        """
        Read a resource from the server
        
        Args:
            uri: Resource URI
            **kwargs: Additional parameters
            
        Returns:
            Resource content
        """
        if not self.is_connected:
            raise RuntimeError("Not connected")
        
        try:
            response = await self._send_request(
                "resources/read",
                params={
                    "uri": uri,
                    **kwargs
                }
            )
            
            if "error" in response:
                raise Exception(f"Resource error: {response['error']}")
            
            # Extract content from response
            contents = response.get("contents", [])
            if contents:
                return contents[0].get("text", "")
            
            return response
        
        except Exception as e:
            logger.error(f"Error reading resource '{uri}': {e}")
            raise
    
    async def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        """
        Get a prompt from the server
        
        Args:
            name: Prompt name
            arguments: Prompt arguments
            
        Returns:
            Rendered prompt text
        """
        if not self.is_connected:
            raise RuntimeError("Not connected")
        
        try:
            response = await self._send_request(
                "prompts/get",
                params={
                    "name": name,
                    "arguments": arguments or {},
                }
            )
            
            if "error" in response:
                raise Exception(f"Prompt error: {response['error']}")
            
            # Extract prompt text from messages
            messages = response.get("messages", [])
            if messages:
                content = messages[0].get("content", {})
                if isinstance(content, dict):
                    return content.get("text", "")
                return str(content)
            
            return response.get("description", "")
        
        except Exception as e:
            logger.error(f"Error getting prompt '{name}': {e}")
            raise

