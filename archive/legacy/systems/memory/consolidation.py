"""
Memory Consolidation
Merges similar memories, summarizes long-term memories, compresses old memories
"""

import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json

from .core import MemCube, MemoryType, MemoryState
from .vault import MemVault

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationResult:
    """Result of memory consolidation operation"""
    original_count: int
    consolidated_count: int
    merged_memories: List[Tuple[List[str], str]]  # (original_ids, new_id)
    summarized_memories: List[Tuple[str, str]]  # (original_id, new_id)
    compressed_memories: List[str]  # memory_ids
    total_tokens_saved: int = 0


class MemoryConsolidator:
    """
    Consolidates memories by:
    - Merging similar/duplicate memories
    - Summarizing long-term memories
    - Compressing old memories
    """
    
    def __init__(
        self,
        vault: MemVault,
        similarity_threshold: float = 0.8,
        summary_age_days: int = 90,
        compression_age_days: int = 365
    ):
        """
        Initialize consolidator
        
        Args:
            vault: Memory vault instance
            similarity_threshold: Threshold for considering memories similar (0-1)
            summary_age_days: Age in days to summarize memories (default: 90)
            compression_age_days: Age in days to compress memories (default: 365)
        """
        self.vault = vault
        self.similarity_threshold = similarity_threshold
        self.summary_age_days = summary_age_days * 24 * 3600
        self.compression_age_days = compression_age_days * 24 * 3600
    
    async def consolidate_namespace(
        self,
        namespace: Tuple[str, str, str],
        merge_similar: bool = True,
        summarize_old: bool = True,
        compress_very_old: bool = True
    ) -> ConsolidationResult:
        """
        Consolidate memories in a namespace
        
        Args:
            namespace: Namespace to consolidate
            merge_similar: Whether to merge similar memories
            summarize_old: Whether to summarize old memories
            compress_very_old: Whether to compress very old memories
            
        Returns:
            ConsolidationResult with statistics
        """
        from .core import MemoryQuery
        
        # Retrieve all memories in namespace
        query = MemoryQuery(
            query_type="hybrid",
            parameters={"limit": 10000},  # Get all
            namespace=namespace,
            requester_id="system"
        )
        
        memories = await self.vault.retrieve(query)
        original_count = len(memories)
        
        result = ConsolidationResult(
            original_count=original_count,
            consolidated_count=original_count,
            merged_memories=[],
            summarized_memories=[],
            compressed_memories=[]
        )
        
        current_time = time.time()
        
        # Group memories by type for processing
        plaintext_memories = [m for m in memories if m.memory_type == MemoryType.PLAINTEXT]
        
        if merge_similar:
            merged = await self._merge_similar_memories(plaintext_memories)
            result.merged_memories.extend(merged)
            result.consolidated_count -= sum(len(ids) - 1 for ids, _ in merged)
        
        if summarize_old:
            old_memories = [
                m for m in plaintext_memories
                if (current_time - m.timestamp) > self.summary_age_days
                and m.state != MemoryState.ARCHIVED
            ]
            summarized = await self._summarize_memories(old_memories)
            result.summarized_memories.extend(summarized)
        
        if compress_very_old:
            very_old = [
                m for m in plaintext_memories
                if (current_time - m.timestamp) > self.compression_age_days
            ]
            compressed = await self._compress_memories(very_old)
            result.compressed_memories.extend(compressed)
        
        logger.info(
            f"Consolidated namespace {namespace}: "
            f"{original_count} -> {result.consolidated_count} memories "
            f"({len(result.merged_memories)} merged, "
            f"{len(result.summarized_memories)} summarized, "
            f"{len(result.compressed_memories)} compressed)"
        )
        
        return result
    
    async def _merge_similar_memories(
        self,
        memories: List[MemCube]
    ) -> List[Tuple[List[str], str]]:
        """Merge similar memories into single memories"""
        merged = []
        processed = set()
        
        for i, mem1 in enumerate(memories):
            if mem1.memory_id in processed:
                continue
            
            similar_group = [mem1.memory_id]
            processed.add(mem1.memory_id)
            
            # Find similar memories
            for mem2 in memories[i+1:]:
                if mem2.memory_id in processed:
                    continue
                
                similarity = self._calculate_similarity(mem1, mem2)
                if similarity >= self.similarity_threshold:
                    similar_group.append(mem2.memory_id)
                    processed.add(mem2.memory_id)
            
            # Merge if we found similar memories
            if len(similar_group) > 1:
                merged_id = await self._merge_memory_group(
                    [m for m in memories if m.memory_id in similar_group]
                )
                merged.append((similar_group, merged_id))
        
        return merged
    
    def _calculate_similarity(self, mem1: MemCube, mem2: MemCube) -> float:
        """Calculate similarity between two memories (0-1)"""
        # Simple similarity: compare content strings
        # In production, would use embeddings or more sophisticated methods
        
        content1 = str(mem1.content).lower() if mem1.content else ""
        content2 = str(mem2.content).lower() if mem2.content else ""
        
        if not content1 or not content2:
            return 0.0
        
        # Jaccard similarity of word sets
        words1 = set(content1.split())
        words2 = set(content2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        jaccard = intersection / union if union > 0 else 0.0
        
        # Boost if same semantic type
        if mem1.semantic_type == mem2.semantic_type:
            jaccard += 0.1
        
        # Boost if same namespace context
        if mem1.namespace[1] == mem2.namespace[1]:
            jaccard += 0.05
        
        return min(1.0, jaccard)
    
    async def _merge_memory_group(self, memories: List[MemCube]) -> str:
        """Merge a group of similar memories into one"""
        if len(memories) == 0:
            return None
        
        if len(memories) == 1:
            return memories[0].memory_id
        
        # Use highest priority memory as base
        base_memory = max(memories, key=lambda m: m.priority_level)
        
        # Combine content
        contents = []
        for mem in sorted(memories, key=lambda m: m.timestamp):
            content_str = str(mem.content)
            if content_str and content_str not in contents:
                contents.append(content_str)
        
        merged_content = "\n\n".join(contents)
        
        # Update base memory with merged content
        base_memory.content = merged_content
        base_memory.priority_level = max(m.priority_level for m in memories)
        
        # Add all related memory IDs
        all_related = set()
        for mem in memories:
            all_related.add(mem.memory_id)
            if mem.related_memories:
                all_related.update(mem.related_memories)
        
        base_memory.related_memories = list(all_related)
        base_memory.version_chain.extend([m.memory_id for m in memories if m.memory_id != base_memory.memory_id])
        
        # Store merged memory
        await self.vault.store(base_memory)
        
        # Archive original memories (except base)
        for mem in memories:
            if mem.memory_id != base_memory.memory_id:
                mem.state = MemoryState.ARCHIVED
                await self.vault.store(mem)  # Update state
        
        return base_memory.memory_id
    
    async def _summarize_memories(
        self,
        memories: List[MemCube]
    ) -> List[Tuple[str, str]]:
        """Summarize old memories"""
        # This would use an LLM to summarize, but for now we'll do simple truncation
        summarized = []
        
        for memory in memories:
            content = str(memory.content)
            
            # Simple summarization: truncate to first 500 chars + "..." if longer
            if len(content) > 500:
                original_id = memory.memory_id
                
                # Create summary version
                summary_content = content[:500] + "... (truncated, original preserved in version chain)"
                
                # Update memory
                memory.content = summary_content
                memory.state = MemoryState.ARCHIVED
                
                await self.vault.store(memory)
                summarized.append((original_id, memory.memory_id))
        
        return summarized
    
    async def _compress_memories(self, memories: List[MemCube]) -> List[str]:
        """Compress very old memories"""
        compressed = []
        
        for memory in memories:
            # Mark as archived (compressed)
            memory.state = MemoryState.ARCHIVED
            
            # Optionally reduce content size
            content = str(memory.content)
            if len(content) > 200:
                memory.content = content[:200] + "... (compressed)"
            
            await self.vault.store(memory)
            compressed.append(memory.memory_id)
        
        return compressed
    
    async def consolidate_by_age(
        self,
        age_days: int,
        namespace: Optional[Tuple[str, str, str]] = None
    ) -> ConsolidationResult:
        """
        Consolidate memories older than specified age
        
        Args:
            age_days: Age threshold in days
            namespace: Optional namespace filter
            
        Returns:
            ConsolidationResult
        """
        from .core import MemoryQuery
        
        # Get all memories
        query = MemoryQuery(
            query_type="temporal",
            parameters={
                "before": time.time() - (age_days * 24 * 3600),
                "limit": 10000
            },
            namespace=namespace or ("*", "*", "*"),
            requester_id="system"
        )
        
        memories = await self.vault.retrieve(query)
        
        # Group by namespace if not specified
        if namespace:
            return await self.consolidate_namespace(namespace)
        else:
            # Consolidate each namespace separately
            namespaces = set(m.namespace for m in memories)
            total_result = ConsolidationResult(
                original_count=len(memories),
                consolidated_count=0,
                merged_memories=[],
                summarized_memories=[],
                compressed_memories=[]
            )
            
            for ns in namespaces:
                ns_memories = [m for m in memories if m.namespace == ns]
                if ns_memories:
                    ns_result = await self.consolidate_namespace(ns)
                    total_result.merged_memories.extend(ns_result.merged_memories)
                    total_result.summarized_memories.extend(ns_result.summarized_memories)
                    total_result.compressed_memories.extend(ns_result.compressed_memories)
                    total_result.consolidated_count += ns_result.consolidated_count
            
            return total_result

