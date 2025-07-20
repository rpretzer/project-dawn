"""
Memory Operator - Handles memory organization, retrieval, and relationships
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
import json

from .core import MemCube, MemoryQuery, MemoryType, MemoryState, MemoryRelation
from .vault import MemVault

logger = logging.getLogger(__name__)


class MemOperator:
    """Memory organization and retrieval management"""
    
    def __init__(self, memory_vault: MemVault):
        self.vault = memory_vault
        
        # Indexes for fast lookup
        self.semantic_index = defaultdict(set)  # semantic_type -> memory_ids
        self.tag_index = defaultdict(set)       # tag -> memory_ids
        self.relation_index = defaultdict(list)  # memory_id -> relations
        
        # Memory graph for relationships
        self.memory_graph = {}  # memory_id -> {related_ids}
        
        # Initialize indexes from existing memories
        asyncio.create_task(self._rebuild_indexes())
    
    async def _rebuild_indexes(self):
        """Rebuild indexes from vault"""
        logger.info("Rebuilding memory indexes...")
        
        # This would query all memories - simplified for example
        # In production, would batch this operation
        pass
    
    async def store(self, memory: MemCube) -> str:
        """Store memory with indexing"""
        # Store in vault
        memory_id = await self.vault.store(memory)
        
        # Update indexes
        self._index_memory(memory)
        
        # Organize by semantic layers
        await self._organize_by_layer(memory)
        
        # Detect and create relationships
        await self._detect_relationships(memory)
        
        return memory_id
    
    async def retrieve(self, query: MemoryQuery) -> List[MemCube]:
        """Hybrid retrieval combining symbolic and semantic search"""
        # Start with vault retrieval
        candidates = await self.vault.retrieve(query)
        
        # Apply additional filtering and ranking
        candidates = await self._apply_symbolic_filters(candidates, query)
        
        # Merge with index-based retrieval
        if query.parameters.get("semantic_type"):
            index_candidates = await self._retrieve_by_semantic_type(
                query.parameters["semantic_type"],
                query.namespace
            )
            candidates = self._merge_candidates(candidates, index_candidates)
        
        # Apply relationship expansion if requested
        if query.parameters.get("expand_relations"):
            candidates = await self._expand_relationships(candidates)
        
        # Rank results
        ranked = self._rank_results(candidates, query)
        
        # Apply limit
        limit = query.parameters.get("limit", 100)
        return ranked[:limit]
    
    async def get_by_id(self, memory_id: str) -> Optional[MemCube]:
        """Get memory by ID"""
        return await self.vault.get_by_id(memory_id)
    
    async def update_relationship(self, relation: MemoryRelation):
        """Add or update relationship between memories"""
        # Store in relation index
        self.relation_index[relation.source_id].append(relation)
        
        # Update memory graph
        if relation.source_id not in self.memory_graph:
            self.memory_graph[relation.source_id] = set()
        self.memory_graph[relation.source_id].add(relation.target_id)
        
        # Update memories
        source = await self.get_by_id(relation.source_id)
        target = await self.get_by_id(relation.target_id)
        
        if source and target:
            source.add_relation(relation.target_id)
            target.add_relation(relation.source_id)
            
            await self.vault.store(source)
            await self.vault.store(target)
    
    def _index_memory(self, memory: MemCube):
        """Update indexes with new memory"""
        # Semantic type index
        self.semantic_index[memory.semantic_type].add(memory.memory_id)
        
        # Tag index
        for tag in memory.compliance_tags:
            self.tag_index[tag].add(memory.memory_id)
        
        # Additional indexing for common patterns
        if "type:" in str(memory.content):
            # Extract type tags from content
            content_str = str(memory.content)
            if "type:" in content_str:
                type_start = content_str.find("type:") + 5
                type_end = content_str.find(" ", type_start)
                if type_end == -1:
                    type_end = len(content_str)
                extracted_type = content_str[type_start:type_end]
                self.tag_index[f"type:{extracted_type}"].add(memory.memory_id)
    
    async def _organize_by_layer(self, memory: MemCube):
        """Organize memory by semantic layers"""
        # Determine layer based on semantic type
        layer_mapping = {
            "fact": "knowledge",
            "insight": "understanding",
            "experience": "episodic",
            "skill": "procedural",
            "belief": "semantic",
            "emotion": "affective"
        }
        
        layer = layer_mapping.get(memory.semantic_type, "general")
        
        # Create layer-specific organization
        layer_namespace = (memory.namespace[0], f"layer_{layer}", memory.namespace[2])
        
        # Store layer reference
        layer_ref = MemCube(
            memory_id=f"layer_ref_{memory.memory_id}",
            content={"reference": memory.memory_id, "layer": layer},
            memory_type=MemoryType.PLAINTEXT,
            timestamp=memory.timestamp,
            origin_signature="system",
            semantic_type="layer_reference",
            namespace=layer_namespace,
            access_control=memory.access_control,
            priority_level=1,
            compliance_tags=["system", "reference"]
        )
        
        await self.vault.store(layer_ref)
    
    async def _detect_relationships(self, memory: MemCube):
        """Automatically detect relationships with existing memories"""
        # Simple relationship detection based on content similarity
        # In production, would use more sophisticated NLP
        
        if not isinstance(memory.content, str):
            return
        
        content_lower = memory.content.lower()
        
        # Find memories with overlapping concepts
        potential_relations = []
        
        # Check recent memories for relationships
        recent_query = MemoryQuery(
            query_type="temporal",
            parameters={
                "limit": 50,
                "temporal_scope": {"type": "relative", "unit": "hours", "value": 24}
            },
            namespace=memory.namespace,
            requester_id=memory.origin_signature
        )
        
        recent_memories = await self.vault.retrieve(recent_query)
        
        for other in recent_memories:
            if other.memory_id == memory.memory_id:
                continue
            
            if isinstance(other.content, str):
                # Simple overlap detection
                other_lower = other.content.lower()
                
                # Count common words (excluding common words)
                common_words = set(content_lower.split()) & set(other_lower.split())
                common_words -= {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for"}
                
                if len(common_words) > 3:
                    relation = MemoryRelation(
                        source_id=memory.memory_id,
                        target_id=other.memory_id,
                        relation_type="related_content",
                        strength=min(1.0, len(common_words) / 10),
                        metadata={"common_words": list(common_words)}
                    )
                    potential_relations.append(relation)
        
        # Store detected relationships
        for relation in potential_relations[:5]:  # Limit to top 5
            await self.update_relationship(relation)
    
    async def _apply_symbolic_filters(self, 
                                    memories: List[MemCube], 
                                    query: MemoryQuery) -> List[MemCube]:
        """Apply rule-based filtering"""
        filtered = memories
        
        # Filter by state
        if "state" in query.parameters:
            target_state = MemoryState(query.parameters["state"])
            filtered = [m for m in filtered if m.state == target_state]
        
        # Filter by priority
        if "min_priority" in query.parameters:
            min_priority = query.parameters["min_priority"]
            filtered = [m for m in filtered if m.priority_level >= min_priority]
        
        # Filter by age
        if "max_age" in query.parameters:
            max_age = query.parameters["max_age"]
            current_time = time.time()
            filtered = [m for m in filtered if current_time - m.timestamp <= max_age]
        
        # Filter by access pattern
        if query.parameters.get("only_hot"):
            # Only frequently accessed memories
            filtered = [m for m in filtered if m.access_count > 10]
        
        return filtered
    
    async def _retrieve_by_semantic_type(self, 
                                       semantic_type: str, 
                                       namespace: Tuple[str, str, str]) -> List[MemCube]:
        """Retrieve memories by semantic type using index"""
        memory_ids = self.semantic_index.get(semantic_type, set())
        
        memories = []
        for memory_id in memory_ids:
            memory = await self.vault.get_by_id(memory_id)
            if memory and memory.matches_namespace(namespace):
                memories.append(memory)
        
        return memories
    
    def _merge_candidates(self, 
                         list1: List[MemCube], 
                         list2: List[MemCube]) -> List[MemCube]:
        """Merge two lists of memories, removing duplicates"""
        seen = {m.memory_id for m in list1}
        merged = list1.copy()
        
        for memory in list2:
            if memory.memory_id not in seen:
                merged.append(memory)
                seen.add(memory.memory_id)
        
        return merged
    
    async def _expand_relationships(self, memories: List[MemCube]) -> List[MemCube]:
        """Expand to include related memories"""
        expanded = memories.copy()
        seen_ids = {m.memory_id for m in memories}
        
        for memory in memories:
            # Get related from graph
            if memory.memory_id in self.memory_graph:
                for related_id in self.memory_graph[memory.memory_id]:
                    if related_id not in seen_ids:
                        related_memory = await self.vault.get_by_id(related_id)
                        if related_memory:
                            expanded.append(related_memory)
                            seen_ids.add(related_id)
        
        return expanded
    
    def _rank_results(self, 
                     memories: List[MemCube], 
                     query: MemoryQuery) -> List[MemCube]:
        """Rank memories by multiple factors"""
        scored_memories = []
        
        for memory in memories:
            score = 0.0
            
            # Recency score
            age_hours = (time.time() - memory.timestamp) / 3600
            recency_score = 1.0 / (1.0 + age_hours / 24)  # Decay over days
            score += recency_score * 0.3
            
            # Access frequency score
            frequency_score = min(1.0, memory.access_count / 50)
            score += frequency_score * 0.2
            
            # Priority score
            priority_score = memory.priority_level / 10.0
            score += priority_score * 0.3
            
            # Semantic relevance (if available from vector search)
            # This would come from vector similarity scores
            semantic_score = 0.5  # Default
            score += semantic_score * 0.2
            
            scored_memories.append((memory, score))
        
        # Sort by score
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        
        return [memory for memory, score in scored_memories]
    
    async def get_hot_memories(self) -> List[str]:
        """Get frequently accessed memories"""
        return await self.vault.get_hot_memories()
    
    async def get_memory_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about memory relationships"""
        total_relations = sum(len(relations) for relations in self.relation_index.values())
        
        # Find most connected memories
        connection_counts = {
            memory_id: len(connections)
            for memory_id, connections in self.memory_graph.items()
        }
        
        most_connected = sorted(
            connection_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            "total_relationships": total_relations,
            "memories_with_relations": len(self.memory_graph),
            "most_connected": most_connected,
            "semantic_types": list(self.semantic_index.keys()),
            "indexed_tags": list(self.tag_index.keys())
        }
    
    def get_operator_stats(self) -> Dict[str, Any]:
        """Get operator statistics"""
        return {
            "indexed_memories": sum(len(ids) for ids in self.semantic_index.values()),
            "semantic_types": len(self.semantic_index),
            "tags": len(self.tag_index),
            "relationships": sum(len(rels) for rels in self.relation_index.values()),
            "graph_nodes": len(self.memory_graph)
        }