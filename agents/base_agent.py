"""
Base Agent Class

Base class for all MCP agents.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from mcp.server import MCPServer
from data_paths import data_root

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base Agent Class
    
    All agents inherit from this class. Agents are MCP servers
    that expose tools, resources, and prompts.
    """
    
    def __init__(self, agent_id: str, name: Optional[str] = None, 
                 data_dir: Optional[Path] = None, persist_state: bool = True):
        """
        Initialize agent
        
        Args:
            agent_id: Unique agent identifier
            name: Agent name (defaults to agent_id)
            data_dir: Data directory for state persistence (defaults to data_root/agents/{agent_id})
            persist_state: Enable state persistence (default True)
        """
        self.agent_id = agent_id
        self.name = name or agent_id
        
        # Create MCP server for this agent
        self.server = MCPServer(name=self.name)
        
        # Agent state
        self.state: Dict[str, Any] = {}
        
        # State persistence
        self.persist_state = persist_state
        self.data_dir = data_dir or data_root() / "agents" / agent_id
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.data_dir / "state.json"
        
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
        
        The default implementation loads persisted state if persistence is enabled.
        Subclasses should override this method for agent-specific initialization.
        This follows the template method pattern.
        
        Example:
            async def initialize(self) -> None:
                await super().initialize()  # Load persisted state
                await self.load_config()
                self.register_tool("my_tool", "Description", self._my_tool_handler)
        """
        # Load persisted state
        if self.persist_state:
            self._load_state()
    
    def _load_state(self) -> None:
        """Load agent state from disk (override in subclasses for custom state)"""
        if not self.state_path.exists():
            return
        
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.state = data.get("state", {})
            logger.debug(f"Loaded state for agent '{self.name}'")
        except Exception as e:
            logger.warning(f"Failed to load state for agent '{self.name}': {e}")
    
    def _save_state(self) -> None:
        """Save agent state to disk (override in subclasses for custom state)"""
        if not self.persist_state:
            return
        
        try:
            data = {
                "agent_id": self.agent_id,
                "name": self.name,
                "state": self.state,
            }
            tmp_path = self.state_path.with_suffix(".json.tmp")
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp_path.replace(self.state_path)
            logger.debug(f"Saved state for agent '{self.name}'")
        except Exception as e:
            logger.error(f"Failed to save state for agent '{self.name}': {e}")
    
    def save_state(self) -> None:
        """
        Save agent state (call this after state changes)
        
        Override _save_state() in subclasses for custom state persistence.
        """
        self._save_state()
    
    async def start(self) -> None:
        """Start agent (override in subclasses)"""
        await self.initialize()
        logger.info(f"Agent '{self.name}' started")
    
    async def stop(self) -> None:
        """Stop agent (override in subclasses)"""
        # Save state before stopping
        if self.persist_state:
            self._save_state()
        logger.info(f"Agent '{self.name}' stopped")



