"""
MCP Resources System

Resources are data sources that servers can expose to clients.
Examples: files, database schemas, API endpoints, etc.
"""

import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MCPResource:
    """
    MCP Resource Definition
    
    Represents a resource that can be accessed by MCP clients.
    """
    uri: str  # Resource URI/identifier
    name: str  # Resource name
    description: Optional[str] = None
    mimeType: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert resource to MCP resource definition dict"""
        result = {
            "uri": self.uri,
            "name": self.name,
        }
        if self.description:
            result["description"] = self.description
        if self.mimeType:
            result["mimeType"] = self.mimeType
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPResource":
        """Create resource from dict"""
        return cls(
            uri=data["uri"],
            name=data["name"],
            description=data.get("description"),
            mimeType=data.get("mimeType"),
        )


class ResourceRegistry:
    """
    Registry for MCP resources
    
    Manages resource registration and discovery.
    """
    
    def __init__(self):
        self.resources: Dict[str, MCPResource] = {}
        self.resource_handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        logger.debug("Resource registry initialized")
    
    def register(
        self,
        resource: MCPResource,
        handler: Optional[Callable[..., Awaitable[Any]]] = None
    ) -> None:
        """
        Register a resource
        
        Args:
            resource: Resource to register
            handler: Optional async handler function to retrieve resource content
        """
        if resource.uri in self.resources:
            logger.warning(f"Resource '{resource.uri}' already registered, overwriting")
        
        self.resources[resource.uri] = resource
        if handler:
            self.resource_handlers[resource.uri] = handler
        logger.debug(f"Registered resource: {resource.uri}")
    
    def unregister(self, uri: str) -> None:
        """
        Unregister a resource
        
        Args:
            uri: Resource URI
        """
        if uri in self.resources:
            del self.resources[uri]
        if uri in self.resource_handlers:
            del self.resource_handlers[uri]
        logger.debug(f"Unregistered resource: {uri}")
    
    def get_resource(self, uri: str) -> Optional[MCPResource]:
        """
        Get a resource by URI
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource or None if not found
        """
        return self.resources.get(uri)
    
    def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all registered resources
        
        Returns:
            List of resource definitions
        """
        return [resource.to_dict() for resource in self.resources.values()]
    
    def has_resource(self, uri: str) -> bool:
        """Check if resource exists"""
        return uri in self.resources
    
    async def read_resource(self, uri: str, **kwargs) -> Any:
        """
        Read resource content
        
        Args:
            uri: Resource URI
            **kwargs: Additional parameters for resource access
            
        Returns:
            Resource content
            
        Raises:
            KeyError: If resource not found
        """
        if uri not in self.resources:
            raise KeyError(f"Resource '{uri}' not found")
        
        if uri not in self.resource_handlers:
            raise ValueError(f"No handler for resource '{uri}'")
        
        handler = self.resource_handlers[uri]
        try:
            result = await handler(**kwargs)
            logger.debug(f"Resource '{uri}' read successfully")
            return result
        except Exception as e:
            logger.error(f"Error reading resource '{uri}': {e}", exc_info=True)
            raise



