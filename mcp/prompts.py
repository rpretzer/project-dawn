"""
MCP Prompts System

Prompts are reusable prompt templates and workflows that servers can expose.
"""

import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MCPPromptArgument:
    """Prompt argument definition"""
    name: str
    description: Optional[str] = None
    required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        result = {
            "name": self.name,
            "required": self.required,
        }
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class MCPPrompt:
    """
    MCP Prompt Definition
    
    Represents a reusable prompt template.
    """
    name: str
    description: Optional[str] = None
    arguments: List[MCPPromptArgument] = field(default_factory=list)
    template: Optional[str] = None  # Prompt template text
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert prompt to MCP prompt definition dict"""
        result = {
            "name": self.name,
        }
        if self.description:
            result["description"] = self.description
        if self.arguments:
            result["arguments"] = [arg.to_dict() for arg in self.arguments]
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPPrompt":
        """Create prompt from dict"""
        args = []
        for arg_data in data.get("arguments", []):
            args.append(MCPPromptArgument(
                name=arg_data["name"],
                description=arg_data.get("description"),
                required=arg_data.get("required", False),
            ))
        return cls(
            name=data["name"],
            description=data.get("description"),
            arguments=args,
            template=data.get("template"),
        )
    
    def render(self, arguments: Optional[Dict[str, Any]] = None) -> str:
        """
        Render prompt with arguments
        
        Args:
            arguments: Arguments to substitute in template
            
        Returns:
            Rendered prompt text
        """
        if not self.template:
            return self.name
        
        arguments = arguments or {}
        template = self.template
        
        # Simple template substitution: {{variable_name}}
        for key, value in arguments.items():
            placeholder = "{{" + key + "}}"
            template = template.replace(placeholder, str(value))
        
        return template


class PromptRegistry:
    """
    Registry for MCP prompts
    
    Manages prompt registration and discovery.
    """
    
    def __init__(self):
        self.prompts: Dict[str, MCPPrompt] = {}
        self.prompt_handlers: Dict[str, Callable[..., Awaitable[str]]] = {}
        logger.debug("Prompt registry initialized")
    
    def register(
        self,
        prompt: MCPPrompt,
        handler: Optional[Callable[..., Awaitable[str]]] = None
    ) -> None:
        """
        Register a prompt
        
        Args:
            prompt: Prompt to register
            handler: Optional async handler function to generate prompt
        """
        if prompt.name in self.prompts:
            logger.warning(f"Prompt '{prompt.name}' already registered, overwriting")
        
        self.prompts[prompt.name] = prompt
        if handler:
            self.prompt_handlers[prompt.name] = handler
        logger.debug(f"Registered prompt: {prompt.name}")
    
    def unregister(self, name: str) -> None:
        """
        Unregister a prompt
        
        Args:
            name: Prompt name
        """
        if name in self.prompts:
            del self.prompts[name]
        if name in self.prompt_handlers:
            del self.prompt_handlers[name]
        logger.debug(f"Unregistered prompt: {name}")
    
    def get_prompt(self, name: str) -> Optional[MCPPrompt]:
        """
        Get a prompt by name
        
        Args:
            name: Prompt name
            
        Returns:
            Prompt or None if not found
        """
        return self.prompts.get(name)
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """
        List all registered prompts
        
        Returns:
            List of prompt definitions
        """
        return [prompt.to_dict() for prompt in self.prompts.values()]
    
    def has_prompt(self, name: str) -> bool:
        """Check if prompt exists"""
        return name in self.prompts
    
    async def get_prompt_text(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get rendered prompt text
        
        Args:
            name: Prompt name
            arguments: Arguments for prompt
            
        Returns:
            Rendered prompt text
            
        Raises:
            KeyError: If prompt not found
        """
        prompt = self.get_prompt(name)
        if prompt is None:
            raise KeyError(f"Prompt '{name}' not found")
        
        # Use handler if available, otherwise render template
        if name in self.prompt_handlers:
            handler = self.prompt_handlers[name]
            try:
                result = await handler(**(arguments or {}))
                logger.debug(f"Prompt '{name}' generated via handler")
                return result
            except Exception as e:
                logger.error(f"Error generating prompt '{name}': {e}", exc_info=True)
                raise
        else:
            # Render template
            return prompt.render(arguments or {})

