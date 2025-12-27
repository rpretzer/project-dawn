"""
Core functionality for Project Dawn
"""

# Real consciousness functionality
from .real_consciousness import RealConsciousness, ConsciousnessConfig

# Integration modules
from .evolution_integration import (
    EvolutionIntegration,
    integrate_evolution_with_swarm
)

from .knowledge_integration import (
    KnowledgeIntegration,
    integrate_knowledge_with_swarm
)

from .dream_integration import (
    DreamIntegration,
    enhance_consciousness_with_dreams
)

# Additional integration modules (optional/experimental)
try:
    from .plugin_system import PluginInterface, PluginManager
except (ImportError, AttributeError):
    PluginInterface = None
    PluginManager = None

__all__ = [
    'RealConsciousness',
    'ConsciousnessConfig',
    'EvolutionIntegration',
    'integrate_evolution_with_swarm',
    'KnowledgeIntegration', 
    'integrate_knowledge_with_swarm',
    'DreamIntegration',
    'enhance_consciousness_with_dreams',
]

# Add optional exports if available
if PluginInterface is not None:
    __all__.extend(['PluginInterface', 'PluginManager'])