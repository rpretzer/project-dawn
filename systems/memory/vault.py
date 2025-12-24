"""
Memory Vault - Central storage system for memOS
"""

import sqlite3
import json
import os
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import asyncio
import time
import logging
from abc import ABC, abstractmethod

# Optional ChromaDB dependency
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except (ImportError, Exception) as e:
    CHROMADB_AVAILABLE = False
    chromadb = None
    Settings = None

from .core import MemCube, MemoryQuery, MemoryType, MemoryState

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends"""
    
    @abstractmethod
    async def store(self, memory: MemCube) -> str:
        """Store a memory"""
        pass
    
    @abstractmethod
    async def retrieve(self, query: Dict[str, Any]) -> List[MemCube]:
        """Retrieve memories"""
        pass
    
    @abstractmethod
    async def update(self, memory_id: str, memory: MemCube) -> bool:
        """Update a memory"""
        pass
    
    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory"""
        pass


class VectorStoreBackend(StorageBackend):
    """ChromaDB backend for semantic search"""
    
    def __init__(self, config: Dict[str, Any]):
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "ChromaDB is not available. Install chromadb>=0.4.0 for vector storage support. "
                "The system will use SQLite backend instead."
            )
        
        self.path = Path(config.get("path", "data/vector_store"))
        self.path.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(self.path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        self.collections = {}
        
    def _get_collection(self, namespace: Tuple[str, str, str]):
        """Get or create collection for namespace"""
        collection_name = f"{namespace[0]}_{namespace[1]}_{namespace[2]}"
        
        if collection_name not in self.collections:
            self.collections[collection_name] = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"namespace": list(namespace)}
            )
        
        return self.collections[collection_name]
    
    async def store(self, memory: MemCube) -> str:
        """Store memory in vector database"""
        collection = self._get_collection(memory.namespace)
        
        # Prepare content for embedding
        if isinstance(memory.content, str):
            document = memory.content
        else:
            document = json.dumps(memory.content)
        
        # Store in ChromaDB
        collection.add(
            ids=[memory.memory_id],
            documents=[document],
            metadatas=[{
                "memory_type": memory.memory_type.value,
                "semantic_type": memory.semantic_type,
                "timestamp": memory.timestamp,
                "priority_level": memory.priority_level,
                "state": memory.state.value,
                "origin_signature": memory.origin_signature
            }]
        )
        
        return memory.memory_id
    
    async def retrieve(self, query: Dict[str, Any]) -> List[MemCube]:
        """Retrieve memories using semantic search"""
        results = []
        
        # Get query text
        query_text = query.get("text", query.get("raw_query", ""))
        if not query_text:
            return results
        
        # Search across relevant collections
        namespace = query.get("namespace", ("*", "*", "*"))
        
        for collection_name, collection in self.collections.items():
            # Check if collection matches namespace pattern
            coll_namespace = collection.metadata.get("namespace", ["", "", ""])
            if self._matches_namespace(coll_namespace, namespace):
                # Search collection
                search_results = collection.query(
                    query_texts=[query_text],
                    n_results=query.get("limit", 10)
                )
                
                # Convert to MemCubes (simplified - would need full reconstruction)
                for i, doc_id in enumerate(search_results["ids"][0]):
                    metadata = search_results["metadatas"][0][i]
                    results.append(MemCube(
                        memory_id=doc_id,
                        content=search_results["documents"][0][i],
                        memory_type=MemoryType(metadata["memory_type"]),
                        timestamp=metadata["timestamp"],
                        origin_signature=metadata["origin_signature"],
                        semantic_type=metadata["semantic_type"],
                        namespace=tuple(coll_namespace),
                        access_control={"owner": ["read", "write"]},
                        priority_level=metadata["priority_level"],
                        compliance_tags=[],
                        state=MemoryState(metadata["state"])
                    ))
        
        return results
    
    async def update(self, memory_id: str, memory: MemCube) -> bool:
        """Update not directly supported - store new version instead"""
        await self.store(memory)
        return True
    
    async def delete(self, memory_id: str) -> bool:
        """Delete from all collections"""
        for collection in self.collections.values():
            try:
                collection.delete(ids=[memory_id])
            except:
                pass
        return True
    
    def _matches_namespace(self, namespace1: List[str], namespace2: Tuple[str, str, str]) -> bool:
        """Check if namespaces match (with wildcards)"""
        for i in range(3):
            if namespace2[i] != "*" and namespace1[i] != namespace2[i]:
                return False
        return True


