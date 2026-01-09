"""
MCP Server Implementation

Server that exposes tools, resources, and prompts via MCP protocol.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable
from .protocol import JSONRPCHandler, JSONRPCRequest, JSONRPCResponse, JSONRPCError
from .tools import ToolRegistry, MCPTool
from .resources import ResourceRegistry, MCPResource
from .prompts import PromptRegistry, MCPPrompt

logger = logging.getLogger(__name__)


class MCPServer:
    """
    MCP Server
    
    Exposes tools, resources, and prompts to MCP clients via JSON-RPC 2.0.
    """
    
    def __init__(self, name: str = "mcp-server"):
        """
        Initialize MCP server
        
        Args:
            name: Server name
        """
        self.name = name
        self.handler = JSONRPCHandler()
        self.tool_registry = ToolRegistry()
        self.resource_registry = ResourceRegistry()
        self.prompt_registry = PromptRegistry()
        
        # Register MCP protocol methods
        self.handler.register_method("tools/list", self._handle_tools_list)
        self.handler.register_method("tools/call", self._handle_tools_call)
        self.handler.register_method("resources/list", self._handle_resources_list)
        self.handler.register_method("resources/read", self._handle_resources_read)
        self.handler.register_method("prompts/list", self._handle_prompts_list)
        self.handler.register_method("prompts/get", self._handle_prompts_get)
        
        logger.info(f"MCP Server '{name}' initialized")
    
    def register_tool(self, tool: MCPTool) -> None:
        """
        Register a tool
        
        Args:
            tool: Tool to register
        """
        self.tool_registry.register(tool)
        logger.debug(f"Server '{self.name}' registered tool: {tool.name}")
    
    def register_function(
        self,
        name: str,
        description: str,
        handler: Callable[..., Awaitable[Any]],
        inputSchema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a function as a tool
        
        Args:
            name: Tool name
            description: Tool description
            handler: Async handler function
            inputSchema: JSON Schema for input (optional)
        """
        self.tool_registry.register_function(name, description, handler, inputSchema)
    
    async def _handle_tools_list(self) -> Dict[str, Any]:
        """
        Handle tools/list request
        
        Returns:
            Tools list response
        """
        tools = self.tool_registry.list_tools()
        return {
            "tools": tools,
        }
    
    async def _handle_tools_call(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle tools/call request
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool call response
        """
        if not self.tool_registry.has_tool(name):
            raise KeyError(f"Tool '{name}' not found")
        
        try:
            # Call tool
            result = await self.tool_registry.call_tool(name, arguments)
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(result),
                    }
                ],
                "isError": False,
            }
        
        except Exception as e:
            logger.error(f"Error calling tool '{name}': {e}", exc_info=True)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {str(e)}",
                    }
                ],
                "isError": True,
            }
    
    async def handle_message(self, message: str) -> Optional[str]:
        """
        Handle incoming JSON-RPC message
        
        Args:
            message: JSON-RPC message as string
            
        Returns:
            Response message or None for notifications
        """
        try:
            response = await self.handler.handle_message_async(message)
            
            if response is None:
                # Notification (no response)
                return None
            
            if isinstance(response, list):
                # Batch response
                return JSONRPCResponse(id=None, result=[r.to_dict() for r in response]).to_json()
            
            # Single response
            return response.to_json()
        
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            # Return error response
            error = JSONRPCError.internal_error(str(e))
            return JSONRPCResponse(id=None, error=error).to_json()
    
    def register_resource(self, resource: MCPResource, handler: Optional[Callable] = None) -> None:
        """
        Register a resource
        
        Args:
            resource: Resource to register
            handler: Optional handler function to retrieve resource content
        """
        self.resource_registry.register(resource, handler)
    
    def register_prompt(self, prompt: MCPPrompt, handler: Optional[Callable] = None) -> None:
        """
        Register a prompt
        
        Args:
            prompt: Prompt to register
            handler: Optional handler function to generate prompt
        """
        self.prompt_registry.register(prompt, handler)
    
    async def _handle_resources_list(self) -> Dict[str, Any]:
        """
        Handle resources/list request
        
        Returns:
            Resources list response
        """
        resources = self.resource_registry.list_resources()
        return {
            "resources": resources,
        }
    
    async def _handle_resources_read(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle resources/read request
        
        Args:
            params: Parameters containing uri and optional kwargs
            
        Returns:
            Resource read response
        """
        if not params or "uri" not in params:
            return {
                "contents": [],
                "error": "Missing 'uri' parameter",
            }
        
        uri = params["uri"]
        kwargs = {k: v for k, v in params.items() if k != "uri"}
        
        try:
            content = await self.resource_registry.read_resource(uri, **kwargs)
            resource = self.resource_registry.get_resource(uri)
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": resource.mimeType if resource else "text/plain",
                        "text": str(content),
                    }
                ],
            }
        except KeyError:
            return {
                "contents": [],
                "error": f"Resource '{uri}' not found",
            }
        except Exception as e:
            logger.error(f"Error reading resource '{uri}': {e}", exc_info=True)
            return {
                "contents": [],
                "error": str(e),
            }
    
    async def _handle_prompts_list(self) -> Dict[str, Any]:
        """
        Handle prompts/list request
        
        Returns:
            Prompts list response
        """
        prompts = self.prompt_registry.list_prompts()
        return {
            "prompts": prompts,
        }
    
    async def _handle_prompts_get(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle prompts/get request
        
        Args:
            params: Parameters containing name and optional arguments
            
        Returns:
            Prompt get response
        """
        if not params or "name" not in params:
            return {
                "error": "Missing 'name' parameter",
            }
        
        name = params["name"]
        arguments = params.get("arguments", {})
        
        try:
            prompt_text = await self.prompt_registry.get_prompt_text(name, arguments)
            prompt = self.prompt_registry.get_prompt(name)
            return {
                "description": prompt.description if prompt else "",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": prompt_text,
                        }
                    }
                ],
            }
        except KeyError:
            return {
                "error": f"Prompt '{name}' not found",
            }
        except Exception as e:
            logger.error(f"Error getting prompt '{name}': {e}", exc_info=True)
            return {
                "error": str(e),
            }
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of all tools"""
        return self.tool_registry.list_tools()
    
    def has_tool(self, name: str) -> bool:
        """Check if tool exists"""
        return self.tool_registry.has_tool(name)
    
    def get_resources(self) -> List[Dict[str, Any]]:
        """Get list of all resources"""
        return self.resource_registry.list_resources()
    
    def has_resource(self, uri: str) -> bool:
        """Check if resource exists"""
        return self.resource_registry.has_resource(uri)
    
    def get_prompts(self) -> List[Dict[str, Any]]:
        """Get list of all prompts"""
        return self.prompt_registry.list_prompts()
    
    def has_prompt(self, name: str) -> bool:
        """Check if prompt exists"""
        return self.prompt_registry.has_prompt(name)

