"""
Advanced Memory Integration for Consciousness
Production-ready memory system with vector search, temporal indexing, and protocol synthesis
Integrates multiple memory subsystems for comprehensive experience storage
"""

import asyncio
import json
import logging
import sqlite3
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
from enum import Enum
import hashlib
import pickle
import heapq
from collections import defaultdict
import mmap
import struct

# Memory system imports
from systems.memory.memory_system import MemorySystem, Memory, MemoryType
from systems.memory.temporal_memory import TemporalMemory, TemporalIndex
from systems.memory.vector_memory import VectorMemory, VectorStore
from systems.communication.protocol_synthesis import ProtocolSynthesizer, Protocol

logger = logging.getLogger(__name__)

class MemoryImportance(Enum):
    """Memory importance levels"""
    CRITICAL = 1.0
    HIGH = 0.8
    MEDIUM = 0.5
    LOW = 0.3
    TRIVIAL = 0.1

class MemoryConsolidation(Enum):
    """Memory consolidation states"""
    IMMEDIATE = "immediate"      # Just stored
    SHORT_TERM = "short_term"   # In working memory
    CONSOLIDATING = "consolidating"  # Being processed
    LONG_TERM = "long_term"     # Permanently stored
    ARCHIVED = "archived"       # Cold storage

@dataclass
class MemoryContext:
    """Context for memory formation"""
    emotional_state: Dict[str, float]
    active_goals: List[str]
    recent_events: List[str]
    social_context: Optional[str]
    location: Optional[str]
    importance_factors: Dict[str, float]
    
@dataclass
class MemoryAssociation:
    """Association between memories"""
    source_id: str
    target_id: str
    association_type: str
    strength: float
    evidence: List[str]
    created_at: datetime

@dataclass
class MemoryCluster:
    """Cluster of related memories"""
    id: str
    theme: str
    memories: Set[str]
    centroid: Optional[np.ndarray]
    coherence: float
    last_accessed: datetime