class RelationalDBBackend(StorageBackend):
    """SQLite backend for structured queries and metadata"""
    
    def __init__(self, config: Dict[str, Any]):
        self.db_path = Path(config.get("path", "data/memories/vault.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        
    def _init_database(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    origin_signature TEXT NOT NULL,
                    semantic_type TEXT NOT NULL,
                    namespace_user TEXT NOT NULL,
                    namespace_context TEXT NOT NULL,
                    namespace_scope TEXT NOT NULL,
                    access_control TEXT NOT NULL,
                    ttl INTEGER,
                    priority_level INTEGER NOT NULL,
                    compliance_tags TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_access REAL,
                    contextual_fingerprint TEXT,
                    version_chain TEXT,
                    state TEXT NOT NULL,
                    related_memories TEXT,
                    parent_memory TEXT,
                    child_memories TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_namespace ON memories(namespace_user, namespace_context, namespace_scope)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_type ON memories(semantic_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_state ON memories(state)")
    
    async def store(self, memory: MemCube) -> str:
        """Store memory in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memories 
                (memory_id, content, memory_type, timestamp, origin_signature,
                 semantic_type, namespace_user, namespace_context, namespace_scope,
                 access_control, ttl, priority_level, compliance_tags,
                 access_count, last_access, contextual_fingerprint, version_chain,
                 state, related_memories, parent_memory, child_memories)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.memory_id,
                json.dumps(memory.content) if not isinstance(memory.content, str) else memory.content,
                memory.memory_type.value,
                memory.timestamp,
                memory.origin_signature,
                memory.semantic_type,
                memory.namespace[0],
                memory.namespace[1],
                memory.namespace[2],
                json.dumps(memory.access_control),
                memory.ttl,
                memory.priority_level,
                json.dumps(memory.compliance_tags),
                memory.access_count,
                memory.last_access,
                memory.contextual_fingerprint,
                json.dumps(memory.version_chain),
                memory.state.value,
                json.dumps(memory.related_memories),
                memory.parent_memory,
                json.dumps(memory.child_memories)
            ))
        
        return memory.memory_id
    
    async def retrieve(self, query: Dict[str, Any]) -> List[MemCube]:
        """Retrieve memories using SQL queries"""
        results = []
        
        # Build SQL query
        conditions = []
        params = []
        
        # Namespace filter
        namespace = query.get("namespace", ("*", "*", "*"))
        if namespace[0] != "*":
            conditions.append("namespace_user = ?")
            params.append(namespace[0])
        if namespace[1] != "*":
            conditions.append("namespace_context = ?")
            params.append(namespace[1])
        if namespace[2] != "*":
            conditions.append("namespace_scope = ?")
            params.append(namespace[2])
        
        # Temporal filter
        if "temporal_scope" in query:
            temporal = query["temporal_scope"]
            if temporal.get("type") == "relative":
                time_ago = time.time() - (temporal["value"] * 
                    (3600 if temporal["unit"] == "hours" else 86400))
                conditions.append("timestamp > ?")
                params.append(time_ago)
        
        # Semantic type filter
        if "semantic_type" in query:
            conditions.append("semantic_type = ?")
            params.append(query["semantic_type"])
        
        # Memory type filter
        if "memory_type" in query:
            conditions.append("memory_type = ?")
            params.append(query["memory_type"])
        
        # Build final query
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT * FROM memories 
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(query.get("limit", 100))
        
        # Execute query
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            
            for row in cursor:
                results.append(self._row_to_memcube(row))
        
        return results
    
    async def update(self, memory_id: str, memory: MemCube) -> bool:
        """Update existing memory"""
        return await self.store(memory)
    
    async def delete(self, memory_id: str) -> bool:
        """Delete memory"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM memories WHERE memory_id = ?", (memory_id,))
        return True
    
    async def get_by_id(self, memory_id: str) -> Optional[MemCube]:
        """Get memory by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM memories WHERE memory_id = ?", (memory_id,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_memcube(row)
        
        return None
    
    def _row_to_memcube(self, row: sqlite3.Row) -> MemCube:
        """Convert database row to MemCube"""
        content = row["content"]
        try:
            content = json.loads(content)
        except:
            pass  # Keep as string
        
        return MemCube(
            memory_id=row["memory_id"],
            content=content,
            memory_type=MemoryType(row["memory_type"]),
            timestamp=row["timestamp"],
            origin_signature=row["origin_signature"],
            semantic_type=row["semantic_type"],
            namespace=(row["namespace_user"], row["namespace_context"], row["namespace_scope"]),
            access_control=json.loads(row["access_control"]),
            ttl=row["ttl"],
            priority_level=row["priority_level"],
            compliance_tags=json.loads(row["compliance_tags"]),
            access_count=row["access_count"],
            last_access=row["last_access"],
            contextual_fingerprint=row["contextual_fingerprint"],
            version_chain=json.loads(row["version_chain"]),
            state=MemoryState(row["state"]),
            related_memories=json.loads(row["related_memories"]),
            parent_memory=row["parent_memory"],
            child_memories=json.loads(row["child_memories"])
        )


class MemVault:
    """Central memory storage with unified interface"""
    
    def __init__(self, storage_config: Dict[str, Any]):
        self.storage_config = storage_config
        self.backends = self._init_backends(storage_config)
        self.governance = None  # Set externally
        self._cache = {}  # Simple in-memory cache
        
    def _init_backends(self, config: Dict[str, Any]) -> Dict[str, StorageBackend]:
        """Initialize storage backends"""
        backends = {}
        
        # Always initialize relational DB for metadata
        backends["relational"] = RelationalDBBackend(
            config.get("relational_db", {"path": "data/memories/vault.db"})
        )
        
        # Initialize vector store if configured
        if "vector_store" in config:
            try:
                backends["vector"] = VectorStoreBackend(config["vector_store"])
            except ImportError as e:
                logger.warning(f"Vector store backend not available: {e}. Using relational DB only.")
        
        return backends
    
    async def store(self, memory: MemCube) -> str:
        """Store memory in appropriate backends"""
        # Apply governance if available
        if self.governance:
            memory = await self.governance.redact_sensitive_content(memory)
        
        # Always store in relational DB
        await self.backends["relational"].store(memory)
        
        # Store in vector DB if available and appropriate
        if "vector" in self.backends and memory.memory_type == MemoryType.PLAINTEXT:
            await self.backends["vector"].store(memory)
        
        # Cache
        self._cache[memory.memory_id] = memory
        
        return memory.memory_id
    
    async def retrieve(self, query: MemoryQuery) -> List[MemCube]:
        """Retrieve memories using hybrid search"""
        results = []
        seen_ids = set()
        
        # Convert MemoryQuery to dict for backends
        query_dict = {
            "namespace": query.namespace,
            "limit": query.parameters.get("limit", 100),
            **query.parameters
        }
        
        # Search relational DB (structured queries)
        relational_results = await self.backends["relational"].retrieve(query_dict)
        for memory in relational_results:
            if memory.memory_id not in seen_ids:
                results.append(memory)
                seen_ids.add(memory.memory_id)
        
        # Search vector DB if query has text
        if "vector" in self.backends and query.parameters.get("raw_query"):
            vector_results = await self.backends["vector"].retrieve(query_dict)
            for memory in vector_results:
                if memory.memory_id not in seen_ids:
                    # Get full memory from relational DB
                    full_memory = await self.backends["relational"].get_by_id(memory.memory_id)
                    if full_memory:
                        results.append(full_memory)
                        seen_ids.add(memory.memory_id)
        
        # Apply governance filters
        if self.governance:
            filtered_results = []
            for memory in results:
                if await self.governance.check_access(
                    query.requester_id,
                    memory,
                    "read",
                    query.context
                ):
                    filtered_results.append(memory)
            results = filtered_results
        
        return results
    
    async def get_by_id(self, memory_id: str) -> Optional[MemCube]:
        """Get specific memory by ID"""
        # Check cache
        if memory_id in self._cache:
            return self._cache[memory_id]
        
        # Get from database
        memory = await self.backends["relational"].get_by_id(memory_id)
        
        if memory:
            self._cache[memory_id] = memory
        
        return memory
    
    async def update_access_stats(self, memory_id: str):
        """Update access statistics for a memory"""
        memory = await self.get_by_id(memory_id)
        if memory:
            memory.update_access()
            await self.backends["relational"].update(memory_id, memory)
    
    async def archive(self, memory_id: str) -> bool:
        """Archive a memory"""
        memory = await self.get_by_id(memory_id)
        if memory:
            memory.transition_state(MemoryState.ARCHIVED)
            await self.backends["relational"].update(memory_id, memory)
            
            # Remove from cache
            if memory_id in self._cache:
                del self._cache[memory_id]
            
            return True
        return False
    
    async def count(self) -> int:
        """Get total memory count"""
        with sqlite3.connect(self.backends["relational"].db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM memories WHERE state != 'archived'")
            return cursor.fetchone()[0]
    
    async def count_by_type(self) -> Dict[str, int]:
        """Get memory count by type"""
        with sqlite3.connect(self.backends["relational"].db_path) as conn:
            cursor = conn.execute("""
                SELECT memory_type, COUNT(*) 
                FROM memories 
                WHERE state != 'archived'
                GROUP BY memory_type
            """)
            return dict(cursor.fetchall())
    
    async def count_by_state(self) -> Dict[str, int]:
        """Get memory count by state"""
        with sqlite3.connect(self.backends["relational"].db_path) as conn:
            cursor = conn.execute("""
                SELECT state, COUNT(*) 
                FROM memories 
                GROUP BY state
            """)
            return dict(cursor.fetchall())
    
    async def get_storage_size(self) -> int:
        """Get total storage size in bytes"""
        total_size = 0
        
        # Database size
        if os.path.exists(self.backends["relational"].db_path):
            total_size += os.path.getsize(self.backends["relational"].db_path)
        
        # Vector store size
        if "vector" in self.backends:
            vector_path = self.backends["vector"].path
            for root, dirs, files in os.walk(vector_path):
                for file in files:
                    total_size += os.path.getsize(os.path.join(root, file))
        
        return total_size
    
    async def get_hot_memories(self, threshold: int = 10, time_window: int = 3600) -> List[str]:
        """Get frequently accessed memories"""
        cutoff_time = time.time() - time_window
        
        with sqlite3.connect(self.backends["relational"].db_path) as conn:
            cursor = conn.execute("""
                SELECT memory_id 
                FROM memories 
                WHERE access_count > ? 
                AND last_access > ?
                AND state != 'archived'
                ORDER BY access_count DESC
                LIMIT 100
            """, (threshold, cutoff_time))
            
            return [row[0] for row in cursor]