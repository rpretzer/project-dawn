"""
memOS - Memory Operating System for Project Dawn
A unified memory architecture treating memory as a first-class resource
"""

import time
from typing import Dict, List, Optional, Any
from .core import MemCube, MemoryType, MemoryState
from .interface import MemoryAPI, MemReader, MemoryPipeline
from .vault import MemVault
from .governance import MemGovernance
from .operator import MemOperator
from .lifecycle import MemLifecycle
from .scheduler import MemScheduler


class MemorySystem:
    """Main memory system for consciousness"""
    
    def __init__(self, consciousness_id: str, config: Dict):
        self.consciousness_id = consciousness_id
        self.config = config
        
        # Initialize infrastructure layer
        self.vault = MemVault(config.get("storage", {}))
        self.governance = MemGovernance(
            config.get("policies", {}),
            config.get("audit", {})
        )
        
        # Cross-references
        self.vault.governance = self.governance
        
        # Initialize interface layer
        self.api = MemoryAPI(self.vault)
        self.reader = MemReader(config.get("nlp_model"))
        
        # Initialize operation layer
        self.operator = MemOperator(self.vault)
        self.lifecycle = MemLifecycle(self.vault)
        self.scheduler = MemScheduler(self.operator, self.lifecycle)
        
    async def start(self):
        """Start memory system background tasks"""
        await self.lifecycle.start_background_tasks()
        
    async def stop(self):
        """Stop memory system"""
        await self.lifecycle.stop_background_tasks()
        
    async def remember(self, content: Any, context: Optional[Dict] = None) -> str:
        """Store a memory with automatic type inference"""
        context = context or {}
        
        memory = MemCube(
            memory_id=None,
            content=content,
            memory_type=self._infer_memory_type(content),
            timestamp=time.time(),
            origin_signature=self.consciousness_id,
            semantic_type=context.get("type", "general"),
            namespace=(self.consciousness_id, "personal", "default"),
            access_control={"owner": ["read", "write", "delete"]},
            ttl=context.get("ttl"),
            priority_level=context.get("priority", 1),
            compliance_tags=context.get("tags", [])
        )
        
        return await self.api.store(memory)
    
    async def recall(self, query: str, context: Optional[Dict] = None) -> List[MemCube]:
        """Retrieve memories using natural language or structured query"""
        context = context or {}
        
        # Parse natural language query
        parsed_query = self.reader.parse_memory_query(query)
        parsed_query.update(context)
        
        # Schedule and execute
        return await self.scheduler.schedule_memory_operation(
            parsed_query,
            {"consciousness_id": self.consciousness_id, **context}
        )
    
    async def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing memory"""
        return await self.api.update(memory_id, updates)
    
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory"""
        return await self.api.delete(memory_id)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        return {
            "total_memories": await self.vault.count(),
            "by_type": await self.vault.count_by_type(),
            "by_state": await self.vault.count_by_state(),
            "hot_memories": await self.operator.get_hot_memories(),
            "storage_size": await self.vault.get_storage_size()
        }
    
    def _infer_memory_type(self, content: Any) -> MemoryType:
        """Infer memory type from content"""
        if isinstance(content, dict):
            if "kv_cache" in content or "attention_mask" in content:
                return MemoryType.ACTIVATION
            elif "lora_weights" in content or "model_params" in content:
                return MemoryType.PARAMETRIC
        
        return MemoryType.PLAINTEXT


__all__ = [
    'MemorySystem',
    'MemCube',
    'MemoryType',
    'MemoryState',
    'MemoryAPI',
    'MemReader',
    'MemoryPipeline'
]