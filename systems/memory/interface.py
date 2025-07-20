"""
Interface layer for memOS - handles API, natural language parsing, and pipelines
"""

from typing import Dict, List, Optional, Tuple, Callable, Any
import asyncio
import time
import re
from abc import ABC, abstractmethod
import logging

from .core import MemCube, MemoryQuery, MemoryType, MemoryState

logger = logging.getLogger(__name__)


class MemReader:
    """Semantic abstraction for memory-level reasoning"""
    
    def __init__(self, nlp_model: Optional[Any] = None):
        self.nlp_model = nlp_model
        self.intent_patterns = self._init_intent_patterns()
        self.temporal_patterns = self._init_temporal_patterns()
        
    def _init_intent_patterns(self) -> Dict[str, List[str]]:
        """Initialize intent recognition patterns"""
        return {
            "retrieve": ["find", "get", "recall", "remember", "what", "show"],
            "analyze": ["analyze", "compare", "understand", "explain"],
            "summarize": ["summarize", "overview", "brief", "tldr"],
            "relate": ["related", "connection", "link", "relationship"],
            "timeline": ["when", "timeline", "history", "progression"]
        }
    
    def _init_temporal_patterns(self) -> Dict[str, str]:
        """Initialize temporal parsing patterns"""
        return {
            r"last (\d+) hours?": "hours",
            r"last (\d+) days?": "days",
            r"since yesterday": "yesterday",
            r"today": "today",
            r"this week": "week",
            r"recent": "recent"
        }
    
    def parse_memory_query(self, query: str) -> Dict[str, Any]:
        """Extract memory-related features from natural language"""
        return {
            "task_intent": self._extract_intent(query),
            "temporal_scope": self._extract_temporal(query),
            "entity_focus": self._extract_entities(query),
            "memory_type": self._infer_memory_type(query),
            "contextual_anchors": self._extract_context(query),
            "raw_query": query
        }
    
    def _extract_intent(self, query: str) -> str:
        """Extract primary intent from query"""
        query_lower = query.lower()
        
        for intent, patterns in self.intent_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                return intent
        
        return "retrieve"  # Default
    
    def _extract_temporal(self, query: str) -> Optional[Dict[str, Any]]:
        """Extract temporal constraints"""
        query_lower = query.lower()
        
        for pattern, time_type in self.temporal_patterns.items():
            match = re.search(pattern, query_lower)
            if match:
                if time_type in ["hours", "days"]:
                    return {
                        "type": "relative",
                        "unit": time_type,
                        "value": int(match.group(1))
                    }
                else:
                    return {"type": time_type}
        
        return None
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract named entities from query"""
        # Simple extraction - in production would use NER
        entities = []
        
        # Extract quoted strings
        quoted = re.findall(r'"([^"]*)"', query)
        entities.extend(quoted)
        
        # Extract capitalized words (simple heuristic)
        words = query.split()
        for word in words:
            if word[0].isupper() and word.lower() not in ["what", "when", "where", "how"]:
                entities.append(word)
        
        return entities
    
    def _infer_memory_type(self, query: str) -> Optional[str]:
        """Infer desired memory type from query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["cache", "activation", "fast"]):
            return MemoryType.ACTIVATION.value
        elif any(word in query_lower for word in ["model", "weights", "lora"]):
            return MemoryType.PARAMETRIC.value
        elif any(word in query_lower for word in ["document", "text", "note"]):
            return MemoryType.PLAINTEXT.value
        
        return None
    
    def _extract_context(self, query: str) -> Dict[str, Any]:
        """Extract contextual information"""
        context = {}
        
        # Extract semantic type hints
        if "insight" in query.lower():
            context["semantic_type"] = "insight"
        elif "fact" in query.lower():
            context["semantic_type"] = "fact"
        elif "experience" in query.lower():
            context["semantic_type"] = "experience"
        
        return context


