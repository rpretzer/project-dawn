"""
Memory Loaders - Import/export functionality for cross-platform memory migration
"""

import json
import csv
import pickle
import sqlite3
import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Tuple, BinaryIO, TextIO
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
from dataclasses import asdict
# Optional ChromaDB dependency
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
import yaml
import msgpack
import h5py
import numpy as np

from .core import MemCube, MemoryType, MemoryState
from .vault import MemVault

logger = logging.getLogger(__name__)


class MemoryFormatHandler:
    """Base class for memory format handlers"""
    
    async def import_memories(self, source: Any, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Import memories from source"""
        logger.warning(
            "%s does not implement import_memories; returning empty list.",
            self.__class__.__name__,
        )
        return []
    
    async def export_memories(self, memories: List[MemCube], destination: Any, options: Dict[str, Any] = None) -> bool:
        """Export memories to destination"""
        logger.warning(
            "%s does not implement export_memories; nothing was written.",
            self.__class__.__name__,
        )
        return False


class MemCubeFormatHandler(MemoryFormatHandler):
    """Native MemCube format handler"""
    
    async def import_memories(self, source: str, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Import from MemCube JSON format"""
        path = Path(source)
        memories = []
        
        if path.suffix == '.json':
            with open(path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    memories = data
                else:
                    memories = [data]
        
        elif path.suffix == '.jsonl':
            with open(path, 'r') as f:
                for line in f:
                    memories.append(json.loads(line.strip()))
        
        elif path.suffix == '.msgpack':
            with open(path, 'rb') as f:
                data = msgpack.unpack(f, raw=False)
                memories = data if isinstance(data, list) else [data]
        
        return memories
    
    async def export_memories(self, memories: List[MemCube], destination: str, options: Dict[str, Any] = None) -> bool:
        """Export to MemCube format"""
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        options = options or {}
        format_type = options.get('format', 'json')
        
        try:
            if format_type == 'json':
                with open(path, 'w') as f:
                    json.dump([m.to_dict() for m in memories], f, indent=2)
            
            elif format_type == 'jsonl':
                with open(path, 'w') as f:
                    for memory in memories:
                        f.write(json.dumps(memory.to_dict()) + '\n')
            
            elif format_type == 'msgpack':
                with open(path, 'wb') as f:
                    msgpack.pack([m.to_dict() for m in memories], f)
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to MemCube format: {e}")
            return False


class ChromaDBFormatHandler(MemoryFormatHandler):
    """ChromaDB format handler"""
    
    async def import_memories(self, source: str, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Import from ChromaDB"""
        client = chromadb.PersistentClient(path=source)
        memories = []
        
        # Get all collections
        collections = client.list_collections()
        
        for collection in collections:
            # Get all documents from collection
            results = collection.get()
            
            for i, doc_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                
                memory_dict = {
                    'memory_id': doc_id,
                    'content': results['documents'][i] if results['documents'] else "",
                    'memory_type': metadata.get('memory_type', 'plaintext'),
                    'timestamp': metadata.get('timestamp', time.time()),
                    'origin_signature': metadata.get('origin_signature', 'chromadb_import'),
                    'semantic_type': metadata.get('semantic_type', 'document'),
                    'namespace': [
                        metadata.get('namespace_user', 'imported'),
                        metadata.get('namespace_context', collection.name),
                        metadata.get('namespace_scope', 'chromadb')
                    ],
                    'access_control': {'owner': ['read', 'write', 'delete']},
                    'priority_level': metadata.get('priority_level', 5),
                    'compliance_tags': metadata.get('tags', [])
                }
                
                # Add embeddings if requested
                if options and options.get('include_embeddings') and results.get('embeddings'):
                    memory_dict['embeddings'] = results['embeddings'][i]
                
                memories.append(memory_dict)
        
        return memories
    
    async def export_memories(self, memories: List[MemCube], destination: str, options: Dict[str, Any] = None) -> bool:
        """Export to ChromaDB format"""
        try:
            client = chromadb.PersistentClient(path=destination)
            
            # Group memories by namespace for collections
            collections_map = {}
            
            for memory in memories:
                collection_name = f"{memory.namespace[0]}_{memory.namespace[1]}"
                
                if collection_name not in collections_map:
                    collections_map[collection_name] = client.get_or_create_collection(
                        name=collection_name,
                        metadata={"namespace": list(memory.namespace)}
                    )
                
                collection = collections_map[collection_name]
                
                # Prepare document
                document = memory.content if isinstance(memory.content, str) else json.dumps(memory.content)
                
                # Prepare metadata
                metadata = {
                    'memory_type': memory.memory_type.value,
                    'semantic_type': memory.semantic_type,
                    'timestamp': memory.timestamp,
                    'origin_signature': memory.origin_signature,
                    'namespace_user': memory.namespace[0],
                    'namespace_context': memory.namespace[1],
                    'namespace_scope': memory.namespace[2],
                    'priority_level': memory.priority_level,
                    'state': memory.state.value,
                    'tags': memory.compliance_tags
                }
                
                # Add to collection
                collection.add(
                    ids=[memory.memory_id],
                    documents=[document],
                    metadatas=[metadata]
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to ChromaDB: {e}")
            return False


class JSONFormatHandler(MemoryFormatHandler):
    """Generic JSON format handler"""
    
    async def import_memories(self, source: str, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Import from generic JSON"""
        with open(source, 'r') as f:
            data = json.load(f)
        
        memories = []
        items = data if isinstance(data, list) else [data]
        
        for item in items:
            # Map generic fields to MemCube format
            memory_dict = {
                'memory_id': item.get('id', f"imported_{int(time.time() * 1000)}"),
                'content': item.get('content', item.get('text', item)),
                'memory_type': 'plaintext',
                'timestamp': item.get('timestamp', item.get('created_at', time.time())),
                'origin_signature': item.get('author', item.get('source', 'json_import')),
                'semantic_type': item.get('type', 'general'),
                'namespace': [
                    item.get('user', 'imported'),
                    item.get('context', 'default'),
                    item.get('scope', 'json')
                ],
                'access_control': {'owner': ['read', 'write', 'delete']},
                'priority_level': item.get('priority', 5),
                'compliance_tags': item.get('tags', [])
            }
            
            # Preserve any additional fields
            memory_dict['original_data'] = item
            
            memories.append(memory_dict)
        
        return memories
    
    async def export_memories(self, memories: List[MemCube], destination: str, options: Dict[str, Any] = None) -> bool:
        """Export to JSON format"""
        try:
            export_data = []
            
            for memory in memories:
                data = memory.to_dict()
                
                # Optionally flatten structure
                if options and options.get('flatten', False):
                    flat_data = {
                        'id': data['memory_id'],
                        'content': data['content'],
                        'type': data['semantic_type'],
                        'timestamp': data['timestamp'],
                        'author': data['origin_signature'],
                        'tags': data.get('compliance_tags', [])
                    }
                    export_data.append(flat_data)
                else:
                    export_data.append(data)
            
            with open(destination, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return False


class ParquetFormatHandler(MemoryFormatHandler):
    """Apache Parquet format handler for large-scale data"""
    
    async def import_memories(self, source: str, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Import from Parquet files"""
        table = pq.read_table(source)
        df = table.to_pandas()
        
        memories = []
        
        for _, row in df.iterrows():
            memory_dict = {
                'memory_id': str(row.get('memory_id', f"parquet_{int(time.time() * 1000)}")),
                'content': row.get('content', ''),
                'memory_type': row.get('memory_type', 'plaintext'),
                'timestamp': float(row.get('timestamp', time.time())),
                'origin_signature': str(row.get('origin_signature', 'parquet_import')),
                'semantic_type': str(row.get('semantic_type', 'data')),
                'namespace': [
                    str(row.get('namespace_0', 'imported')),
                    str(row.get('namespace_1', 'default')),
                    str(row.get('namespace_2', 'parquet'))
                ],
                'access_control': json.loads(row.get('access_control', '{"owner": ["read", "write", "delete"]}')),
                'priority_level': int(row.get('priority_level', 5)),
                'compliance_tags': json.loads(row.get('compliance_tags', '[]'))
            }
            
            memories.append(memory_dict)
        
        return memories
    
    async def export_memories(self, memories: List[MemCube], destination: str, options: Dict[str, Any] = None) -> bool:
        """Export to Parquet format"""
        try:
            # Convert to DataFrame
            data = []
            
            for memory in memories:
                row = {
                    'memory_id': memory.memory_id,
                    'content': json.dumps(memory.content) if not isinstance(memory.content, str) else memory.content,
                    'memory_type': memory.memory_type.value,
                    'timestamp': memory.timestamp,
                    'origin_signature': memory.origin_signature,
                    'semantic_type': memory.semantic_type,
                    'namespace_0': memory.namespace[0],
                    'namespace_1': memory.namespace[1],
                    'namespace_2': memory.namespace[2],
                    'access_control': json.dumps(memory.access_control),
                    'priority_level': memory.priority_level,
                    'compliance_tags': json.dumps(memory.compliance_tags),
                    'state': memory.state.value,
                    'access_count': memory.access_count,
                    'last_access': memory.last_access
                }
                data.append(row)
            
            df = pd.DataFrame(data)
            
            # Convert to Parquet
            table = pa.Table.from_pandas(df)
            pq.write_table(table, destination, compression='snappy')
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to Parquet: {e}")
            return False


class HDF5FormatHandler(MemoryFormatHandler):
    """HDF5 format handler for scientific data and embeddings"""
    
    async def import_memories(self, source: str, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Import from HDF5 files"""
        memories = []
        
        with h5py.File(source, 'r') as f:
            # Check for memories group
            if 'memories' not in f:
                raise ValueError("HDF5 file does not contain 'memories' group")
            
            memories_group = f['memories']
            
            for memory_id in memories_group:
                memory_data = memories_group[memory_id]
                
                # Extract attributes
                attrs = dict(memory_data.attrs)
                
                # Extract content
                if 'content' in memory_data:
                    content = memory_data['content'][()]
                    if isinstance(content, bytes):
                        content = content.decode('utf-8')
                else:
                    content = attrs.get('content', '')
                
                # Extract embeddings if present
                embeddings = None
                if 'embeddings' in memory_data:
                    embeddings = memory_data['embeddings'][()].tolist()
                
                memory_dict = {
                    'memory_id': memory_id,
                    'content': content,
                    'memory_type': attrs.get('memory_type', 'plaintext'),
                    'timestamp': attrs.get('timestamp', time.time()),
                    'origin_signature': attrs.get('origin_signature', 'hdf5_import'),
                    'semantic_type': attrs.get('semantic_type', 'data'),
                    'namespace': json.loads(attrs.get('namespace', '["imported", "default", "hdf5"]')),
                    'access_control': json.loads(attrs.get('access_control', '{"owner": ["read", "write", "delete"]}')),
                    'priority_level': attrs.get('priority_level', 5),
                    'compliance_tags': json.loads(attrs.get('compliance_tags', '[]'))
                }
                
                if embeddings:
                    memory_dict['embeddings'] = embeddings
                
                memories.append(memory_dict)
        
        return memories
    
    async def export_memories(self, memories: List[MemCube], destination: str, options: Dict[str, Any] = None) -> bool:
        """Export to HDF5 format"""
        try:
            with h5py.File(destination, 'w') as f:
                memories_group = f.create_group('memories')
                
                for memory in memories:
                    memory_group = memories_group.create_group(memory.memory_id)
                    
                    # Store content
                    if isinstance(memory.content, str):
                        memory_group.create_dataset('content', data=memory.content.encode('utf-8'))
                    else:
                        memory_group.attrs['content'] = json.dumps(memory.content)
                    
                    # Store attributes
                    memory_group.attrs['memory_type'] = memory.memory_type.value
                    memory_group.attrs['timestamp'] = memory.timestamp
                    memory_group.attrs['origin_signature'] = memory.origin_signature
                    memory_group.attrs['semantic_type'] = memory.semantic_type
                    memory_group.attrs['namespace'] = json.dumps(list(memory.namespace))
                    memory_group.attrs['access_control'] = json.dumps(memory.access_control)
                    memory_group.attrs['priority_level'] = memory.priority_level
                    memory_group.attrs['compliance_tags'] = json.dumps(memory.compliance_tags)
                    memory_group.attrs['state'] = memory.state.value
                    
                    # Store embeddings if available
                    if hasattr(memory, 'embeddings') and memory.embeddings:
                        memory_group.create_dataset('embeddings', data=np.array(memory.embeddings))
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to HDF5: {e}")
            return False


class SQLiteFormatHandler(MemoryFormatHandler):
    """SQLite database format handler"""
    
    async def import_memories(self, source: str, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Import from SQLite database"""
        memories = []
        
        with sqlite3.connect(source) as conn:
            conn.row_factory = sqlite3.Row
            
            # Try to find memories table
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE '%memor%'
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            
            if not tables:
                raise ValueError("No memory-related tables found in SQLite database")
            
            # Use first matching table
            table_name = tables[0]
            
            # Get all records
            cursor = conn.execute(f"SELECT * FROM {table_name}")
            columns = [desc[0] for desc in cursor.description]
            
            for row in cursor:
                row_dict = dict(zip(columns, row))
                
                # Map to MemCube format
                memory_dict = {
                    'memory_id': str(row_dict.get('id', row_dict.get('memory_id', f"sqlite_{int(time.time() * 1000)}"))),
                    'content': row_dict.get('content', row_dict.get('data', '')),
                    'memory_type': row_dict.get('type', row_dict.get('memory_type', 'plaintext')),
                    'timestamp': float(row_dict.get('timestamp', row_dict.get('created_at', time.time()))),
                    'origin_signature': row_dict.get('origin', row_dict.get('author', 'sqlite_import')),
                    'semantic_type': row_dict.get('semantic_type', 'general'),
                    'namespace': [
                        row_dict.get('user', 'imported'),
                        row_dict.get('context', 'default'),
                        row_dict.get('scope', 'sqlite')
                    ],
                    'access_control': {'owner': ['read', 'write', 'delete']},
                    'priority_level': int(row_dict.get('priority', 5)),
                    'compliance_tags': []
                }
                
                memories.append(memory_dict)
        
        return memories
    
    async def export_memories(self, memories: List[MemCube], destination: str, options: Dict[str, Any] = None) -> bool:
        """Export to SQLite database"""
        try:
            with sqlite3.connect(destination) as conn:
                # Create table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        memory_id TEXT PRIMARY KEY,
                        content TEXT,
                        memory_type TEXT,
                        timestamp REAL,
                        origin_signature TEXT,
                        semantic_type TEXT,
                        namespace TEXT,
                        access_control TEXT,
                        priority_level INTEGER,
                        compliance_tags TEXT,
                        state TEXT,
                        access_count INTEGER,
                        last_access REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert memories
                for memory in memories:
                    conn.execute("""
                        INSERT OR REPLACE INTO memories
                        (memory_id, content, memory_type, timestamp, origin_signature,
                         semantic_type, namespace, access_control, priority_level,
                         compliance_tags, state, access_count, last_access)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        memory.memory_id,
                        json.dumps(memory.content) if not isinstance(memory.content, str) else memory.content,
                        memory.memory_type.value,
                        memory.timestamp,
                        memory.origin_signature,
                        memory.semantic_type,
                        json.dumps(list(memory.namespace)),
                        json.dumps(memory.access_control),
                        memory.priority_level,
                        json.dumps(memory.compliance_tags),
                        memory.state.value,
                        memory.access_count,
                        memory.last_access
                    ))
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to SQLite: {e}")
            return False


class MemLoader:
    """Cross-platform memory import/export manager"""
    
    def __init__(self, vault: MemVault):
        self.vault = vault
        
        # Register format handlers
        self.format_handlers = {
            "memcube": MemCubeFormatHandler(),
            "chromadb": ChromaDBFormatHandler(),
            "json": JSONFormatHandler(),
            "parquet": ParquetFormatHandler(),
            "hdf5": HDF5FormatHandler(),
            "sqlite": SQLiteFormatHandler()
        }
        
        # File extension mapping
        self.extension_map = {
            ".json": "json",
            ".jsonl": "memcube",
            ".msgpack": "memcube",
            ".parquet": "parquet",
            ".pq": "parquet",
            ".h5": "hdf5",
            ".hdf5": "hdf5",
            ".db": "sqlite",
            ".sqlite": "sqlite",
            ".sqlite3": "sqlite"
        }
    
    async def import_memories(self, 
                            source: str, 
                            format: Optional[str] = None,
                            namespace: Tuple[str, str, str] = ("imported", "default", "external"),
                            options: Dict[str, Any] = None) -> List[str]:
        """Import memories from external source"""
        # Auto-detect format if not specified
        if not format:
            source_path = Path(source)
            if source_path.is_dir():
                # Check if it's a ChromaDB directory
                if (source_path / "chroma.sqlite3").exists():
                    format = "chromadb"
                else:
                    raise ValueError("Cannot auto-detect format for directory")
            else:
                format = self.extension_map.get(source_path.suffix)
                
            if not format:
                raise ValueError(f"Cannot auto-detect format for {source}")
        
        # Get handler
        handler = self.format_handlers.get(format)
        if not handler:
            raise ValueError(f"Unsupported format: {format}")
        
        # Import memories
        logger.info(f"Importing memories from {source} using {format} format")
        raw_memories = await handler.import_memories(source, options)
        
        # Convert to MemCubes and store
        imported_ids = []
        
        for i, raw_mem in enumerate(raw_memories):
            try:
                # Auto-fill missing metadata
                raw_mem = await self._autofill_metadata(raw_mem, namespace)
                
                # Create MemCube
                memcube = MemCube.from_dict(raw_mem)
                
                # Store in vault
                mem_id = await self.vault.store(memcube)
                imported_ids.append(mem_id)
                
                if (i + 1) % 100 == 0:
                    logger.info(f"Imported {i + 1}/{len(raw_memories)} memories")
                    
            except Exception as e:
                logger.error(f"Error importing memory {i}: {e}")
                continue
        
        logger.info(f"Successfully imported {len(imported_ids)} memories")
        return imported_ids
    
    async def export_memories(self,
                            query: Dict[str, Any],
                            destination: str,
                            format: Optional[str] = None,
                            options: Dict[str, Any] = None) -> bool:
        """Export memories to external format"""
        # Auto-detect format from destination
        if not format:
            dest_path = Path(destination)
            format = self.extension_map.get(dest_path.suffix, "json")
        
        # Get handler
        handler = self.format_handlers.get(format)
        if not handler:
            raise ValueError(f"Unsupported format: {format}")
        
        # Query memories
        from .core import MemoryQuery
        memory_query = MemoryQuery(
            query_type="export",
            parameters=query,
            namespace=query.get("namespace", ("*", "*", "*")),
            requester_id="export_system"
        )
        
        memories = await self.vault.retrieve(memory_query)
        
        if not memories:
            logger.warning("No memories found to export")
            return False
        
        # Export
        logger.info(f"Exporting {len(memories)} memories to {destination} in {format} format")
        success = await handler.export_memories(memories, destination, options)
        
        if success:
            logger.info(f"Successfully exported {len(memories)} memories")
        else:
            logger.error("Export failed")
        
        return success
    
    async def _autofill_metadata(self, raw_mem: Dict[str, Any], default_namespace: Tuple[str, str, str]) -> Dict[str, Any]:
        """Auto-fill missing metadata fields"""
        # Ensure required fields
        if 'memory_id' not in raw_mem:
            raw_mem['memory_id'] = f"imported_{int(time.time() * 1000)}_{hash(str(raw_mem)) % 1000000}"
        
        if 'timestamp' not in raw_mem:
            raw_mem['timestamp'] = time.time()
        
        if 'namespace' not in raw_mem:
            raw_mem['namespace'] = list(default_namespace)
        
        if 'access_control' not in raw_mem:
            raw_mem['access_control'] = {"owner": ["read", "write", "delete"]}
        
        if 'priority_level' not in raw_mem:
            raw_mem['priority_level'] = 5
        
        if 'compliance_tags' not in raw_mem:
            raw_mem['compliance_tags'] = []
        
        if 'state' not in raw_mem:
            raw_mem['state'] = MemoryState.GENERATED.value
        
        # Ensure lists are lists, not tuples
        if isinstance(raw_mem.get('namespace'), tuple):
            raw_mem['namespace'] = list(raw_mem['namespace'])
        
        return raw_mem
    
    async def batch_import(self,
                         sources: List[Tuple[str, str]],  # [(source, format), ...]
                         namespace: Tuple[str, str, str] = ("imported", "default", "external"),
                         parallel: bool = True) -> Dict[str, List[str]]:
        """Import from multiple sources"""
        results = {}
        
        if parallel:
            # Import in parallel
            tasks = []
            for source, format in sources:
                task = self.import_memories(source, format, namespace)
                tasks.append((source, task))
            
            for source, task in tasks:
                try:
                    imported_ids = await task
                    results[source] = imported_ids
                except Exception as e:
                    logger.error(f"Error importing from {source}: {e}")
                    results[source] = []
        else:
            # Import sequentially
            for source, format in sources:
                try:
                    imported_ids = await self.import_memories(source, format, namespace)
                    results[source] = imported_ids
                except Exception as e:
                    logger.error(f"Error importing from {source}: {e}")
                    results[source] = []
        
        return results
    
    def get_supported_formats(self) -> Dict[str, str]:
        """Get list of supported formats"""
        return {
            format_name: handler.__class__.__name__
            for format_name, handler in self.format_handlers.items()
        }
