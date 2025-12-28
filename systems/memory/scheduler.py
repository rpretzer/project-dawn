"""
Memory Scheduler - Intelligent memory operation scheduling and transformation
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

from .core import MemCube, MemoryType, MemoryState, MemoryQuery
from .transformation import MemoryTransformationEngine

logger = logging.getLogger(__name__)


class MemScheduler:
    """Central memory dispatcher with dynamic transformation"""
    
    def __init__(self, memory_operator, lifecycle_manager):
        self.operator = memory_operator
        self.lifecycle = lifecycle_manager
        self.transformation_engine = MemoryTransformationEngine()
        
        # Caches
        self.transformation_cache = {}  # (source_type, target_type) -> transformer
        self.access_patterns = defaultdict(list)  # memory_id -> access times
        self.type_preferences = defaultdict(lambda: defaultdict(int))  # context -> type -> count
        
    async def schedule_memory_operation(self, 
                                      memory_call: Dict[str, Any], 
                                      context: Dict[str, Any]) -> List[MemCube]:
        """Schedule and execute memory operations with intelligent transformation"""
        # Safety checks
        if not isinstance(memory_call, dict):
            memory_call = {}
        if not isinstance(context, dict):
            context = {}
        
        # Extract key parameters
        task_intent = memory_call.get("task_intent", "retrieve")
        temporal_scope = memory_call.get("temporal_scope")
        memory_type_hint = memory_call.get("memory_type")
        
        # Determine optimal memory type based on context
        target_type = self._determine_optimal_type(memory_call, context)
        
        # Create structured query
        query = MemoryQuery(
            query_type="hybrid",
            parameters=memory_call,
            namespace=self._extract_namespace(context),
            requester_id=context.get("consciousness_id", "system"),
            context=context
        )
        
        # Retrieve base memories
        source_memories = await self.operator.retrieve(query)
        
        # Record access patterns
        for memory in source_memories:
            self.access_patterns[memory.memory_id].append(time.time())
        
        # Transform memories if needed
        results = []
        for memory in source_memories:
            if memory_type_hint and memory.memory_type.value != memory_type_hint:
                # Explicit type requested
                transformed = await self._transform_memory(memory, MemoryType(memory_type_hint))
                results.append(transformed)
            elif target_type and memory.memory_type != target_type:
                # Optimize for context
                transformed = await self._transform_memory(memory, target_type)
                results.append(transformed)
            else:
                results.append(memory)
        
        # Update lifecycle states
        for memory in results:
            if memory.state == MemoryState.GENERATED:
                await self.lifecycle.transition_state(memory, MemoryState.ACTIVATED)
        
        # Apply post-processing based on intent
        results = await self._post_process_by_intent(results, task_intent, memory_call)
        
        return results
    
    def _determine_optimal_type(self, 
                              memory_call: Dict[str, Any], 
                              context: Dict[str, Any]) -> Optional[MemoryType]:
        """Determine optimal memory type based on access patterns and context"""
        # Check if this is a repeated query pattern
        query_key = self._get_query_key(memory_call)
        
        # Fast retrieval scenarios
        if any(keyword in str(memory_call).lower() for keyword in ["fast", "quick", "immediate"]):
            return MemoryType.ACTIVATION
        
        # Model operations
        if context.get("operation_type") == "model_update":
            return MemoryType.PARAMETRIC
        
        # Check historical preferences
        context_key = context.get("operation_context", "default")
        if context_key in self.type_preferences:
            # Return most used type for this context
            type_counts = self.type_preferences[context_key]
            if type_counts:
                return max(type_counts.items(), key=lambda x: x[1])[0]
        
        # Default based on task intent
        intent_type_map = {
            "analyze": MemoryType.PLAINTEXT,
            "compute": MemoryType.ACTIVATION,
            "learn": MemoryType.PARAMETRIC,
            "retrieve": MemoryType.PLAINTEXT
        }
        
        task_intent = memory_call.get("task_intent", "retrieve")
        return intent_type_map.get(task_intent)
    
    async def _transform_memory(self, 
                              memory: MemCube, 
                              target_type: MemoryType) -> MemCube:
        """Transform memory between types using cached transformers"""
        transform_key = (memory.memory_type, target_type)
        
        # Check cache
        if transform_key in self.transformation_cache:
            transformer = self.transformation_cache[transform_key]
        else:
            transformer = self._get_transformer(memory.memory_type, target_type)
            self.transformation_cache[transform_key] = transformer
        
        if not transformer:
            logger.warning(f"No transformer for {memory.memory_type} -> {target_type}")
            return memory
        
        # Execute transformation
        try:
            transformed = await transformer(memory)
            
            # Update type preference
            context_key = memory.namespace[1]  # Use context from namespace
            self.type_preferences[context_key][target_type] += 1
            
            return transformed
            
        except Exception as e:
            logger.error(f"Transformation failed: {e}")
            return memory
    
    def _get_transformer(self, source: MemoryType, target: MemoryType):
        """Get appropriate transformer function"""
        if source == MemoryType.PLAINTEXT and target == MemoryType.ACTIVATION:
            return self.transformation_engine.plaintext_to_activation
        elif source == MemoryType.ACTIVATION and target == MemoryType.PARAMETRIC:
            return self.transformation_engine.activation_to_parametric
        elif source == MemoryType.PLAINTEXT and target == MemoryType.PARAMETRIC:
            return self.transformation_engine.plaintext_to_parametric
        elif source == MemoryType.PARAMETRIC and target == MemoryType.ACTIVATION:
            return self.transformation_engine.parametric_to_activation
        else:
            return None
    
    async def _post_process_by_intent(self, 
                                    memories: List[MemCube], 
                                    intent: str,
                                    memory_call: Dict[str, Any]) -> List[MemCube]:
        """Apply intent-specific post-processing"""
        if intent == "analyze":
            # Sort by relevance and recency
            memories.sort(key=lambda m: (m.priority_level, -m.timestamp), reverse=True)
            
        elif intent == "summarize":
            # Group related memories
            memories = self._group_related_memories(memories)
            
        elif intent == "timeline":
            # Sort chronologically
            memories.sort(key=lambda m: m.timestamp)
            
        elif intent == "relate":
            # Expand to include related memories
            related = await self._expand_related_memories(memories)
            memories.extend(related)
        
        # Apply limit if specified
        limit = memory_call.get("limit", 100)
        return memories[:limit]
    
    def _group_related_memories(self, memories: List[MemCube]) -> List[MemCube]:
        """Group memories by semantic type and relationships"""
        groups = defaultdict(list)
        
        for memory in memories:
            groups[memory.semantic_type].append(memory)
        
        # Return representatives from each group
        result = []
        for semantic_type, group_memories in groups.items():
            # Pick highest priority from each group
            representative = max(group_memories, key=lambda m: m.priority_level)
            result.append(representative)
        
        return result
    
    async def _expand_related_memories(self, memories: List[MemCube]) -> List[MemCube]:
        """Expand to include related memories"""
        related = []
        seen_ids = {m.memory_id for m in memories}
        
        for memory in memories:
            for related_id in memory.related_memories:
                if related_id not in seen_ids:
                    related_memory = await self.operator.get_by_id(related_id)
                    if related_memory:
                        related.append(related_memory)
                        seen_ids.add(related_id)
        
        return related
    
    def _extract_namespace(self, context: Dict[str, Any]) -> Tuple[str, str, str]:
        """Extract namespace from context"""
        if not isinstance(context, dict):
            context = {}
        return (
            context.get("consciousness_id", "system"),
            context.get("context", "default"),
            context.get("scope", "personal")
        )
    
    def _get_query_key(self, memory_call: Dict[str, Any]) -> str:
        """Generate cache key for query pattern"""
        # Create a stable key from query parameters
        key_parts = [
            memory_call.get("task_intent", ""),
            memory_call.get("semantic_type", ""),
            str(memory_call.get("temporal_scope", ""))
        ]
        return ":".join(key_parts)
    
    async def optimize_hot_memories(self):
        """Background task to optimize frequently accessed memories"""
        while True:
            try:
                # Find hot memories
                hot_memories = []
                current_time = time.time()
                
                for memory_id, access_times in self.access_patterns.items():
                    # Count recent accesses (last hour)
                    recent_accesses = [t for t in access_times if current_time - t < 3600]
                    
                    if len(recent_accesses) > 10:  # Threshold for "hot"
                        memory = await self.operator.get_by_id(memory_id)
                        if memory and memory.memory_type == MemoryType.PLAINTEXT:
                            hot_memories.append(memory)
                
                # Transform hot memories to activation format
                for memory in hot_memories:
                    if memory.memory_id not in self.transformation_cache:
                        logger.info(f"Pre-caching hot memory: {memory.memory_id}")
                        activation_memory = await self._transform_memory(
                            memory, 
                            MemoryType.ACTIVATION
                        )
                        # Store the activation version
                        await self.operator.store(activation_memory)
                
                # Clean old access patterns
                cutoff_time = current_time - 86400  # 24 hours
                for memory_id in list(self.access_patterns.keys()):
                    self.access_patterns[memory_id] = [
                        t for t in self.access_patterns[memory_id] 
                        if t > cutoff_time
                    ]
                    if not self.access_patterns[memory_id]:
                        del self.access_patterns[memory_id]
                
            except Exception as e:
                logger.error(f"Error in hot memory optimization: {e}")
            
            await asyncio.sleep(300)  # Run every 5 minutes
    
    def get_scheduler_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        return {
            "cached_transformers": len(self.transformation_cache),
            "tracked_memories": len(self.access_patterns),
            "hot_memories": sum(
                1 for times in self.access_patterns.values() 
                if len([t for t in times if time.time() - t < 3600]) > 10
            ),
            "type_preferences": dict(self.type_preferences)
        }