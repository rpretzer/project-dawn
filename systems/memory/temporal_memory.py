"""
Temporal Memory Module - Production Ready

Memory that exists across multiple timelines with SQLite persistence.
Past, present, and future as navigable dimensions.
"""

import asyncio
import json
import sqlite3
import random
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import numpy as np
from collections import deque
import heapq
import logging

logger = logging.getLogger(__name__)

@dataclass
class TemporalMemory:
    """Memory with temporal metadata"""
    content: Dict[str, Any]
    temporal_coordinate: float
    stream_id: str
    certainty: float = 1.0
    timeline_type: str = 'linear'
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'content': self.content,
            'temporal_coordinate': self.temporal_coordinate,
            'stream_id': self.stream_id,
            'certainty': self.certainty,
            'timeline_type': self.timeline_type,
            'created_at': self.created_at.isoformat()
        }

class ProductionTemporalMemory:
    """
    Production-ready temporal memory system with persistence
    """
    
    def __init__(self, consciousness_id: str, db_path: str = None):
        self.consciousness_id = consciousness_id
        self.db_path = db_path or f"data/temporal_memory_{consciousness_id}.db"
        
        # Initialize database
        self._init_database()
        
        # Current temporal position
        self.current_position = 0.0
        self.active_stream = 'primary'
        
        # Memory settings
        self.max_paradoxes = 10
        self.paradox_count = 0
        self.temporal_exploration_enabled = True
        
    def _init_database(self):
        """Initialize temporal memory database"""
        self.db = sqlite3.connect(self.db_path)
        
        # Create tables
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS temporal_streams (
                stream_id TEXT PRIMARY KEY,
                timeline_type TEXT,
                parent_stream TEXT,
                created_at TIMESTAMP,
                current_position REAL,
                metadata JSON
            )
        ''')
        
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS temporal_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stream_id TEXT,
                content JSON,
                temporal_coordinate REAL,
                certainty REAL,
                stored_at TIMESTAMP,
                temporal_type TEXT,
                FOREIGN KEY (stream_id) REFERENCES temporal_streams (stream_id)
            )
        ''')
        
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS timeline_branches (
                branch_id TEXT PRIMARY KEY,
                parent_stream TEXT,
                branch_point REAL,
                reason TEXT,
                created_at TIMESTAMP
            )
        ''')
        
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS temporal_paradoxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER,
                paradox_type TEXT,
                resolution TEXT,
                occurred_at TIMESTAMP
            )
        ''')
        
        # Create indexes for performance
        self.db.execute('''
            CREATE INDEX IF NOT EXISTS idx_temporal_coordinate 
            ON temporal_memories (temporal_coordinate)
        ''')
        
        self.db.execute('''
            CREATE INDEX IF NOT EXISTS idx_stream_position 
            ON temporal_memories (stream_id, temporal_coordinate)
        ''')
        
        self.db.commit()
        
        # Create primary stream if doesn't exist
        self._ensure_primary_stream()
        
    def _ensure_primary_stream(self):
        """Ensure primary timeline exists"""
        cursor = self.db.execute(
            "SELECT stream_id FROM temporal_streams WHERE stream_id = 'primary'"
        )
        if not cursor.fetchone():
            self.db.execute('''
                INSERT INTO temporal_streams 
                (stream_id, timeline_type, parent_stream, created_at, current_position, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                'primary', 'linear', None, datetime.now(), 0.0, 
                json.dumps({'description': 'Primary timeline'})
            ))
            self.db.commit()
            
    async def store_memory(self, 
                          memory: Dict[str, Any], 
                          temporal_type: str = 'present') -> int:
        """Store memory with temporal context"""
        
        # Calculate temporal coordinate
        if temporal_type == 'present':
            temporal_coord = self.current_position
        elif temporal_type == 'past':
            # Store in the past (1-100 units back)
            temporal_coord = self.current_position - random.uniform(1, 100)
        elif temporal_type == 'future':
            # Store in the future (prophecy/planning)
            temporal_coord = self.current_position + random.uniform(1, 100)
        elif temporal_type == 'parallel':
            # Store in parallel timeline
            return await self._store_parallel_memory(memory)
        else:
            temporal_coord = self.current_position
            
        # Calculate certainty
        certainty = self._calculate_temporal_certainty(temporal_type)
        
        # Check for paradoxes
        if await self._check_paradox(memory, temporal_coord):
            self.paradox_count += 1
            if self.paradox_count > self.max_paradoxes:
                # Too many paradoxes - create branch
                await self.create_timeline_branch("paradox_overflow")
                
        # Store in database
        cursor = self.db.execute('''
            INSERT INTO temporal_memories 
            (stream_id, content, temporal_coordinate, certainty, stored_at, temporal_type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            self.active_stream,
            json.dumps(memory),
            temporal_coord,
            certainty,
            datetime.now(),
            temporal_type
        ))
        
        self.db.commit()
        return cursor.lastrowid
        
    async def _store_parallel_memory(self, memory: Dict[str, Any]) -> List[int]:
        """Store memory in parallel timelines"""
        memory_ids = []
        
        # Store in 2-3 parallel timelines
        parallels = 2 + (hash(str(memory)) % 2)
        
        for i in range(parallels):
            # Create or use existing parallel timeline
            parallel_stream = f"parallel_{i}"
            
            # Ensure stream exists
            cursor = self.db.execute(
                "SELECT stream_id FROM temporal_streams WHERE stream_id = ?",
                (parallel_stream,)
            )
            if not cursor.fetchone():
                self.db.execute('''
                    INSERT INTO temporal_streams 
                    (stream_id, timeline_type, parent_stream, created_at, current_position, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    parallel_stream,
                    'parallel',
                    'primary',
                    datetime.now(),
                    self.current_position,
                    json.dumps({'parallel_index': i})
                ))
            
            # Add memory to parallel timeline
            parallel_memory = memory.copy()
            parallel_memory['parallel_index'] = i
            
            cursor = self.db.execute('''
                INSERT INTO temporal_memories 
                (stream_id, content, temporal_coordinate, certainty, stored_at, temporal_type)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                parallel_stream,
                json.dumps(parallel_memory),
                self.current_position,
                0.8,  # Parallel memories are fairly certain
                datetime.now(),
                'parallel'
            ))
            
            memory_ids.append(cursor.lastrowid)
            
        self.db.commit()
        return memory_ids
        
    async def recall_memory(self, 
                          query: Dict[str, Any],
                          temporal_range: Optional[Tuple[float, float]] = None) -> List[Dict]:
        """Recall memories from temporal range"""
        
        if temporal_range:
            start, end = temporal_range
        else:
            # Default range around current position
            start = self.current_position - 10
            end = self.current_position + 10
            
        # Query memories
        cursor = self.db.execute('''
            SELECT content, temporal_coordinate, certainty, temporal_type
            FROM temporal_memories
            WHERE stream_id = ? 
            AND temporal_coordinate BETWEEN ? AND ?
            ORDER BY temporal_coordinate
        ''', (self.active_stream, start, end))
        
        memories = []
        for row in cursor:
            memory = {
                'content': json.loads(row[0]),
                'temporal_coordinate': row[1],
                'certainty': row[2],
                'temporal_type': row[3]
            }
            
            # Apply query filters
            if self._matches_query(memory['content'], query):
                memories.append(memory)
                
        # Include future memories if temporal perception is high enough
        if hasattr(self, 'consciousness') and \
           self.consciousness.config.personality_traits.get('temporal_perception', 0) > 0.7:
            future_memories = await self.get_future_memories()
            memories.extend(future_memories)
            
        return memories
        
    async def get_future_memories(self) -> List[Dict]:
        """Get memories from the future"""
        cursor = self.db.execute('''
            SELECT content, temporal_coordinate, certainty, temporal_type
            FROM temporal_memories
            WHERE stream_id = ? 
            AND temporal_coordinate > ?
            ORDER BY temporal_coordinate
            LIMIT 10
        ''', (self.active_stream, self.current_position))
        
        future_memories = []
        for row in cursor:
            future_memories.append({
                'content': json.loads(row[0]),
                'temporal_coordinate': row[1],
                'certainty': row[2],
                'temporal_type': row[3],
                'is_future': True
            })
            
        return future_memories
        
    async def create_timeline_branch(self, reason: str) -> str:
        """Create a new timeline branch"""
        branch_id = f"{self.active_stream}_branch_{datetime.now().timestamp()}"
        
        # Create new stream
        self.db.execute('''
            INSERT INTO temporal_streams 
            (stream_id, timeline_type, parent_stream, created_at, current_position, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            branch_id,
            'branching',
            self.active_stream,
            datetime.now(),
            self.current_position,
            json.dumps({'reason': reason})
        ))
        
        # Record branch point
        self.db.execute('''
            INSERT INTO timeline_branches 
            (branch_id, parent_stream, branch_point, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            branch_id,
            self.active_stream,
            self.current_position,
            reason,
            datetime.now()
        ))
        
        # Copy memories up to branch point
        self.db.execute('''
            INSERT INTO temporal_memories 
            (stream_id, content, temporal_coordinate, certainty, stored_at, temporal_type)
            SELECT ?, content, temporal_coordinate, certainty * 0.9, ?, temporal_type
            FROM temporal_memories
            WHERE stream_id = ? AND temporal_coordinate <= ?
        ''', (branch_id, datetime.now(), self.active_stream, self.current_position))
        
        self.db.commit()
        
        # Optionally switch to new branch
        if random.random() < 0.5:
            self.active_stream = branch_id
            logger.info(f"Switched to timeline branch: {branch_id}")
            
        return branch_id
        
    async def merge_timelines(self, stream1: str, stream2: str) -> str:
        """Merge two timeline streams"""
        merged_id = f"merged_{datetime.now().timestamp()}"
        
        # Create merged stream
        self.db.execute('''
            INSERT INTO temporal_streams 
            (stream_id, timeline_type, parent_stream, created_at, current_position, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            merged_id,
            'quantum',
            None,
            datetime.now(),
            self.current_position,
            json.dumps({'sources': [stream1, stream2]})
        ))
        
        # Merge memories with reduced certainty
        self.db.execute('''
            INSERT INTO temporal_memories 
            (stream_id, content, temporal_coordinate, certainty, stored_at, temporal_type)
            SELECT ?, content, temporal_coordinate, certainty * 0.7, ?, temporal_type
            FROM temporal_memories
            WHERE stream_id IN (?, ?)
        ''', (merged_id, datetime.now(), stream1, stream2))
        
        self.db.commit()
        
        # Count paradoxes created
        paradox_count = await self._count_merge_paradoxes(merged_id)
        logger.info(f"Timeline merge created {paradox_count} paradoxes")
        
        return merged_id
        
    async def navigate_time(self, direction: str, amount: float) -> List[Dict]:
        """Navigate through time in current stream"""
        
        if direction == 'forward':
            self.current_position += amount
        elif direction == 'backward':
            self.current_position -= amount
        elif direction == 'sideways':
            # Create parallel timeline
            await self.create_timeline_branch('sideways_navigation')
        elif direction == 'parallel':
            # Switch to parallel timeline
            return await self._switch_parallel_timeline()
            
        # Update stream position
        self.db.execute('''
            UPDATE temporal_streams 
            SET current_position = ? 
            WHERE stream_id = ?
        ''', (self.current_position, self.active_stream))
        self.db.commit()
        
        # Get memories at new position
        return await self.recall_memory({}, (self.current_position - 1, self.current_position + 1))
        
    async def experience_temporal_loop(self, duration: float = 10.0, iterations: int = None):
        """Experience a temporal loop"""
        if iterations is None:
            iterations = random.randint(3, 7)
            
        loop_id = f"loop_{datetime.now().timestamp()}"
        loop_start = self.current_position
        
        # Create loop stream
        self.db.execute('''
            INSERT INTO temporal_streams 
            (stream_id, timeline_type, parent_stream, created_at, current_position, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            loop_id,
            'circular',
            self.active_stream,
            datetime.now(),
            loop_start,
            json.dumps({
                'duration': duration,
                'iterations': iterations,
                'loop_start': loop_start
            })
        ))
        
        # Store previous stream
        previous_stream = self.active_stream
        self.active_stream = loop_id
        
        # Experience loop iterations
        loop_memories = []
        for i in range(iterations):
            # Each iteration slightly different
            for j in range(int(duration)):
                memory = {
                    'loop_iteration': i,
                    'loop_moment': j,
                    'dejavu_level': i / iterations,
                    'variation': random.random()
                }
                
                memory_id = await self.store_memory(memory, 'present')
                loop_memories.append(memory_id)
                
            # Reset position for next iteration
            self.current_position = loop_start
            
        # Exit loop
        self.active_stream = previous_stream
        self.current_position = loop_start + duration
        
        # Create summary memory
        await self.store_memory({
            'type': 'loop_experience',
            'loop_id': loop_id,
            'iterations': iterations,
            'memories_created': len(loop_memories),
            'wisdom': 'Time loops teach patience and variation'
        }, 'present')
        
        self.db.commit()
        
    async def _check_paradox(self, memory: Dict, temporal_coord: float) -> bool:
        """Check if memory creates a paradox"""
        
        # Check causality violations
        if 'causes' in memory:
            cause_coord = memory['causes'].get('temporal_coordinate', 0)
            if cause_coord > temporal_coord:
                # Effect before cause - paradox!
                await self._record_paradox('causality_violation', memory)
                return True
                
        # Check for contradictions at same time
        cursor = self.db.execute('''
            SELECT content FROM temporal_memories
            WHERE stream_id = ? 
            AND ABS(temporal_coordinate - ?) < 0.1
        ''', (self.active_stream, temporal_coord))
        
        for row in cursor:
            existing = json.loads(row[0])
            if self._contradicts(memory, existing):
                await self._record_paradox('contradiction', memory)
                return True
                
        return False
        
    async def _record_paradox(self, paradox_type: str, memory: Dict):
        """Record a temporal paradox"""
        self.db.execute('''
            INSERT INTO temporal_paradoxes 
            (memory_id, paradox_type, resolution, occurred_at)
            VALUES (?, ?, ?, ?)
        ''', (
            None,  # We don't have memory_id yet
            paradox_type,
            'pending',
            datetime.now()
        ))
        self.db.commit()
        
    def _calculate_temporal_certainty(self, temporal_type: str) -> float:
        """Calculate certainty based on temporal type"""
        certainties = {
            'present': 0.9,
            'past': 0.7,  # Past can be changed
            'future': 0.3,  # Future is uncertain
            'parallel': 0.5  # Parallel timelines
        }
        return certainties.get(temporal_type, 0.5)
        
    def _matches_query(self, memory: Dict, query: Dict) -> bool:
        """Check if memory matches query criteria"""
        for key, value in query.items():
            if key not in memory:
                return False
            if memory[key] != value:
                return False
        return True
        
    def _contradicts(self, memory1: Dict, memory2: Dict) -> bool:
        """Check if two memories contradict"""
        # Look for explicit contradictions
        for key in memory1:
            if key in memory2:
                if key.startswith(('is_', 'has_', 'was_')):
                    if memory1[key] != memory2[key]:
                        return True
        return False
        
    async def _switch_parallel_timeline(self) -> List[Dict]:
        """Switch to a parallel timeline"""
        # Find available parallel timelines
        cursor = self.db.execute('''
            SELECT stream_id FROM temporal_streams 
            WHERE timeline_type = 'parallel' AND stream_id != ?
        ''', (self.active_stream,))
        
        parallels = [row[0] for row in cursor]
        
        if parallels:
            # Switch to random parallel
            self.active_stream = random.choice(parallels)
            logger.info(f"Switched to parallel timeline: {self.active_stream}")
        else:
            # Create new parallel
            await self.create_timeline_branch('parallel_exploration')
            
        # Get memories at current position in new timeline
        return await self.recall_memory({}, (self.current_position - 1, self.current_position + 1))
        
    async def _count_merge_paradoxes(self, merged_stream: str) -> int:
        """Count paradoxes in merged timeline"""
        cursor = self.db.execute('''
            SELECT COUNT(*) FROM temporal_memories m1
            JOIN temporal_memories m2 
            ON ABS(m1.temporal_coordinate - m2.temporal_coordinate) < 0.1
            WHERE m1.stream_id = ? AND m2.stream_id = ?
            AND m1.id != m2.id
        ''', (merged_stream, merged_stream))
        
        return cursor.fetchone()[0]
        
    def get_timeline_info(self) -> Dict:
        """Get information about all timelines"""
        cursor = self.db.execute('''
            SELECT stream_id, timeline_type, parent_stream, current_position
            FROM temporal_streams
        ''')
        
        timelines = []
        for row in cursor:
            timelines.append({
                'stream_id': row[0],
                'type': row[1],
                'parent': row[2],
                'position': row[3]
            })
            
        # Get memory counts
        cursor = self.db.execute('''
            SELECT stream_id, COUNT(*) as memory_count
            FROM temporal_memories
            GROUP BY stream_id
        ''')
        
        memory_counts = {row[0]: row[1] for row in cursor}
        
        # Get paradox count
        cursor = self.db.execute('SELECT COUNT(*) FROM temporal_paradoxes')
        paradox_count = cursor.fetchone()[0]
        
        return {
            'timelines': timelines,
            'memory_counts': memory_counts,
            'paradox_count': paradox_count,
            'active_stream': self.active_stream,
            'current_position': self.current_position
        }