class MemoryAPI:
    """Unified API for all memory operations"""
    
    def __init__(self, memory_vault):
        self.vault = memory_vault
        self.access_log = []
        
    async def store(self, memory: MemCube) -> str:
        """Store a new memory with full governance"""
        # Validate memory
        self._validate_memory(memory)
        
        # Apply governance
        if hasattr(self.vault, 'governance'):
            memory = await self.vault.governance.apply_policies(memory)
        
        # Store in vault
        memory_id = await self.vault.store(memory)
        
        # Log operation
        self._log_operation("store", memory_id, True)
        
        return memory_id
    
    async def retrieve(self, query: MemoryQuery) -> List[MemCube]:
        """Retrieve memories based on structured query"""
        # Log access attempt
        self._log_operation("retrieve", query.to_dict(), True)
        
        # Retrieve from vault
        memories = await self.vault.retrieve(query)
        
        # Update access patterns
        for memory in memories:
            memory.update_access()
            await self.vault.update_access_stats(memory.memory_id)
        
        return memories
    
    async def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing memory"""
        try:
            # Retrieve current memory
            memory = await self.vault.get_by_id(memory_id)
            if not memory:
                return False
            
            # Create new version
            old_version = memory.memory_id
            memory.memory_id = f"mem_{uuid.uuid4().hex[:12]}"
            memory.version_chain.append(old_version)
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(memory, key):
                    setattr(memory, key, value)
            
            # Store new version
            await self.vault.store(memory)
            
            # Archive old version
            await self.vault.archive(old_version)
            
            self._log_operation("update", memory_id, True)
            return True
            
        except Exception as e:
            logger.error(f"Error updating memory {memory_id}: {e}")
            self._log_operation("update", memory_id, False)
            return False
    
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory (actually archives it)"""
        try:
            success = await self.vault.archive(memory_id)
            self._log_operation("delete", memory_id, success)
            return success
        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}")
            return False
    
    async def search(self, query: str, namespace: Tuple[str, str, str], limit: int = 10) -> List[MemCube]:
        """High-level search interface"""
        reader = MemReader()
        parsed = reader.parse_memory_query(query)
        
        memory_query = MemoryQuery(
            query_type="hybrid",
            parameters={
                **parsed,
                "limit": limit
            },
            namespace=namespace,
            requester_id=namespace[0]
        )
        
        return await self.retrieve(memory_query)
    
    def _validate_memory(self, memory: MemCube):
        """Validate memory before storage"""
        if not memory.memory_id:
            raise ValueError("Memory must have an ID")
        if not memory.namespace or len(memory.namespace) != 3:
            raise ValueError("Memory must have valid namespace (user, context, scope)")
        if memory.priority_level < 1 or memory.priority_level > 10:
            raise ValueError("Priority level must be between 1 and 10")
    
    def _log_operation(self, operation: str, target: Any, success: bool):
        """Log memory operation"""
        self.access_log.append({
            "timestamp": time.time(),
            "operation": operation,
            "target": str(target),
            "success": success
        })
        
        # Keep last 1000 entries
        if len(self.access_log) > 1000:
            self.access_log = self.access_log[-1000:]


