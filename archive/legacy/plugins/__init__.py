"""
Plugin system for extending consciousness capabilities
"""

# Plugin discovery function
import os
from pathlib import Path

def discover_plugins():
    """Discover all available plugins"""
    plugins = {}
    plugin_dir = Path(__file__).parent
    
    for item in plugin_dir.iterdir():
        if item.is_dir() and item.name != '__pycache__':
            plugin_yaml = item / 'plugin.yaml'
            if plugin_yaml.exists():
                plugins[item.name] = {
                    'path': str(item),
                    'config': str(plugin_yaml)
                }
    
    return plugins

# Make plugins discoverable
available_plugins = discover_plugins()

__all__ = [
    'discover_plugins',
    'available_plugins'
]