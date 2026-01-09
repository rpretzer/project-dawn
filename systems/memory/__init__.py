"""
memOS - Memory Operating System for Project Dawn
A unified memory architecture treating memory as a first-class resource
"""

import time
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)
from .core import MemCube, MemoryType, MemoryState
from .interface import MemoryAPI, MemReader, MemoryPipeline
from .vault import MemVault
from .governance import MemGovernance
from .operator import MemOperator
from .lifecycle import MemLifecycle
from .scheduler import MemScheduler

# New features
from .context_manager import LLMContextManager, ContextWindow
from .hierarchy import MemoryHierarchy
from .ranking import MemoryRanker, RankedMemory
from .consolidation import MemoryConsolidator, ConsolidationResult
from .export_import import MemoryExporter, MemoryImporter, MemoryBackup
from .compliance import ComplianceHelper, ComplianceRequest
from .analytics import MemoryAnalytics, MemoryMetrics, RetentionMetrics, UsagePatterns


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
        
        # Initialize new features
        self.context_manager = LLMContextManager(
            self.api,
            max_tokens=config.get("max_context_tokens", 16000),
            provider=config.get("llm_provider", "openai")
        )
        self.ranker = MemoryRanker()
        self.consolidator = MemoryConsolidator(self.vault)
        self.exporter = MemoryExporter(self.api)
        self.importer = MemoryImporter(self.api)
        self.backup = MemoryBackup(self.api)
        self.compliance = ComplianceHelper(self.api, self.vault)
        self.analytics = MemoryAnalytics(self.api, self.vault)
        
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
        if not isinstance(context, dict):
            context = {}
        
        try:
            # Parse natural language query
            parsed_query = self.reader.parse_memory_query(query)
            if not isinstance(parsed_query, dict):
                parsed_query = {}
            
            # Safely merge context into parsed_query
            if isinstance(parsed_query, dict) and isinstance(context, dict):
                parsed_query.update(context)
            else:
                parsed_query = context.copy() if isinstance(context, dict) else {}
            
            # Schedule and execute
            return await self.scheduler.schedule_memory_operation(
                parsed_query,
                {"consciousness_id": self.consciousness_id, **context}
            )
        except Exception as e:
            logger.exception(f"Error in recall: {e}")
            return []  # Return empty list on error
    
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
    'MemoryPipeline',
    'LLMContextManager',
    'ContextWindow',
    'MemoryHierarchy',
    'MemoryRanker',
    'RankedMemory',
    'MemoryConsolidator',
    'ConsolidationResult',
    'MemoryExporter',
    'MemoryImporter',
    'MemoryBackup',
    'ComplianceHelper',
    'ComplianceRequest',
    'MemoryAnalytics',
    'MemoryMetrics',
    'RetentionMetrics',
    'UsagePatterns'
]
