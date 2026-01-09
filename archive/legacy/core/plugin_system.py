"""
Plugin System for Consciousness
Production-ready plugin architecture for extending consciousness capabilities
Supports hot-loading, dependency management, and sandboxed execution
"""

import asyncio
import importlib
import importlib.util
import inspect
import json
import logging
import os
import sys
import yaml
from typing import Dict, List, Optional, Any, Callable, Set, Type
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from abc import ABC, abstractmethod
import hashlib
import traceback
from enum import Enum
import aiofiles
import watchdog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

class PluginState(Enum):
    """Plugin lifecycle states"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"

class PluginPriority(Enum):
    """Plugin execution priority"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3

@dataclass
class PluginMetadata:
    """Plugin metadata from plugin.yaml"""
    name: str
    version: str
    author: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    required_systems: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    priority: PluginPriority = PluginPriority.NORMAL
    auto_enable: bool = True
    sandbox: bool = True
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> 'PluginMetadata':
        """Load metadata from plugin.yaml"""
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
            
        # Convert priority string to enum
        priority_str = data.get('priority', 'normal').upper()
        priority = PluginPriority[priority_str] if priority_str in PluginPriority.__members__ else PluginPriority.NORMAL
        
        return cls(
            name=data['name'],
            version=data['version'],
            author=data['author'],
            description=data['description'],
            dependencies=data.get('dependencies', []),
            required_systems=data.get('required_systems', []),
            config_schema=data.get('config_schema', {}),
            priority=priority,
            auto_enable=data.get('auto_enable', True),
            sandbox=data.get('sandbox', True)
        )

@dataclass
class PluginInstance:
    """Runtime plugin instance"""
    metadata: PluginMetadata
    module: Any
    instance: 'PluginInterface'
    state: PluginState
    config: Dict[str, Any]
    load_time: datetime
    error_count: int = 0
    last_error: Optional[str] = None
    capabilities: Dict[str, Callable] = field(default_factory=dict)
    handlers: Dict[str, Callable] = field(default_factory=dict)
    
class PluginInterface(ABC):
    """Base interface all plugins must implement"""
    
    @abstractmethod
    async def initialize(self, consciousness: Any, config: Dict[str, Any]) -> None:
        """Initialize the plugin with consciousness reference and config"""
        pass
        
    @abstractmethod
    async def start(self) -> None:
        """Start plugin operations"""
        pass
        
    @abstractmethod
    async def stop(self) -> None:
        """Stop plugin operations"""
        pass
        
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Callable]:
        """Return plugin capabilities as name->function mapping"""
        pass
        
    @abstractmethod
    def get_handlers(self) -> Dict[str, Callable]:
        """Return event handlers as event_type->handler mapping"""
        pass
        
    def get_status(self) -> Dict[str, Any]:
        """Get plugin status (optional override)"""
        return {"status": "active"}

