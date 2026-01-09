"""
Memory Lifecycle Management - Handles state transitions and memory evolution
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
from collections import defaultdict

from .core import MemCube, MemoryState, MemoryType
from .vault import MemVault

logger = logging.getLogger(__name__)


class MemLifecycle:
    """Dynamic memory lifecycle management"""
    
    def __init__(self, memory_vault: MemVault):
        self.vault = memory_vault
        
        # State machine definition
        self.state_machine = self._init_state_machine()
        
        # Lifecycle policies
        self.policies = {
            "auto_archive_days": 30,
            "auto_merge_threshold": 0.8,  # Similarity threshold
            "garbage_collection_interval": 3600,  # 1 hour
            "state_transition_cooldown": 300  # 5 minutes
        }
        
        # Tracking
        self.state_transitions = defaultdict(list)  # memory_id -> [(from_state, to_state, timestamp)]
        self.merge_candidates = defaultdict(set)    # memory_id -> {similar_memory_ids}
        
        # Background tasks
        self.background_tasks = []
    
    def _init_state_machine(self) -> Dict[MemoryState, List[MemoryState]]:
        """Initialize finite state machine for memory lifecycle"""
        return {
            MemoryState.GENERATED: [MemoryState.ACTIVATED, MemoryState.ARCHIVED],
            MemoryState.ACTIVATED: [MemoryState.MERGED, MemoryState.ARCHIVED],
            MemoryState.MERGED: [MemoryState.ACTIVATED, MemoryState.ARCHIVED],
            MemoryState.ARCHIVED: [MemoryState.ACTIVATED]  # Can be reactivated
        }
    
    async def start_background_tasks(self):
        """Start background lifecycle management tasks"""
        self.background_tasks = [
            asyncio.create_task(self._garbage_collection_loop()),
            asyncio.create_task(self._auto_archive_loop()),
            asyncio.create_task(self._merge_detection_loop()),
            asyncio.create_task(self._lifecycle_optimization_loop())
        ]
        logger.info("Lifecycle background tasks started")
    
    async def stop_background_tasks(self):
        """Stop all background tasks"""
        for task in self.background_tasks:
            task.cancel()
        
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        logger.info("Lifecycle background tasks stopped")
    
    async def transition_state(self, 
                             memory: MemCube, 
                             new_state: MemoryState,
                             reason: Optional[str] = None) -> MemCube:
        """Transition memory to new state with validation"""
        current_state = memory.state
        
        # Validate transition
        if new_state not in self.state_machine.get(current_state, []):
            raise ValueError(f"Invalid transition: {current_state} -> {new_state}")
        
        # Check cooldown
        if memory.memory_id in self.state_transitions:
            last_transition = self.state_transitions[memory.memory_id][-1]
            if time.time() - last_transition[2] < self.policies["state_transition_cooldown"]:
                logger.warning(f"Transition cooldown active for {memory.memory_id}")
                return memory
        
        # Create snapshot before transition
        await self._create_snapshot(memory)
        
        # Update state
        old_state = memory.state
        memory.transition_state(new_state)
        
        # Record transition
        self.state_transitions[memory.memory_id].append(
            (old_state, new_state, time.time(), reason)
        )
        
        # Execute state-specific actions
        await self._execute_state_actions(memory, old_state, new_state)
        
        # Store updated memory
        await self.vault.store(memory)
        
        logger.info(f"Memory {memory.memory_id} transitioned: {old_state} -> {new_state}")
        return memory
    
    async def _execute_state_actions(self, 
                                   memory: MemCube, 
                                   old_state: MemoryState,
                                   new_state: MemoryState):
        """Execute actions specific to state transitions"""
        if new_state == MemoryState.ARCHIVED:
            await self._archive_memory(memory)
            
        elif new_state == MemoryState.MERGED:
            await self._prepare_for_merge(memory)
            
        elif new_state == MemoryState.ACTIVATED and old_state == MemoryState.ARCHIVED:
            await self._reactivate_memory(memory)
    
    async def _archive_memory(self, memory: MemCube):
        """Archive memory - compress and move to cold storage"""
        # In production, would move to cheaper storage
        # Could also compress content
        memory.priority_level = max(1, memory.priority_level - 2)
        
        logger.info(f"Archived memory {memory.memory_id}")
    
    async def _prepare_for_merge(self, memory: MemCube):
        """Prepare memory for merging with similar memories"""
        # Find merge candidates
        if memory.memory_id in self.merge_candidates:
            candidates = self.merge_candidates[memory.memory_id]
            
            if candidates:
                # Perform merge
                merged = await self._merge_memories(memory, list(candidates))
                if merged:
                    # Store merged memory
                    await self.vault.store(merged)
                    
                    # Archive originals
                    for mem_id in [memory.memory_id] + list(candidates):
                        original = await self.vault.get_by_id(mem_id)
                        if original:
                            await self.transition_state(
                                original,
                                MemoryState.ARCHIVED,
                                f"Merged into {merged.memory_id}"
                            )
    
    async def _reactivate_memory(self, memory: MemCube):
        """Reactivate archived memory"""
        # Restore priority
        memory.priority_level = min(10, memory.priority_level + 2)
        
        # Reset access count to give it a chance
        memory.access_count = 1
        memory.last_access = time.time()
        
        logger.info(f"Reactivated memory {memory.memory_id}")
    
    async def _create_snapshot(self, memory: MemCube):
        """Create snapshot for rollback capability"""
        snapshot = MemCube.from_dict(memory.to_dict())
        snapshot.memory_id = f"snapshot_{memory.memory_id}_{int(time.time())}"
        snapshot.semantic_type = "snapshot"
        snapshot.priority_level = 1
        snapshot.ttl = 86400 * 7  # Keep snapshots for 7 days
        
        await self.vault.store(snapshot)
    
    async def _merge_memories(self, 
                            primary: MemCube, 
                            others: List[str]) -> Optional[MemCube]:
        """Merge similar memories into one"""
        # Load other memories
        other_memories = []
        for mem_id in others:
            mem = await self.vault.get_by_id(mem_id)
            if mem:
                other_memories.append(mem)
        
        if not other_memories:
            return None
        
        # Create merged memory
        merged_content = {
            "merged_from": [primary.memory_id] + [m.memory_id for m in other_memories],
            "primary_content": primary.content,
            "additional_content": [m.content for m in other_memories],
            "merge_timestamp": time.time()
        }
        
        # Combine metadata
        all_memories = [primary] + other_memories
        merged = MemCube(
            memory_id=f"merged_{int(time.time())}_{primary.memory_id[:8]}",
            content=merged_content,
            memory_type=primary.memory_type,
            timestamp=min(m.timestamp for m in all_memories),
            origin_signature="system_merge",
            semantic_type=primary.semantic_type,
            namespace=primary.namespace,
            access_control=primary.access_control,
            priority_level=max(m.priority_level for m in all_memories),
            compliance_tags=list(set().union(*[m.compliance_tags for m in all_memories])),
            state=MemoryState.MERGED
        )
        
        # Preserve relationships
        for mem in all_memories:
            merged.related_memories.extend(mem.related_memories)
        merged.related_memories = list(set(merged.related_memories))
        
        return merged
    
    async def _garbage_collection_loop(self):
        """Periodic garbage collection"""
        while True:
            try:
                await asyncio.sleep(self.policies["garbage_collection_interval"])
                
                collected = await self._collect_garbage()
                if collected:
                    logger.info(f"Garbage collected {collected} memories")
                    
            except Exception as e:
                logger.error(f"Error in garbage collection: {e}")
    
    async def _collect_garbage(self) -> int:
        """Collect expired and unused memories"""
        collected = 0
        
        # Query for garbage collection candidates
        # In production, would batch this
        candidates = []
        
        # Check TTL expiration
        current_time = time.time()
        for memory_id in await self.vault.get_hot_memories(threshold=0):  # Get all
            memory = await self.vault.get_by_id(memory_id)
            if memory and memory.is_expired():
                candidates.append(memory)
        
        # Archive expired memories
        for memory in candidates:
            await self.transition_state(memory, MemoryState.ARCHIVED, "TTL expired")
            collected += 1
        
        return collected
    
    async def _auto_archive_loop(self):
        """Automatically archive old, unused memories"""
        while True:
            try:
                await asyncio.sleep(86400)  # Daily
                
                archived = await self._auto_archive_old_memories()
                if archived:
                    logger.info(f"Auto-archived {archived} old memories")
                    
            except Exception as e:
                logger.error(f"Error in auto-archive: {e}")
    
    async def _auto_archive_old_memories(self) -> int:
        """Archive memories that haven't been accessed recently"""
        archived = 0
        threshold_time = time.time() - (86400 * self.policies["auto_archive_days"])
        
        # This would be more efficient with database query
        candidates = []
        
        for memory_id in await self.vault.get_hot_memories(threshold=0):
            memory = await self.vault.get_by_id(memory_id)
            if memory and memory.last_access < threshold_time and memory.state != MemoryState.ARCHIVED:
                candidates.append(memory)
        
        for memory in candidates:
            if memory.priority_level < 5:  # Don't auto-archive high priority
                await self.transition_state(memory, MemoryState.ARCHIVED, "Auto-archive due to inactivity")
                archived += 1
        
        return archived
    
    async def _merge_detection_loop(self):
        """Detect similar memories that could be merged"""
        while True:
            try:
                await asyncio.sleep(3600)  # Hourly
                
                detected = await self._detect_merge_candidates()
                if detected:
                    logger.info(f"Detected {detected} merge candidate groups")
                    
            except Exception as e:
                logger.error(f"Error in merge detection: {e}")
    
    async def _detect_merge_candidates(self) -> int:
        """Detect similar memories that could be merged"""
        # This is simplified - in production would use more sophisticated similarity
        semantic_groups = defaultdict(list)
        
        # Group by semantic type and namespace
        for memory_id in await self.vault.get_hot_memories(threshold=5):
            memory = await self.vault.get_by_id(memory_id)
            if memory and memory.state == MemoryState.ACTIVATED:
                key = (memory.semantic_type, memory.namespace)
                semantic_groups[key].append(memory)
        
        detected = 0
        for group_memories in semantic_groups.values():
            if len(group_memories) > 5:  # Many similar memories
                # Simple similarity based on timestamp proximity
                group_memories.sort(key=lambda m: m.timestamp)
                
                for i in range(len(group_memories) - 1):
                    mem1 = group_memories[i]
                    mem2 = group_memories[i + 1]
                    
                    # If created within 1 minute of each other
                    if abs(mem1.timestamp - mem2.timestamp) < 60:
                        self.merge_candidates[mem1.memory_id].add(mem2.memory_id)
                        self.merge_candidates[mem2.memory_id].add(mem1.memory_id)
                        detected += 1
        
        return detected
    
    async def _lifecycle_optimization_loop(self):
        """Optimize memory lifecycle based on patterns"""
        while True:
            try:
                await asyncio.sleep(7200)  # Every 2 hours
                
                await self._optimize_lifecycle_policies()
                
            except Exception as e:
                logger.error(f"Error in lifecycle optimization: {e}")
    
    async def _optimize_lifecycle_policies(self):
        """Adjust lifecycle policies based on usage patterns"""
        # Analyze state transition patterns
        transition_stats = defaultdict(int)
        
        for transitions in self.state_transitions.values():
            for from_state, to_state, _, _ in transitions:
                transition_stats[(from_state, to_state)] += 1
        
        # Adjust policies based on patterns
        total_transitions = sum(transition_stats.values())
        if total_transitions > 1000:
            # Check if too many memories are being archived
            archive_rate = transition_stats.get((MemoryState.ACTIVATED, MemoryState.ARCHIVED), 0) / total_transitions
            
            if archive_rate > 0.5:
                # Increase auto-archive threshold
                self.policies["auto_archive_days"] = min(90, self.policies["auto_archive_days"] + 5)
                logger.info(f"Increased auto-archive threshold to {self.policies['auto_archive_days']} days")
    
    def get_lifecycle_stats(self) -> Dict[str, Any]:
        """Get lifecycle statistics"""
        transition_counts = defaultdict(int)
        for transitions in self.state_transitions.values():
            for from_state, to_state, _, _ in transitions:
                key = f"{from_state.value}->{to_state.value}"
                transition_counts[key] += 1
        
        return {
            "total_transitions": sum(len(t) for t in self.state_transitions.values()),
            "transition_types": dict(transition_counts),
            "memories_with_transitions": len(self.state_transitions),
            "merge_candidate_groups": len(self.merge_candidates),
            "policies": self.policies
        }