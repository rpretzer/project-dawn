"""
memOS - Memory Operating System for Project Dawn
"""

from .core import MemCube, MemoryType, MemoryState
from .interface import MemoryAPI, MemReader, MemoryPipeline
from .vault import MemVault
from .governance import MemGovernance

# Main entry point
class MemorySystem:
    """Main memory system for consciousness"""
    
    def __init__(self, consciousness_id: str, config: Dict):
        # Initialize layers
        self.vault = MemVault(config.get("storage", {}))
        self.governance = MemGovernance(
            config.get("policies", {}),
            config.get("audit", {})
        )
        
        # Set cross-references
        self.vault.governance = self.governance
        
        # Initialize API
        self.api = MemoryAPI(self.vault)
        self.reader = MemReader(config.get("nlp_model"))
        
        # Initialize scheduler and operator
        from .operator import MemOperator
        from .lifecycle import MemLifecycle
        from .scheduler import MemScheduler
        
        self.operator = MemOperator(self.vault)
        self.lifecycle = MemLifecycle(self.vault)
        self.scheduler = MemScheduler(self.operator, self.lifecycle)
        
        self.consciousness_id = consciousness_id
        
    async def remember(self, content: Any, context: Dict = None) -> str:
        """Store a memory"""
        memory = MemCube(
            memory_id=None,
            content=content,
            memory_type=self._infer_memory_type(content),
            timestamp=time.time(),
            origin_signature=self.consciousness_id,
            semantic_type=context.get("type", "general"),
            namespace=(self.consciousness_id, "personal", "default"),
            access_control={"owner": ["read", "write", "delete"]},
            ttl=None,
            priority_level=context.get("priority", 1),
            compliance_tags=[]
        )
        
        return await self.api.store(memory)
    
    async def recall(self, query: str, context: Dict = None) -> List[MemCube]:
        """Retrieve memories"""
        parsed_query = self.reader.parse_memory_query(query)
        parsed_query.update(context or {})
        
        return await self.scheduler.schedule_memory_operation(
            parsed_query,
            context or {}
        )

__all__ = [
    'MemorySystem',
    'MemCube',
    'MemoryType',
    'MemoryState',
    'MemoryAPI'
]