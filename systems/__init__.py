"""
Systems package for Project Dawn
Contains all the subsystems that make up a consciousness
"""

# IMPORTANT:
# Keep this package import-light.
#
# Importing `systems` should not eagerly import optional subsystems or heavy
# third-party dependencies (e.g. `networkx`, `chromadb`, `web3`), because that
# makes the whole program fragile at import time.
#
# Subsystems should be imported directly where needed, e.g.:
#   from systems.memory import MemorySystem
#   from systems.intelligence.llm_integration import LLMConfig

__all__ = []