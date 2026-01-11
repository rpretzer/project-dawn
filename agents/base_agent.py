"""
Base Agent Class

Base class for all MCP agents.
"""

import logging
from typing import Any, Dict, Optional
from mcp.server import MCPServer

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base Agent Class
    
    All agents inherit from this class. Agents are MCP servers
    that expose tools, resources, and prompts.
    """
    
    def __init__(self, agent_id: str, name: Optional[str] = None):
        """
        Initialize agent
        
        Args:
            agent_id: Unique agent identifier
            name: Agent name (defaults to agent_id)
        """
        self.agent_id = agent_id
        self.name = name or agent_id
        
        # Create MCP server for this agent
        self.server = MCPServer(name=self.name)
        
        # Agent state
        self.state: Dict[str, Any] = {}
        
        logger.info(f"Agent '{self.name}' ({self.agent_id}) initialized")
    
    def register_tool(self, tool_name: str, description: str, handler, inputSchema: Optional[Dict[str, Any]] = None):
        """
        Register a tool with the agent's MCP server
        
        Args:
            tool_name: Tool name
            description: Tool description
            handler: Async handler function
            inputSchema: JSON Schema for input (optional)
        """
        self.server.register_function(tool_name, description, handler, inputSchema)
        logger.debug(f"Agent '{self.name}' registered tool: {tool_name}")
    
    def get_tools(self) -> list:
        """Get list of all tools exposed by this agent"""
        return self.server.get_tools()
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if agent has a tool"""
        return self.server.has_tool(tool_name)
    
    def get_state(self) -> Dict[str, Any]:
        """Get agent state"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "tools": self.get_tools(),
            "state": self.state,
        }
    
    async def initialize(self) -> None:
        """
        Initialize agent (override in subclasses)
        
        This method is called automatically by `start()`. Override this method
        in subclasses to perform agent-specific initialization, such as:
        - Loading configuration or state
        - Registering tools, resources, or prompts
        - Setting up connections or dependencies
        - Pre-computing values or indices
        
        The default implementation does nothing and should be overridden by subclasses
        that need initialization logic. This follows the template method pattern.
        
        Example:
            async def initialize(self) -> None:
                await self.load_config()
                self.register_tool("my_tool", "Description", self._my_tool_handler)
        """
        # Default implementation: no-op
        # Subclasses should override this method for agent-specific initialization
        pass
    
    async def start(self) -> None:
        """Start agent (override in subclasses)"""
        await self.initialize()
        logger.info(f"Agent '{self.name}' started")
    
    async def stop(self) -> None:
        """Stop agent (override in subclasses)"""
        logger.info(f"Agent '{self.name}' stopped")



