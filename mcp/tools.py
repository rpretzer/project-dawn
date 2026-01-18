"""
MCP Tool System

Tool definition, registration, and execution for MCP protocol.
"""

import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """
    MCP Tool Definition
    
    Represents a tool that can be called by MCP clients.
    """
    name: str
    description: str
    inputSchema: Dict[str, Any]  # JSON Schema
    handler: Callable[..., Awaitable[Any]]  # Async handler function
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to MCP tool definition dict"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], handler: Callable[..., Awaitable[Any]]) -> "MCPTool":
        """Create tool from dict"""
        return cls(
            name=data["name"],
            description=data["description"],
            inputSchema=data.get("inputSchema", {}),
            handler=handler,
        )


class ToolRegistry:
    """
    Registry for MCP tools
    
    Manages tool registration and discovery.
    """
    
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        logger.debug("Tool registry initialized")
    
    def register(self, tool: MCPTool) -> None:
        """
        Register a tool
        
        Args:
            tool: Tool to register
        """
        if tool.name in self.tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")
        
        self.tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
    
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
        if inputSchema is None:
            # Generate basic schema from function signature
            inputSchema = {"type": "object", "properties": {}}
        
        tool = MCPTool(
            name=name,
            description=description,
            inputSchema=inputSchema,
            handler=handler,
        )
        self.register(tool)
    
    def unregister(self, name: str) -> None:
        """
        Unregister a tool
        
        Args:
            name: Tool name
        """
        if name in self.tools:
            del self.tools[name]
            logger.debug(f"Unregistered tool: {name}")
        else:
            logger.warning(f"Tool '{name}' not found")
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """
        Get a tool by name
        
        Args:
            name: Tool name
            
        Returns:
            Tool or None if not found
        """
        return self.tools.get(name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all registered tools
        
        Returns:
            List of tool definitions
        """
        return [tool.to_dict() for tool in self.tools.values()]
    
    def has_tool(self, name: str) -> bool:
        """Check if tool exists"""
        return name in self.tools
    
    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """
        Call a tool
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool result
            
        Raises:
            KeyError: If tool not found
        """
        tool = self.get_tool(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found")
        
        arguments = arguments or {}
        
        try:
            # Call handler with arguments
            if isinstance(arguments, dict):
                result = await tool.handler(**arguments)
            elif isinstance(arguments, list):
                result = await tool.handler(*arguments)
            else:
                result = await tool.handler()
            
            logger.debug(f"Tool '{name}' executed successfully")
            return result
        
        except Exception as e:
            logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
            raise



