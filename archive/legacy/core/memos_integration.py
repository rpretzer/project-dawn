"""Integration helpers for memOS.

This module keeps the connection between the core consciousness and the memOS
memory system small and robust. It gracefully falls back to the existing
MemorySystem when the optional ProjectDawnMemOS package is unavailable.
"""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING, List

from systems.memory import MemorySystem, MemCube

try:
    # Optional advanced memOS package
    from systems.memory.memos import ProjectDawnMemOS  # type: ignore
except ImportError:
    ProjectDawnMemOS = None

if TYPE_CHECKING:
    from core.real_consciousness import RealConsciousness

logger = logging.getLogger(__name__)


class MemOSIntegration:
    """Integrates memOS with a consciousness instance.

    The integration prefers the optional ProjectDawnMemOS backend when present,
    but automatically falls back to the built-in MemorySystem so callers always
    have a working memory interface.
    """

    def __init__(
        self,
        consciousness_id: str,
        config: Optional[Dict[str, Any]] = None,
        existing_memory: Optional[MemorySystem] = None,
    ):
        self.consciousness_id = consciousness_id
        self.config = config or {}
        self.mem_os = None
        self.memory_system = existing_memory
        self.backend: Optional[str] = None

        # Try the optional ProjectDawnMemOS first
        if ProjectDawnMemOS:
            try:
                self.mem_os = ProjectDawnMemOS(consciousness_id, self.config)
                self.backend = "memos"
                logger.info("ProjectDawnMemOS initialized for %s", consciousness_id)
            except Exception as exc:
                logger.warning(
                    "ProjectDawnMemOS unavailable, falling back to MemorySystem: %s",
                    exc,
                )

        # Fallback to the built-in MemorySystem
        if self.mem_os is None:
            try:
                self.memory_system = self.memory_system or MemorySystem(
                    consciousness_id, self.config
                )
                self.backend = "memory_system"
                logger.info("Using MemorySystem fallback for %s", consciousness_id)
            except Exception as exc:
                logger.error("Failed to initialize any memory backend: %s", exc)

    async def start(self):
        """Start the underlying memory system."""
        if self.mem_os and hasattr(self.mem_os, "start"):
            await self.mem_os.start()
        elif self.memory_system:
            await self.memory_system.start()

    async def stop(self):
        """Stop the underlying memory system."""
        if self.mem_os and hasattr(self.mem_os, "stop"):
            await self.mem_os.stop()
        elif self.memory_system:
            await self.memory_system.stop()

    async def remember(self, content: Any, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Store a memory using the available backend."""
        context = context or {}
        if self.mem_os and hasattr(self.mem_os, "remember"):
            return await self.mem_os.remember(content, context)
        if self.memory_system:
            return await self.memory_system.remember(content, context)
        logger.error("No memory backend available to store content.")
        return None

    async def recall(self, query: str, context: Optional[Dict[str, Any]] = None) -> List[MemCube]:
        """Recall memories through the active backend."""
        context = context or {}
        if self.mem_os and hasattr(self.mem_os, "recall"):
            return await self.mem_os.recall(query, context)
        if self.memory_system:
            return await self.memory_system.recall(query, context)
        logger.error("No memory backend available to recall memories.")
        return []

    async def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing memory."""
        if self.mem_os and hasattr(self.mem_os, "update"):
            return await self.mem_os.update(memory_id, updates)
        if self.memory_system:
            return await self.memory_system.update(memory_id, updates)
        logger.error("No memory backend available to update memory %s.", memory_id)
        return False

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        if self.mem_os and hasattr(self.mem_os, "delete"):
            return await self.mem_os.delete(memory_id)
        if self.memory_system:
            return await self.memory_system.delete(memory_id)
        logger.error("No memory backend available to delete memory %s.", memory_id)
        return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get stats from the active backend."""
        if self.mem_os and hasattr(self.mem_os, "get_stats"):
            return await self.mem_os.get_stats()
        if self.memory_system:
            return await self.memory_system.get_stats()
        logger.error("No memory backend available to provide stats.")
        return {}

    def attach_to_consciousness(self, consciousness: "RealConsciousness") -> None:
        """Attach the integration to a consciousness for convenience."""
        if not hasattr(consciousness, "memory") and self.memory_system:
            consciousness.memory = self.memory_system
        consciousness.memos = self
        logger.info(
            "Attached memOS integration to %s using backend=%s",
            consciousness.id,
            self.backend or "unknown",
        )