class AdvancedMemoryIntegration:
    """Advanced memory integration system for consciousness"""
    
    def __init__(
        self,
        consciousness_id: str,
        base_path: Optional[Path] = None,
        vector_dimensions: int = 768
    ):
        self.consciousness_id = consciousness_id
        self.base_path = base_path or Path(f"data/consciousness_{consciousness_id}")
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize subsystems
        self.memory_system = MemorySystem(consciousness_id, self.base_path / "memory.db")
        self.temporal_memory = TemporalMemory(consciousness_id, self.base_path / "temporal.db")
        self.vector_memory = VectorMemory(consciousness_id, self.base_path / "vectors", vector_dimensions)
        self.protocol_synthesis = ProtocolSynthesizer(consciousness_id, self.base_path / "protocols.db")
        
        # Memory indices
        self.importance_index: Dict[str, float] = {}
        self.emotion_index: Dict[str, Dict[str, float]] = {}
        self.association_graph: Dict[str, List[MemoryAssociation]] = {}
        self.memory_clusters: Dict[str, MemoryCluster] = {}
        
        # Working memory
        self.working_memory: List[Memory] = []
        self.working_memory_capacity = 7  # Miller's magic number
        
        # Consolidation queue
        self.consolidation_queue: List[Tuple[float, str]] = []  # (priority, memory_id)
        
        # Memory statistics
        self.access_counts: Dict[str, int] = defaultdict(int)
        self.last_consolidation = datetime.utcnow()
        
        # Initialize database
        self._init_database()
        
        # Start background tasks
        self.tasks = []
        self._start_background_tasks()
        
        logger.info(f"Advanced memory integration initialized for {consciousness_id}")
        
    def _init_database(self):
        """Initialize advanced memory database"""
        db_path = self.base_path / "advanced_memory.db"
        with sqlite3.connect(db_path) as conn:
            # Memory associations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_associations (
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    association_type TEXT NOT NULL,
                    strength REAL NOT NULL,
                    evidence TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (source_id, target_id, association_type)
                )
            """)
            
            # Memory clusters table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_clusters (
                    id TEXT PRIMARY KEY,
                    theme TEXT NOT NULL,
                    memories TEXT NOT NULL,
                    centroid BLOB,
                    coherence REAL NOT NULL,
                    last_accessed TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Memory importance table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_importance (
                    memory_id TEXT PRIMARY KEY,
                    importance REAL NOT NULL,
                    factors TEXT NOT NULL,
                    calculated_at TEXT NOT NULL
                )
            """)
            
            # Memory emotions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_emotions (
                    memory_id TEXT PRIMARY KEY,
                    emotions TEXT NOT NULL,
                    intensity REAL NOT NULL,
                    recorded_at TEXT NOT NULL
                )
            """)
            
            # Create indices
            conn.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memory_importance(importance DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_associations_source ON memory_associations(source_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_associations_target ON memory_associations(target_id)")
            
    def _start_background_tasks(self):
        """Start background memory processing tasks"""
        self.tasks = [
            asyncio.create_task(self._consolidation_loop()),
            asyncio.create_task(self._clustering_loop()),
            asyncio.create_task(self._protocol_synthesis_loop()),
            asyncio.create_task(self._memory_decay_loop())
        ]
        
    async def store_memory(
        self,
        content: Any,
        memory_type: MemoryType,
        context: Optional[MemoryContext] = None,
        importance: Optional[float] = None
    ) -> Memory:
        """Store a new memory with advanced processing"""
        # Create base memory
        memory = await self.memory_system.store_memory(
            content=content,
            memory_type=memory_type,
            tags=self._generate_tags(content, context),
            metadata=self._generate_metadata(context)
        )
        
        # Calculate importance if not provided
        if importance is None:
            importance = self._calculate_importance(memory, context)
        
        # Store importance
        self.importance_index[memory.id] = importance
        self._store_importance(memory.id, importance, context)
        
        # Add to working memory if important enough
        if importance >= MemoryImportance.MEDIUM.value:
            self._add_to_working_memory(memory)
            
        # Extract and store emotions
        if context and context.emotional_state:
            self.emotion_index[memory.id] = context.emotional_state
            self._store_emotions(memory.id, context.emotional_state)
            
        # Generate vector embedding
        embedding = await self._generate_embedding(memory)
        await self.vector_memory.store_vector(memory.id, embedding, {
            'type': memory_type.value,
            'importance': importance
        })
        
        # Add temporal index
        await self.temporal_memory.add_memory(
            memory_id=memory.id,
            timestamp=memory.timestamp,
            memory_type=memory_type,
            importance=importance
        )
        
        # Find associations with existing memories
        associations = await self._find_associations(memory, embedding)
        for assoc in associations:
            self._add_association(assoc)
            
        # Queue for consolidation if important
        if importance >= MemoryImportance.HIGH.value:
            heapq.heappush(self.consolidation_queue, (-importance, memory.id))
            
        logger.info(f"Stored memory {memory.id} with importance {importance:.2f}")
        return memory
        
    async def recall_memory(
        self,
        query: str,
        context: Optional[MemoryContext] = None,
        recall_type: str = "semantic",
        limit: int = 5
    ) -> List[Tuple[Memory, float]]:
        """Recall memories using multiple strategies"""
        results = []
        
        if recall_type == "semantic":
            # Vector similarity search
            query_embedding = await self._generate_query_embedding(query)
            vector_results = await self.vector_memory.search_similar(
                query_embedding,
                limit=limit * 2  # Get more for filtering
            )
            
            # Retrieve full memories
            for vec_id, similarity in vector_results:
                memory = await self.memory_system.get_memory(vec_id)
                if memory:
                    # Adjust score based on importance and recency
                    adjusted_score = self._adjust_recall_score(
                        memory, similarity, context
                    )
                    results.append((memory, adjusted_score))
                    
        elif recall_type == "temporal":
            # Time-based recall
            temporal_results = await self.temporal_memory.get_memories_in_range(
                start_time=datetime.utcnow() - timedelta(days=7),
                end_time=datetime.utcnow(),
                memory_types=None
            )
            
            for memory_id in temporal_results[:limit]:
                memory = await self.memory_system.get_memory(memory_id)
                if memory:
                    results.append((memory, 1.0))
                    
        elif recall_type == "associative":
            # Follow association chains
            if context and context.recent_events:
                seed_memories = await self._get_recent_memories(5)
                for seed in seed_memories:
                    associated = await self._get_associated_memories(seed.id, limit=3)
                    for assoc_id, strength in associated:
                        memory = await self.memory_system.get_memory(assoc_id)
                        if memory:
                            results.append((memory, strength))
                            
        elif recall_type == "emotional":
            # Emotion-based recall
            if context and context.emotional_state:
                emotional_memories = await self._find_emotional_memories(
                    context.emotional_state,
                    limit=limit
                )
                results.extend(emotional_memories)
                
        # Sort by score and limit
        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:limit]
        
        # Update access counts
        for memory, _ in results:
            self.access_counts[memory.id] += 1
            
        return results
        
    async def consolidate_memories(self) -> int:
        """Consolidate important memories into long-term storage"""
        consolidated = 0
        
        while self.consolidation_queue and consolidated < 10:
            _, memory_id = heapq.heappop(self.consolidation_queue)
            
            memory = await self.memory_system.get_memory(memory_id)
            if not memory:
                continue
                
            # Skip if recently consolidated
            if memory.metadata.get('consolidation_state') == MemoryConsolidation.LONG_TERM.value:
                continue
                
            # Perform consolidation
            success = await self._consolidate_memory(memory)
            if success:
                consolidated += 1
                
        self.last_consolidation = datetime.utcnow()
        logger.info(f"Consolidated {consolidated} memories")
        return consolidated
        
    async def _consolidate_memory(self, memory: Memory) -> bool:
        """Consolidate a single memory"""
        try:
            # Find related memories
            embedding = await self._get_memory_embedding(memory.id)
            related = await self.vector_memory.search_similar(embedding, limit=10)
            
            # Build consolidation context
            context_memories = []
            for related_id, _ in related[1:]:  # Skip self
                related_memory = await self.memory_system.get_memory(related_id)
                if related_memory:
                    context_memories.append(related_memory)
                    
            # Generate consolidated representation
            consolidated_content = await self._generate_consolidated_content(
                memory, context_memories
            )
            
            # Update memory with consolidation
            memory.metadata['consolidation_state'] = MemoryConsolidation.LONG_TERM.value
            memory.metadata['consolidated_at'] = datetime.utcnow().isoformat()
            memory.metadata['consolidated_content'] = consolidated_content
            
            # Store updated memory
            await self.memory_system.update_memory(memory)
            
            # Create memory cluster if patterns found
            if len(context_memories) >= 3:
                cluster = await self._create_memory_cluster(
                    memory, context_memories, embedding
                )
                if cluster:
                    self.memory_clusters[cluster.id] = cluster
                    
            return True
            
        except Exception as e:
            logger.error(f"Error consolidating memory {memory.id}: {e}")
            return False
            
    async def synthesize_protocols(self) -> List[Protocol]:
        """Synthesize behavioral protocols from memory patterns"""
        # Get recent important memories
        important_memories = await self._get_important_memories(50)
        
        # Group by type and context
        memory_groups = self._group_memories_by_pattern(important_memories)
        
        protocols = []
        for pattern, memories in memory_groups.items():
            if len(memories) >= 3:  # Need sufficient examples
                # Extract common elements
                protocol = await self.protocol_synthesis.synthesize_from_memories(
                    memories,
                    pattern_hint=pattern
                )
                
                if protocol and protocol.confidence > 0.7:
                    protocols.append(protocol)
                    
        logger.info(f"Synthesized {len(protocols)} protocols from memory patterns")
        return protocols
        
    async def create_memory_summary(
        self,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        memory_types: Optional[List[MemoryType]] = None
    ) -> Dict[str, Any]:
        """Create a summary of memories in a time range"""
        if not time_range:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=1)
            time_range = (start_time, end_time)
            
        # Get memories in range
        memory_ids = await self.temporal_memory.get_memories_in_range(
            start_time=time_range[0],
            end_time=time_range[1],
            memory_types=memory_types
        )
        
        memories = []
        for memory_id in memory_ids:
            memory = await self.memory_system.get_memory(memory_id)
            if memory:
                memories.append(memory)
                
        # Generate summary statistics
        summary = {
            'time_range': {
                'start': time_range[0].isoformat(),
                'end': time_range[1].isoformat()
            },
            'total_memories': len(memories),
            'by_type': defaultdict(int),
            'important_events': [],
            'emotional_profile': defaultdict(float),
            'key_themes': [],
            'synthesized_insights': []
        }
        
        # Analyze memories
        for memory in memories:
            summary['by_type'][memory.memory_type.value] += 1
            
            # Important events
            importance = self.importance_index.get(memory.id, 0)
            if importance >= MemoryImportance.HIGH.value:
                summary['important_events'].append({
                    'memory_id': memory.id,
                    'content': str(memory.content)[:200],
                    'importance': importance,
                    'timestamp': memory.timestamp.isoformat()
                })
                
            # Emotional profile
            emotions = self.emotion_index.get(memory.id, {})
            for emotion, intensity in emotions.items():
                summary['emotional_profile'][emotion] += intensity
                
        # Normalize emotional profile
        if summary['emotional_profile']:
            total_intensity = sum(summary['emotional_profile'].values())
            for emotion in summary['emotional_profile']:
                summary['emotional_profile'][emotion] /= total_intensity
                
        # Extract themes from clusters
        active_clusters = []
        for cluster in self.memory_clusters.values():
            if any(m in memory_ids for m in cluster.memories):
                active_clusters.append(cluster)
                
        summary['key_themes'] = [
            {
                'theme': cluster.theme,
                'coherence': cluster.coherence,
                'memory_count': len(cluster.memories & set(memory_ids))
            }
            for cluster in sorted(active_clusters, key=lambda c: c.coherence, reverse=True)[:5]
        ]
        
        # Generate insights
        if len(memories) >= 10:
            insights = await self._generate_summary_insights(memories, summary)
            summary['synthesized_insights'] = insights
            
        return summary
        
    def _calculate_importance(
        self,
        memory: Memory,
        context: Optional[MemoryContext]
    ) -> float:
        """Calculate memory importance based on multiple factors"""
        importance = MemoryImportance.MEDIUM.value
        
        # Type-based importance
        type_importance = {
            MemoryType.EXPERIENCE: 0.6,
            MemoryType.INSIGHT: 0.8,
            MemoryType.GOAL: 0.7,
            MemoryType.ERROR: 0.9,
            MemoryType.SOCIAL: 0.5,
            MemoryType.CREATION: 0.7,
            MemoryType.KNOWLEDGE: 0.6
        }
        
        importance = type_importance.get(memory.memory_type, 0.5)
        
        # Context-based adjustments
        if context:
            # Emotional intensity
            if context.emotional_state:
                max_emotion = max(abs(v) for v in context.emotional_state.values())
                importance += max_emotion * 0.2
                
            # Goal relevance
            if context.active_goals:
                # Check if memory relates to active goals
                content_str = str(memory.content).lower()
                goal_relevance = sum(
                    1 for goal in context.active_goals
                    if any(word in content_str for word in goal.lower().split())
                )
                importance += min(0.3, goal_relevance * 0.1)
                
            # Explicit importance factors
            if context.importance_factors:
                for factor, weight in context.importance_factors.items():
                    if factor in str(memory.content):
                        importance += weight * 0.1
                        
        return min(1.0, max(0.1, importance))
        
    def _add_to_working_memory(self, memory: Memory):
        """Add memory to working memory with capacity management"""
        # Remove duplicates
        self.working_memory = [m for m in self.working_memory if m.id != memory.id]
        
        # Add new memory
        self.working_memory.append(memory)
        
        # Manage capacity
        if len(self.working_memory) > self.working_memory_capacity:
            # Remove least important
            self.working_memory.sort(
                key=lambda m: self.importance_index.get(m.id, 0),
                reverse=True
            )
            self.working_memory = self.working_memory[:self.working_memory_capacity]
            
    async def _find_associations(
        self,
        memory: Memory,
        embedding: np.ndarray
    ) -> List[MemoryAssociation]:
        """Find associations with existing memories"""
        associations = []
        
        # Semantic associations via embedding similarity
        similar = await self.vector_memory.search_similar(embedding, limit=20)
        
        for similar_id, similarity in similar[1:]:  # Skip self
            if similarity > 0.7:  # High similarity threshold
                similar_memory = await self.memory_system.get_memory(similar_id)
                if similar_memory:
                    # Determine association type
                    assoc_type = self._determine_association_type(
                        memory, similar_memory, similarity
                    )
                    
                    associations.append(MemoryAssociation(
                        source_id=memory.id,
                        target_id=similar_id,
                        association_type=assoc_type,
                        strength=similarity,
                        evidence=[f"Semantic similarity: {similarity:.3f}"],
                        created_at=datetime.utcnow()
                    ))
                    
        # Temporal associations
        temporal_window = timedelta(minutes=5)
        nearby_memories = await self.temporal_memory.get_memories_in_range(
            start_time=memory.timestamp - temporal_window,
            end_time=memory.timestamp + temporal_window
        )
        
        for nearby_id in nearby_memories:
            if nearby_id != memory.id and nearby_id not in [a.target_id for a in associations]:
                associations.append(MemoryAssociation(
                    source_id=memory.id,
                    target_id=nearby_id,
                    association_type="temporal",
                    strength=0.5,
                    evidence=["Temporal proximity"],
                    created_at=datetime.utcnow()
                ))
                
        return associations
        
    def _determine_association_type(
        self,
        memory1: Memory,
        memory2: Memory,
        similarity: float
    ) -> str:
        """Determine the type of association between memories"""
        # Check for causal relationship
        if memory1.timestamp < memory2.timestamp:
            time_diff = (memory2.timestamp - memory1.timestamp).total_seconds()
            if time_diff < 60 and similarity > 0.8:
                return "causal"
                
        # Check for same type
        if memory1.memory_type == memory2.memory_type:
            return "similar_type"
            
        # Check for complementary types
        complementary = {
            (MemoryType.GOAL, MemoryType.EXPERIENCE): "goal_achievement",
            (MemoryType.ERROR, MemoryType.INSIGHT): "learning",
            (MemoryType.SOCIAL, MemoryType.KNOWLEDGE): "social_learning"
        }
        
        type_pair = (memory1.memory_type, memory2.memory_type)
        if type_pair in complementary:
            return complementary[type_pair]
            
        # Default to semantic
        return "semantic"
        
    def _add_association(self, association: MemoryAssociation):
        """Add association to graph"""
        if association.source_id not in self.association_graph:
            self.association_graph[association.source_id] = []
        
        self.association_graph[association.source_id].append(association)
        
        # Store in database
        self._store_association(association)
        
    async def _get_associated_memories(
        self,
        memory_id: str,
        association_types: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Tuple[str, float]]:
        """Get memories associated with a given memory"""
        associations = self.association_graph.get(memory_id, [])
        
        # Filter by type if specified
        if association_types:
            associations = [a for a in associations if a.association_type in association_types]
            
        # Sort by strength
        associations.sort(key=lambda a: a.strength, reverse=True)
        
        return [(a.target_id, a.strength) for a in associations[:limit]]
        
    async def _consolidation_loop(self):
        """Background task for memory consolidation"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Check if consolidation needed
                if self.consolidation_queue:
                    await self.consolidate_memories()
                    
            except Exception as e:
                logger.error(f"Error in consolidation loop: {e}")
                
    async def _clustering_loop(self):
        """Background task for memory clustering"""
        while True:
            try:
                await asyncio.sleep(1800)  # Every 30 minutes
                
                # Get recent vectors
                recent_vectors = await self.vector_memory.get_recent_vectors(100)
                
                if len(recent_vectors) >= 10:
                    # Perform clustering
                    clusters = await self._perform_clustering(recent_vectors)
                    
                    # Update clusters
                    for cluster in clusters:
                        self.memory_clusters[cluster.id] = cluster
                        self._store_cluster(cluster)
                        
            except Exception as e:
                logger.error(f"Error in clustering loop: {e}")
                
    async def _protocol_synthesis_loop(self):
        """Background task for protocol synthesis"""
        while True:
            try:
                await asyncio.sleep(3600)  # Every hour
                
                # Synthesize new protocols
                protocols = await self.synthesize_protocols()
                
                # Store successful protocols
                for protocol in protocols:
                    await self.protocol_synthesis.store_protocol(protocol)
                    
            except Exception as e:
                logger.error(f"Error in protocol synthesis loop: {e}")
                
    async def _memory_decay_loop(self):
        """Background task for memory decay and cleanup"""
        while True:
            try:
                await asyncio.sleep(86400)  # Daily
                
                # Apply memory decay
                decayed_count = await self._apply_memory_decay()
                
                # Archive old memories
                archived_count = await self._archive_old_memories()
                
                logger.info(f"Memory maintenance: {decayed_count} decayed, {archived_count} archived")
                
            except Exception as e:
                logger.error(f"Error in memory decay loop: {e}")
                
    async def _apply_memory_decay(self) -> int:
        """Apply decay to memory importance based on access patterns"""
        decayed = 0
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        for memory_id, importance in list(self.importance_index.items()):
            memory = await self.memory_system.get_memory(memory_id)
            
            if not memory:
                continue
                
            # Check last access
            last_access = memory.metadata.get('last_accessed', memory.timestamp)
            if isinstance(last_access, str):
                last_access = datetime.fromisoformat(last_access)
                
            if last_access < cutoff_date:
                # Apply decay based on time and access count
                access_count = self.access_counts.get(memory_id, 0)
                decay_factor = 0.9 if access_count > 5 else 0.7
                
                new_importance = importance * decay_factor
                
                if new_importance < MemoryImportance.TRIVIAL.value:
                    # Mark for archival
                    memory.metadata['consolidation_state'] = MemoryConsolidation.ARCHIVED.value
                    await self.memory_system.update_memory(memory)
                    decayed += 1
                else:
                    self.importance_index[memory_id] = new_importance
                    self._store_importance(memory_id, new_importance, None)
                    
        return decayed
        
    async def _archive_old_memories(self) -> int:
        """Archive memories marked for archival"""
        archived = 0
        
        # This would typically move to cold storage
        # For now, just mark as archived
        all_memories = await self.memory_system.get_all_memories(limit=1000)
        
        for memory in all_memories:
            if memory.metadata.get('consolidation_state') == MemoryConsolidation.ARCHIVED.value:
                # Remove from active indices
                self.importance_index.pop(memory.id, None)
                self.emotion_index.pop(memory.id, None)
                self.access_counts.pop(memory.id, None)
                
                archived += 1
                
        return archived
        
    # Helper methods for embedding generation (would integrate with LLM)
    async def _generate_embedding(self, memory: Memory) -> np.ndarray:
        """Generate vector embedding for memory"""
        # In production, this would use the LLM's embedding model
        # For now, create a deterministic embedding based on content
        content_str = json.dumps(memory.content, sort_keys=True)
        hash_digest = hashlib.sha256(content_str.encode()).digest()
        
        # Convert to normalized vector
        embedding = np.frombuffer(hash_digest, dtype=np.float32)
        embedding = np.tile(embedding, (768 // len(embedding)) + 1)[:768]
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
        
    async def _generate_query_embedding(self, query: str) -> np.ndarray:
        """Generate embedding for query"""
        # Similar to memory embedding
        hash_digest = hashlib.sha256(query.encode()).digest()
        embedding = np.frombuffer(hash_digest, dtype=np.float32)
        embedding = np.tile(embedding, (768 // len(embedding)) + 1)[:768]
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
        
    async def _get_memory_embedding(self, memory_id: str) -> Optional[np.ndarray]:
        """Get existing embedding for memory"""
        return await self.vector_memory.get_vector(memory_id)
        
    # Database storage methods
    def _store_importance(
        self,
        memory_id: str,
        importance: float,
        context: Optional[MemoryContext]
    ):
        """Store memory importance in database"""
        factors = {}
        if context and context.importance_factors:
            factors = context.importance_factors
            
        with sqlite3.connect(self.base_path / "advanced_memory.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memory_importance
                (memory_id, importance, factors, calculated_at)
                VALUES (?, ?, ?, ?)
            """, (
                memory_id,
                importance,
                json.dumps(factors),
                datetime.utcnow().isoformat()
            ))
            
    def _store_emotions(self, memory_id: str, emotions: Dict[str, float]):
        """Store memory emotions in database"""
        intensity = sum(abs(v) for v in emotions.values()) / len(emotions)
        
        with sqlite3.connect(self.base_path / "advanced_memory.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memory_emotions
                (memory_id, emotions, intensity, recorded_at)
                VALUES (?, ?, ?, ?)
            """, (
                memory_id,
                json.dumps(emotions),
                intensity,
                datetime.utcnow().isoformat()
            ))
            
    def _store_association(self, association: MemoryAssociation):
        """Store memory association in database"""
        with sqlite3.connect(self.base_path / "advanced_memory.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memory_associations
                (source_id, target_id, association_type, strength, evidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                association.source_id,
                association.target_id,
                association.association_type,
                association.strength,
                json.dumps(association.evidence),
                association.created_at.isoformat()
            ))
            
    def _store_cluster(self, cluster: MemoryCluster):
        """Store memory cluster in database"""
        with sqlite3.connect(self.base_path / "advanced_memory.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memory_clusters
                (id, theme, memories, centroid, coherence, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                cluster.id,
                cluster.theme,
                json.dumps(list(cluster.memories)),
                pickle.dumps(cluster.centroid) if cluster.centroid is not None else None,
                cluster.coherence,
                cluster.last_accessed.isoformat()
            ))
            
    # Additional helper methods
    def _generate_tags(self, content: Any, context: Optional[MemoryContext]) -> List[str]:
        """Generate tags for memory"""
        tags = []
        
        # Extract from content
        if isinstance(content, dict):
            tags.extend(content.keys())
        elif isinstance(content, str):
            # Simple keyword extraction
            words = content.lower().split()
            tags.extend([w for w in words if len(w) > 5][:5])
            
        # Add context tags
        if context:
            if context.active_goals:
                tags.append("goal_related")
            if context.social_context:
                tags.append(f"social_{context.social_context}")
            if context.location:
                tags.append(f"location_{context.location}")
                
        return list(set(tags))
        
    def _generate_metadata(self, context: Optional[MemoryContext]) -> Dict[str, Any]:
        """Generate metadata for memory"""
        metadata = {
            'created_at': datetime.utcnow().isoformat(),
            'consolidation_state': MemoryConsolidation.IMMEDIATE.value
        }
        
        if context:
            if context.emotional_state:
                metadata['emotional_context'] = context.emotional_state
            if context.active_goals:
                metadata['active_goals'] = context.active_goals
            if context.recent_events:
                metadata['recent_events'] = context.recent_events[:5]
                
        return metadata
        
    async def shutdown(self):
        """Shutdown memory integration"""
        # Cancel background tasks
        for task in self.tasks:
            task.cancel()
            
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Shutdown subsystems
        await self.memory_system.close()
        await self.temporal_memory.close()
        await self.vector_memory.close()
        
        logger.info("Advanced memory integration shutdown complete")
        
    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        return {
            'total_memories': len(self.importance_index),
            'working_memory_size': len(self.working_memory),
            'consolidation_queue_size': len(self.consolidation_queue),
            'memory_clusters': len(self.memory_clusters),
            'total_associations': sum(len(assocs) for assocs in self.association_graph.values()),
            'last_consolidation': self.last_consolidation.isoformat() if self.last_consolidation else None,
            'subsystem_stats': {
                'memory_system': self.memory_system.get_stats(),
                'temporal_memory': self.temporal_memory.get_stats(),
                'vector_memory': self.vector_memory.get_stats()
            }
        }

# Helper functions for consciousness integration
async def integrate_advanced_memory(consciousness):
    """Integrate advanced memory system with consciousness"""
    memory_integration = AdvancedMemoryIntegration(consciousness.id)
    
    # Add to consciousness
    consciousness.advanced_memory = memory_integration
    
    # Add convenience methods
    consciousness.store_experience = lambda content, context=None: memory_integration.store_memory(
        content, MemoryType.EXPERIENCE, context
    )
    consciousness.store_insight = lambda content, context=None: memory_integration.store_memory(
        content, MemoryType.INSIGHT, context
    )
    consciousness.recall = memory_integration.recall_memory
    consciousness.get_memory_summary = memory_integration.create_memory_summary
    
    return memory_integration