class PluginSandbox:
    """Sandbox environment for plugin execution"""
    
    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self.allowed_modules = {
            'asyncio', 'json', 'datetime', 'logging', 'typing',
            'dataclasses', 'enum', 'pathlib', 'os', 'sys',
            'aiohttp', 'numpy', 'pandas'  # Add allowed third-party modules
        }
        self.blocked_functions = {
            'eval', 'exec', 'compile', '__import__',
            'open', 'file', 'input', 'raw_input'
        }
        
    def create_restricted_globals(self) -> Dict[str, Any]:
        """Create restricted global namespace for plugin"""
        # Start with safe builtins
        safe_builtins = {}
        for name in dir(__builtins__):
            if name not in self.blocked_functions:
                safe_builtins[name] = getattr(__builtins__, name)
                
        # Create restricted globals
        restricted_globals = {
            '__builtins__': safe_builtins,
            '__name__': f'plugin_{self.plugin_name}',
            '__doc__': None,
            # Add safe imports
            'asyncio': asyncio,
            'json': json,
            'logging': logging.getLogger(f'plugin.{self.plugin_name}')
        }
        
        return restricted_globals
        
    async def execute_sandboxed(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function in sandboxed environment"""
        try:
            # For async functions
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Sandboxed execution error in {self.plugin_name}: {e}")
            raise

class PluginLoader:
    """Handles plugin discovery and loading"""
    
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.plugins_dir.mkdir(exist_ok=True)
        
    async def discover_plugins(self) -> List[Tuple[Path, PluginMetadata]]:
        """Discover all available plugins"""
        plugins = []
        
        for entry in self.plugins_dir.iterdir():
            if entry.is_dir() and (entry / 'plugin.yaml').exists():
                try:
                    metadata = PluginMetadata.from_yaml(entry / 'plugin.yaml')
                    plugins.append((entry, metadata))
                except Exception as e:
                    logger.error(f"Error loading plugin metadata from {entry}: {e}")
                    
        # Sort by priority
        plugins.sort(key=lambda x: x[1].priority.value)
        return plugins
        
    async def load_plugin(self, plugin_path: Path, metadata: PluginMetadata) -> Any:
        """Load a plugin module"""
        main_file = plugin_path / 'main.py'
        if not main_file.exists():
            raise FileNotFoundError(f"Plugin main.py not found at {main_file}")
            
        # Create module spec
        spec = importlib.util.spec_from_file_location(
            f"plugins.{metadata.name}",
            main_file
        )
        
        if not spec or not spec.loader:
            raise ImportError(f"Failed to create module spec for {metadata.name}")
            
        # Load module
        module = importlib.util.module_from_spec(spec)
        
        # Add to sys.modules
        sys.modules[spec.name] = module
        
        # Execute module
        spec.loader.exec_module(module)
        
        return module
        
    def find_plugin_class(self, module: Any) -> Optional[Type[PluginInterface]]:
        """Find the main plugin class in module"""
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, PluginInterface) and 
                obj != PluginInterface):
                return obj
        return None

class PluginManager:
    """Main plugin management system"""
    
    def __init__(self, consciousness_id: str, plugins_dir: Optional[Path] = None):
        self.consciousness_id = consciousness_id
        self.plugins_dir = plugins_dir or Path('plugins')
        self.consciousness = None  # Set during initialization
        
        # Plugin storage
        self.plugins: Dict[str, PluginInstance] = {}
        self.capabilities: Dict[str, List[Tuple[str, Callable]]] = {}  # capability -> [(plugin, func)]
        self.handlers: Dict[str, List[Tuple[str, Callable]]] = {}  # event -> [(plugin, handler)]
        
        # Plugin loader
        self.loader = PluginLoader(self.plugins_dir)
        
        # File watcher for hot reload
        self.watcher: Optional[Observer] = None
        self.watch_enabled = False
        
        # Dependency graph
        self.dependency_graph: Dict[str, Set[str]] = {}
        
        # Performance tracking
        self.execution_stats: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"Plugin manager initialized for {consciousness_id}")
        
    async def initialize(self, consciousness: Any) -> None:
        """Initialize plugin manager with consciousness reference"""
        self.consciousness = consciousness
        
        # Load all plugins
        await self.load_all_plugins()
        
        # Start file watcher if enabled
        if self.watch_enabled:
            self._start_file_watcher()
            
    async def load_all_plugins(self) -> None:
        """Load all discovered plugins"""
        plugins = await self.loader.discover_plugins()
        
        for plugin_path, metadata in plugins:
            if metadata.auto_enable:
                try:
                    await self.load_plugin(plugin_path, metadata)
                except Exception as e:
                    logger.error(f"Failed to load plugin {metadata.name}: {e}")
                    
    async def load_plugin(self, plugin_path: Path, metadata: Optional[PluginMetadata] = None) -> bool:
        """Load a single plugin"""
        try:
            # Load metadata if not provided
            if not metadata:
                metadata = PluginMetadata.from_yaml(plugin_path / 'plugin.yaml')
                
            # Check if already loaded
            if metadata.name in self.plugins:
                logger.warning(f"Plugin {metadata.name} already loaded")
                return False
                
            # Check dependencies
            if not self._check_dependencies(metadata):
                logger.error(f"Plugin {metadata.name} has unmet dependencies")
                return False
                
            # Check required systems
            if not self._check_required_systems(metadata):
                logger.error(f"Plugin {metadata.name} requires unavailable systems")
                return False
                
            # Load module
            module = await self.loader.load_plugin(plugin_path, metadata)
            
            # Find plugin class
            plugin_class = self.loader.find_plugin_class(module)
            if not plugin_class:
                raise ValueError(f"No PluginInterface implementation found in {metadata.name}")
                
            # Create instance
            instance = plugin_class()
            
            # Load config
            config = self._load_plugin_config(metadata)
            
            # Create plugin instance record
            plugin = PluginInstance(
                metadata=metadata,
                module=module,
                instance=instance,
                state=PluginState.LOADING,
                config=config,
                load_time=datetime.utcnow()
            )
            
            # Initialize plugin
            await instance.initialize(self.consciousness, config)
            
            # Get capabilities and handlers
            plugin.capabilities = instance.get_capabilities()
            plugin.handlers = instance.get_handlers()
            
            # Register capabilities
            for cap_name, cap_func in plugin.capabilities.items():
                if cap_name not in self.capabilities:
                    self.capabilities[cap_name] = []
                self.capabilities[cap_name].append((metadata.name, cap_func))
                
            # Register handlers
            for event_type, handler in plugin.handlers.items():
                if event_type not in self.handlers:
                    self.handlers[event_type] = []
                self.handlers[event_type].append((metadata.name, handler))
                
            # Start plugin
            await instance.start()
            
            # Update state
            plugin.state = PluginState.ACTIVE
            self.plugins[metadata.name] = plugin
            
            # Update dependency graph
            self._update_dependency_graph(metadata)
            
            logger.info(f"Successfully loaded plugin {metadata.name} v{metadata.version}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading plugin {metadata.name if metadata else 'unknown'}: {e}")
            logger.error(traceback.format_exc())
            
            # Record error if plugin partially loaded
            if metadata and metadata.name in self.plugins:
                plugin = self.plugins[metadata.name]
                plugin.state = PluginState.ERROR
                plugin.error_count += 1
                plugin.last_error = str(e)
                
            return False
            
    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin"""
        if plugin_name not in self.plugins:
            logger.warning(f"Plugin {plugin_name} not loaded")
            return False
            
        plugin = self.plugins[plugin_name]
        
        try:
            # Stop plugin
            if plugin.state == PluginState.ACTIVE:
                await plugin.instance.stop()
                
            # Remove capabilities
            for cap_name in plugin.capabilities:
                if cap_name in self.capabilities:
                    self.capabilities[cap_name] = [
                        (name, func) for name, func in self.capabilities[cap_name]
                        if name != plugin_name
                    ]
                    if not self.capabilities[cap_name]:
                        del self.capabilities[cap_name]
                        
            # Remove handlers
            for event_type in plugin.handlers:
                if event_type in self.handlers:
                    self.handlers[event_type] = [
                        (name, handler) for name, handler in self.handlers[event_type]
                        if name != plugin_name
                    ]
                    if not self.handlers[event_type]:
                        del self.handlers[event_type]
                        
            # Remove from sys.modules
            module_name = f"plugins.{plugin_name}"
            if module_name in sys.modules:
                del sys.modules[module_name]
                
            # Remove from plugins
            del self.plugins[plugin_name]
            
            # Update dependency graph
            self._update_dependency_graph()
            
            logger.info(f"Successfully unloaded plugin {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_name}: {e}")
            return False
            
    async def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a plugin (unload and load again)"""
        if plugin_name not in self.plugins:
            logger.warning(f"Plugin {plugin_name} not loaded")
            return False
            
        # Get plugin path
        plugin_path = self.plugins_dir / plugin_name
        
        # Unload
        if not await self.unload_plugin(plugin_name):
            return False
            
        # Load again
        return await self.load_plugin(plugin_path)
        
    async def execute_capability(self, capability: str, *args, **kwargs) -> List[Any]:
        """Execute a capability across all plugins that provide it"""
        if capability not in self.capabilities:
            logger.warning(f"No plugins provide capability: {capability}")
            return []
            
        results = []
        
        for plugin_name, func in self.capabilities[capability]:
            if self.plugins[plugin_name].state != PluginState.ACTIVE:
                continue
                
            try:
                # Track execution time
                start_time = asyncio.get_event_loop().time()
                
                # Execute based on sandbox setting
                plugin = self.plugins[plugin_name]
                if plugin.metadata.sandbox:
                    sandbox = PluginSandbox(plugin_name)
                    result = await sandbox.execute_sandboxed(func, *args, **kwargs)
                else:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                        
                results.append(result)
                
                # Update stats
                self._update_execution_stats(
                    plugin_name,
                    capability,
                    asyncio.get_event_loop().time() - start_time
                )
                
            except Exception as e:
                logger.error(f"Error executing capability {capability} in plugin {plugin_name}: {e}")
                plugin = self.plugins[plugin_name]
                plugin.error_count += 1
                plugin.last_error = str(e)
                
        return results
        
    async def emit_event(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Emit an event to all registered handlers"""
        if event_type not in self.handlers:
            return {}
            
        responses = {}
        
        # Sort handlers by plugin priority
        sorted_handlers = sorted(
            self.handlers[event_type],
            key=lambda x: self.plugins[x[0]].metadata.priority.value
        )
        
        for plugin_name, handler in sorted_handlers:
            if self.plugins[plugin_name].state != PluginState.ACTIVE:
                continue
                
            try:
                # Execute handler
                plugin = self.plugins[plugin_name]
                if plugin.metadata.sandbox:
                    sandbox = PluginSandbox(plugin_name)
                    response = await sandbox.execute_sandboxed(handler, data)
                else:
                    if asyncio.iscoroutinefunction(handler):
                        response = await handler(data)
                    else:
                        response = handler(data)
                        
                responses[plugin_name] = response
                
            except Exception as e:
                logger.error(f"Error handling event {event_type} in plugin {plugin_name}: {e}")
                plugin = self.plugins[plugin_name]
                plugin.error_count += 1
                plugin.last_error = str(e)
                
        return responses
        
    def get_plugin_status(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific plugin"""
        if plugin_name not in self.plugins:
            return None
            
        plugin = self.plugins[plugin_name]
        
        status = {
            'name': plugin.metadata.name,
            'version': plugin.metadata.version,
            'state': plugin.state.value,
            'load_time': plugin.load_time.isoformat(),
            'error_count': plugin.error_count,
            'last_error': plugin.last_error,
            'capabilities': list(plugin.capabilities.keys()),
            'handlers': list(plugin.handlers.keys())
        }
        
        # Get plugin-specific status
        try:
            plugin_status = plugin.instance.get_status()
            status.update(plugin_status)
        except Exception as e:
            logger.error(f"Error getting status from plugin {plugin_name}: {e}")
            
        return status
        
    def get_all_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all plugins"""
        return {
            name: self.get_plugin_status(name)
            for name in self.plugins
        }
        
    def _check_dependencies(self, metadata: PluginMetadata) -> bool:
        """Check if plugin dependencies are met"""
        for dep in metadata.dependencies:
            try:
                importlib.import_module(dep)
            except ImportError:
                logger.error(f"Missing dependency for {metadata.name}: {dep}")
                return False
        return True
        
    def _check_required_systems(self, metadata: PluginMetadata) -> bool:
        """Check if required consciousness systems are available"""
        if not self.consciousness:
            return True  # Can't check yet
            
        for system in metadata.required_systems:
            if not hasattr(self.consciousness, system):
                logger.error(f"Missing required system for {metadata.name}: {system}")
                return False
        return True
        
    def _load_plugin_config(self, metadata: PluginMetadata) -> Dict[str, Any]:
        """Load plugin configuration"""
        # Start with defaults from schema
        config = {}
        for key, schema in metadata.config_schema.items():
            config[key] = schema.get('default')
            
        # Override with environment variables
        env_prefix = f"PLUGIN_{metadata.name.upper()}_"
        for key in config:
            env_key = env_prefix + key.upper()
            if env_key in os.environ:
                # Type conversion based on schema
                schema = metadata.config_schema.get(key, {})
                value = os.environ[env_key]
                
                if schema.get('type') == 'boolean':
                    config[key] = value.lower() in ('true', '1', 'yes')
                elif schema.get('type') == 'integer':
                    config[key] = int(value)
                elif schema.get('type') == 'float':
                    config[key] = float(value)
                elif schema.get('type') == 'list':
                    config[key] = value.split(',')
                else:
                    config[key] = value
                    
        # Load from config file if exists
        config_file = self.plugins_dir / metadata.name / 'config.json'
        if config_file.exists():
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
                
        return config
        
    def _update_dependency_graph(self, metadata: Optional[PluginMetadata] = None):
        """Update plugin dependency graph"""
        if metadata:
            # Add new plugin to graph
            self.dependency_graph[metadata.name] = set(metadata.dependencies)
        else:
            # Rebuild entire graph
            self.dependency_graph.clear()
            for plugin in self.plugins.values():
                self.dependency_graph[plugin.metadata.name] = set(plugin.metadata.dependencies)
                
    def _update_execution_stats(self, plugin_name: str, capability: str, execution_time: float):
        """Update plugin execution statistics"""
        if plugin_name not in self.execution_stats:
            self.execution_stats[plugin_name] = {}
            
        if capability not in self.execution_stats[plugin_name]:
            self.execution_stats[plugin_name][capability] = {
                'count': 0,
                'total_time': 0,
                'avg_time': 0,
                'max_time': 0
            }
            
        stats = self.execution_stats[plugin_name][capability]
        stats['count'] += 1
        stats['total_time'] += execution_time
        stats['avg_time'] = stats['total_time'] / stats['count']
        stats['max_time'] = max(stats['max_time'], execution_time)
        
    def _start_file_watcher(self):
        """Start watching plugin directory for changes"""
        class PluginFileHandler(FileSystemEventHandler):
            def __init__(self, manager: PluginManager):
                self.manager = manager
                
            def on_modified(self, event):
                if event.is_directory:
                    return
                    
                # Check if it's a plugin file
                path = Path(event.src_path)
                if path.suffix in ['.py', '.yaml'] and path.parts[-3] == 'plugins':
                    plugin_name = path.parts[-2]
                    logger.info(f"Detected change in plugin {plugin_name}")
                    
                    # Schedule reload
                    asyncio.create_task(self.manager.reload_plugin(plugin_name))
                    
        self.watcher = Observer()
        self.watcher.schedule(
            PluginFileHandler(self),
            str(self.plugins_dir),
            recursive=True
        )
        self.watcher.start()
        logger.info("Plugin file watcher started")
        
    async def shutdown(self):
        """Shutdown plugin manager"""
        # Stop file watcher
        if self.watcher:
            self.watcher.stop()
            self.watcher.join()
            
        # Stop all plugins
        for plugin_name in list(self.plugins.keys()):
            await self.unload_plugin(plugin_name)
            
        logger.info("Plugin manager shutdown complete")
        
    def get_capability_providers(self, capability: str) -> List[str]:
        """Get list of plugins providing a capability"""
        if capability not in self.capabilities:
            return []
        return [name for name, _ in self.capabilities[capability]]
        
    def get_event_listeners(self, event_type: str) -> List[str]:
        """Get list of plugins listening to an event"""
        if event_type not in self.handlers:
            return []
        return [name for name, _ in self.handlers[event_type]]
        
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get plugin execution statistics"""
        return {
            'plugins': self.execution_stats,
            'total_capabilities': len(self.capabilities),
            'total_handlers': len(self.handlers),
            'active_plugins': sum(1 for p in self.plugins.values() if p.state == PluginState.ACTIVE)
        }

# Consciousness integration helper
async def integrate_plugin_system(consciousness):
    """Integrate plugin system with consciousness"""
    plugin_manager = PluginManager(consciousness.id)
    
    # Initialize with consciousness
    await plugin_manager.initialize(consciousness)
    
    # Add to consciousness
    consciousness.plugins = plugin_manager
    
    # Add convenience methods
    consciousness.execute_plugin_capability = plugin_manager.execute_capability
    consciousness.emit_plugin_event = plugin_manager.emit_event
    consciousness.get_plugin_status = plugin_manager.get_all_plugin_status
    
    return plugin_manager