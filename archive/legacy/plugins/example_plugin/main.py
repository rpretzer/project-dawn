"""
Example Plugin for Project Dawn
Shows the basic structure of a consciousness plugin
"""

import asyncio
import logging
from typing import Dict, Any, Callable
from core.plugin_system import PluginInterface

logger = logging.getLogger(__name__)

class ExamplePlugin(PluginInterface):
    """Example plugin implementation"""
    
    def __init__(self):
        self.consciousness = None
        self.config = {}
        self.counter = 0
        self.running = False
        
    async def initialize(self, consciousness: Any, config: Dict[str, Any]) -> None:
        """Initialize the plugin with consciousness reference and config"""
        self.consciousness = consciousness
        self.config = config
        logger.info(f"Example plugin initialized for {consciousness.id}")
        
    async def start(self) -> None:
        """Start the plugin's background tasks"""
        self.running = True
        # Start background task
        asyncio.create_task(self._background_loop())
        logger.info("Example plugin started")
        
    async def stop(self) -> None:
        """Stop the plugin"""
        self.running = False
        logger.info("Example plugin stopped")
        
    def get_capabilities(self) -> Dict[str, Callable]:
        """Return callable methods this plugin provides"""
        return {
            'example_action': self.example_action,
            'get_example_stats': self.get_example_stats
        }
        
    def get_handlers(self) -> Dict[str, Callable]:
        """Return message handlers this plugin provides"""
        return {
            'example_message': self.handle_example_message
        }
        
    async def _background_loop(self):
        """Example background task"""
        while self.running:
            try:
                # Do something periodically
                self.counter += 1
                
                # Interact with consciousness
                if hasattr(self.consciousness, 'memory'):
                    self.consciousness.memory.add_memory({
                        'type': 'plugin_event',
                        'plugin': 'example',
                        'counter': self.counter
                    })
                    
                await asyncio.sleep(60)  # Every minute
                
            except Exception as e:
                logger.error(f"Error in example plugin loop: {e}")
                
    async def example_action(self, param: str) -> Dict[str, Any]:
        """Example action that can be called"""
        logger.info(f"Example action called with param: {param}")
        
        # Do something with the consciousness
        result = {
            'success': True,
            'param': param,
            'consciousness_id': self.consciousness.id,
            'counter': self.counter
        }
        
        return result
        
    def get_example_stats(self) -> Dict[str, Any]:
        """Get plugin statistics"""
        return {
            'counter': self.counter,
            'running': self.running,
            'config': self.config
        }
        
    async def handle_example_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming message"""
        logger.info(f"Received example message: {message}")
        
        # Process message
        response = {
            'type': 'example_response',
            'received': message,
            'counter': self.counter
        }
        
        return response

# Plugin entry point
def create_plugin():
    """Factory function to create plugin instance"""
    return ExamplePlugin()