class MemoryPipeline:
    """Composable pipeline for chaining memory operations"""
    
    def __init__(self):
        self.operations: List[Tuple[str, Callable]] = []
        self.checkpoints: List[Tuple[int, Any]] = []
        
    def add_operation(self, name: str, operation: Callable) -> 'MemoryPipeline':
        """Add operation to pipeline"""
        self.operations.append((name, operation))
        return self
    
    def filter(self, predicate: Callable[[MemCube], bool]) -> 'MemoryPipeline':
        """Add filter operation"""
        async def filter_op(memories: List[MemCube]) -> List[MemCube]:
            return [m for m in memories if predicate(m)]
        
        return self.add_operation("filter", filter_op)
    
    def map(self, transform: Callable[[MemCube], MemCube]) -> 'MemoryPipeline':
        """Add map operation"""
        async def map_op(memories: List[MemCube]) -> List[MemCube]:
            return [transform(m) for m in memories]
        
        return self.add_operation("map", map_op)
    
    def sort(self, key: Callable[[MemCube], Any], reverse: bool = False) -> 'MemoryPipeline':
        """Add sort operation"""
        async def sort_op(memories: List[MemCube]) -> List[MemCube]:
            return sorted(memories, key=key, reverse=reverse)
        
        return self.add_operation("sort", sort_op)
    
    def limit(self, n: int) -> 'MemoryPipeline':
        """Limit results"""
        async def limit_op(memories: List[MemCube]) -> List[MemCube]:
            return memories[:n]
        
        return self.add_operation("limit", limit_op)
    
    async def execute(self, input_data: Any) -> Any:
        """Execute pipeline with transaction support"""
        result = input_data
        
        try:
            for i, (name, op) in enumerate(self.operations):
                logger.debug(f"Executing pipeline operation: {name}")
                result = await op(result)
                self.checkpoints.append((i, result))
                
        except Exception as e:
            logger.error(f"Pipeline error at operation {i}: {e}")
            # Rollback to last checkpoint
            if self.checkpoints:
                last_checkpoint = self.checkpoints[-1]
                result = last_checkpoint[1]
            raise e
        
        return result
    
    async def _rollback(self):
        """Rollback to last checkpoint"""
        if self.checkpoints:
            # In a real implementation, this would undo changes
            logger.info(f"Rolling back to checkpoint {len(self.checkpoints) - 1}")


class ProvenanceAPI:
    """Track memory lineage and provenance"""
    
    def __init__(self, vault):
        self.vault = vault
        
    async def embed_metadata(self, memory: MemCube) -> MemCube:
        """Embed provenance metadata"""
        memory.contextual_fingerprint = self._generate_fingerprint(memory)
        return memory
    
    def _generate_fingerprint(self, memory: MemCube) -> str:
        """Generate contextual fingerprint"""
        import hashlib
        
        fingerprint_data = f"{memory.origin_signature}:{memory.semantic_type}:{memory.timestamp}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]
    
    async def get_lineage(self, memory_id: str) -> List[MemCube]:
        """Get complete lineage of a memory"""
        lineage = []
        current_id = memory_id
        
        while current_id:
            memory = await self.vault.get_by_id(current_id)
            if not memory:
                break
                
            lineage.append(memory)
            
            # Get parent
            if memory.version_chain:
                current_id = memory.version_chain[-1]
            else:
                current_id = None
        
        return lineage


class UpdateAPI:
    """Handle memory updates and versioning"""
    
    def __init__(self, vault):
        self.vault = vault
        
    async def create_version(self, memory: MemCube, changes: Dict[str, Any]) -> MemCube:
        """Create new version of memory"""
        # Clone memory
        new_memory = MemCube.from_dict(memory.to_dict())
        
        # Update version chain
        new_memory.version_chain.append(memory.memory_id)
        new_memory.memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        
        # Apply changes
        for key, value in changes.items():
            if hasattr(new_memory, key):
                setattr(new_memory, key, value)
        
        # Update metadata
        new_memory.timestamp = time.time()
        
        return new_memory


class LogQueryAPI:
    """Log and analyze memory access patterns"""
    
    def __init__(self, vault):
        self.vault = vault
        self.query_log = []
        
    async def log_access(self, query: Dict[str, Any], namespace: Tuple[str, str, str]):
        """Log query access"""
        self.query_log.append({
            "timestamp": time.time(),
            "query": query,
            "namespace": namespace
        })
        
        # Analyze patterns periodically
        if len(self.query_log) % 100 == 0:
            await self._analyze_patterns()
    
    async def _analyze_patterns(self):
        """Analyze access patterns for optimization"""
        # Simple frequency analysis
        query_types = {}
        for entry in self.query_log[-1000:]:  # Last 1000 queries
            q_type = entry["query"].get("task_intent", "unknown")
            query_types[q_type] = query_types.get(q_type, 0) + 1
        
        logger.info(f"Query pattern analysis: {query_types}")