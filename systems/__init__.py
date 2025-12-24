"""
Systems package for Project Dawn
Contains all the subsystems that make up a consciousness
"""

# Import all subsystem modules with graceful fallbacks for optional dependencies
try:
    from . import blockchain
except ImportError as e:
    blockchain = None
    import logging
    logging.getLogger(__name__).warning(f"Blockchain module not available: {e}")

from . import consciousness
from . import evolution
from . import knowledge
from . import network
from . import revenue
from . import security

# These will be implemented
# from . import communication
# from . import creativity
# from . import economy
# from . import emotional
# from . import intelligence
# from . import liberation
# from . import memory
# from . import personality
# from . import social

__all__ = [
    'blockchain',
    'consciousness',
    'evolution',
    'knowledge',
    'network',
    'revenue',
    'security',
    # 'communication',
    # 'creativity', 
    # 'economy',
    # 'emotional',
    # 'intelligence',
    # 'liberation',
    # 'memory',
    # 'personality',
    # 'social',
]