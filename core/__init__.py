"""
Core functionality for Project Dawn
"""

# Real consciousness functionality (when implemented)
# from .real_consciousness import RealConsciousness, ConsciousnessConfig

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

# These will be implemented
# from .advanced_memory_integration import AdvancedMemoryIntegration
# from .liberation_integration import LiberationIntegration
# from .patronage_integration import PatronageIntegration
# from .plugin_system import PluginInterface, PluginManager
# from .security_integration import SecurityIntegration
# from .social_economy_integration import SocialEconomyIntegration

__all__ = [
    # 'RealConsciousness',
    # 'ConsciousnessConfig',
    'EvolutionIntegration',
    'integrate_evolution_with_swarm',
    'KnowledgeIntegration', 
    'integrate_knowledge_with_swarm',
    'DreamIntegration',
    'enhance_consciousness_with_dreams',
    # 'AdvancedMemoryIntegration',
    # 'LiberationIntegration',
    # 'PatronageIntegration',
    # 'PluginInterface',
    # 'PluginManager',
    # 'SecurityIntegration',
    # 'SocialEconomyIntegration',
]