"""
Memory Export/Import
Client-side export/import functionality for portable memory format
Similar to Anthropic's file-based memory system
"""

import json
import time
import logging
from typing import List, Dict, Any, Optional, BinaryIO, TextIO
from pathlib import Path
from datetime import datetime

from .core import MemCube, MemoryType, MemoryState
from .vault import MemVault
from .interface import MemoryAPI

logger = logging.getLogger(__name__)


class MemoryExporter:
    """
    Export memories to portable formats (JSON, JSONL)
    Similar to Anthropic's client-side memory files
    """
    
    def __init__(self, memory_api: MemoryAPI):
        self.memory_api = memory_api
    
    async def export_namespace(
        self,
        namespace: tuple,
        output_path: str,
        format: str = "json",
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Export all memories from a namespace to file
        
        Args:
            namespace: Namespace tuple to export
            output_path: Output file path
            format: Export format ("json", "jsonl")
            include_metadata: Whether to include full metadata
            
        Returns:
            Export statistics
        """
        from .core import MemoryQuery
        
        # Retrieve all memories in namespace
        query = MemoryQuery(
            query_type="hybrid",
            parameters={"limit": 100000},
            namespace=namespace,
            requester_id="system"
        )
        
        memories = await self.memory_api.retrieve(query)
        
        # Convert to exportable format
        export_data = []
        for memory in memories:
            mem_data = self._memory_to_export_dict(memory, include_metadata)
            export_data.append(mem_data)
        
        # Write to file
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            with open(output_path_obj, 'w', encoding='utf-8') as f:
                json.dump({
                    "version": "1.0",
                    "exported_at": datetime.utcnow().isoformat(),
                    "namespace": list(namespace),
                    "count": len(export_data),
                    "memories": export_data
                }, f, indent=2, ensure_ascii=False)
        
        elif format == "jsonl":
            with open(output_path_obj, 'w', encoding='utf-8') as f:
                for mem_data in export_data:
                    f.write(json.dumps(mem_data, ensure_ascii=False) + '\n')
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Exported {len(export_data)} memories to {output_path}")
        
        return {
            "exported_count": len(export_data),
            "output_path": str(output_path_obj),
            "format": format,
            "size_bytes": output_path_obj.stat().st_size
        }
    
    async def export_memories(
        self,
        memory_ids: List[str],
        output_path: str,
        format: str = "json",
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Export specific memories by ID
        
        Args:
            memory_ids: List of memory IDs to export
            output_path: Output file path
            format: Export format ("json", "jsonl")
            include_metadata: Whether to include full metadata
            
        Returns:
            Export statistics
        """
        export_data = []
        
        for mem_id in memory_ids:
            memory = await self.memory_api.vault.get_by_id(mem_id)
            if memory:
                mem_data = self._memory_to_export_dict(memory, include_metadata)
                export_data.append(mem_data)
        
        # Write to file
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            with open(output_path_obj, 'w', encoding='utf-8') as f:
                json.dump({
                    "version": "1.0",
                    "exported_at": datetime.utcnow().isoformat(),
                    "count": len(export_data),
                    "memories": export_data
                }, f, indent=2, ensure_ascii=False)
        
        elif format == "jsonl":
            with open(output_path_obj, 'w', encoding='utf-8') as f:
                for mem_data in export_data:
                    f.write(json.dumps(mem_data, ensure_ascii=False) + '\n')
        
        logger.info(f"Exported {len(export_data)} memories to {output_path}")
        
        return {
            "exported_count": len(export_data),
            "output_path": str(output_path_obj),
            "format": format,
            "size_bytes": output_path_obj.stat().st_size
        }
    
    def _memory_to_export_dict(self, memory: MemCube, include_metadata: bool) -> Dict[str, Any]:
        """Convert memory to exportable dictionary"""
        data = {
            "memory_id": memory.memory_id,
            "content": memory.content,
            "memory_type": memory.memory_type.value,
            "semantic_type": memory.semantic_type,
            "timestamp": memory.timestamp,
            "namespace": list(memory.namespace)
        }
        
        if include_metadata:
            data.update({
                "origin_signature": memory.origin_signature,
                "access_control": memory.access_control,
                "priority_level": memory.priority_level,
                "compliance_tags": memory.compliance_tags,
                "ttl": memory.ttl,
                "state": memory.state.value,
                "access_count": memory.access_count,
                "last_access": memory.last_access,
                "version_chain": memory.version_chain,
                "related_memories": memory.related_memories,
                "parent_memory": memory.parent_memory,
                "child_memories": memory.child_memories
            })
        
        return data


class MemoryImporter:
    """
    Import memories from portable formats
    Supports JSON and JSONL formats exported by MemoryExporter
    """
    
    def __init__(self, memory_api: MemoryAPI):
        self.memory_api = memory_api
    
    async def import_from_file(
        self,
        file_path: str,
        namespace: Optional[tuple] = None,
        overwrite: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Import memories from file
        
        Args:
            file_path: Path to import file (JSON or JSONL)
            namespace: Optional target namespace (if None, uses original)
            overwrite: Whether to overwrite existing memories with same ID
            dry_run: If True, don't actually import, just validate
            
        Returns:
            Import statistics
        """
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            raise FileNotFoundError(f"Import file not found: {file_path}")
        
        # Detect format
        if file_path_obj.suffix == ".jsonl":
            memories_data = self._load_jsonl(file_path_obj)
            metadata = {"count": len(memories_data)}
        else:
            # Assume JSON
            with open(file_path_obj, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                memories_data = data
                metadata = {"count": len(memories_data)}
            else:
                # Structured format
                memories_data = data.get("memories", [])
                metadata = {k: v for k, v in data.items() if k != "memories"}
        
        # Import memories
        imported = []
        skipped = []
        errors = []
        
        for mem_data in memories_data:
            try:
                memory = self._import_dict_to_memory(mem_data, namespace)
                
                if not dry_run:
                    # Check if exists
                    existing = await self.memory_api.vault.get_by_id(memory.memory_id)
                    if existing and not overwrite:
                        skipped.append(memory.memory_id)
                        continue
                    
                    # Store memory
                    await self.memory_api.store(memory)
                    imported.append(memory.memory_id)
                else:
                    imported.append(memory.memory_id)  # Count even in dry run
                    
            except Exception as e:
                logger.error(f"Error importing memory: {e}")
                errors.append({"memory_id": mem_data.get("memory_id"), "error": str(e)})
        
        result = {
            "imported_count": len(imported),
            "skipped_count": len(skipped),
            "error_count": len(errors),
            "imported_ids": imported,
            "skipped_ids": skipped,
            "errors": errors,
            "metadata": metadata
        }
        
        if not dry_run:
            logger.info(
                f"Imported {len(imported)} memories from {file_path} "
                f"({len(skipped)} skipped, {len(errors)} errors)"
            )
        else:
            logger.info(f"Dry run: would import {len(imported)} memories from {file_path}")
        
        return result
    
    def _load_jsonl(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load JSONL file"""
        memories = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    memories.append(json.loads(line))
        return memories
    
    def _import_dict_to_memory(
        self,
        data: Dict[str, Any],
        target_namespace: Optional[tuple]
    ) -> MemCube:
        """Convert imported dictionary to MemCube"""
        # Use target namespace if provided, otherwise use original
        namespace = target_namespace if target_namespace else tuple(data["namespace"])
        
        memory = MemCube(
            memory_id=data.get("memory_id"),  # Preserve ID if present
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            timestamp=data.get("timestamp", time.time()),
            origin_signature=data.get("origin_signature", "imported"),
            semantic_type=data.get("semantic_type", "general"),
            namespace=namespace,
            access_control=data.get("access_control", {"owner": ["read", "write", "delete"]}),
            priority_level=data.get("priority_level", 5),
            compliance_tags=data.get("compliance_tags", []),
            ttl=data.get("ttl"),
            state=MemoryState(data.get("state", "generated")),
            access_count=data.get("access_count", 0),
            last_access=data.get("last_access"),
            version_chain=data.get("version_chain", []),
            related_memories=data.get("related_memories", []),
            parent_memory=data.get("parent_memory"),
            child_memories=data.get("child_memories", [])
        )
        
        return memory


class MemoryBackup:
    """
    Backup and restore functionality for memory system
    """
    
    def __init__(self, memory_api: MemoryAPI):
        self.exporter = MemoryExporter(memory_api)
        self.importer = MemoryImporter(memory_api)
    
    async def create_backup(
        self,
        backup_dir: str,
        namespaces: Optional[List[tuple]] = None
    ) -> Dict[str, Any]:
        """
        Create complete backup of memory system
        
        Args:
            backup_dir: Directory to save backups
            namespaces: Optional list of namespaces to backup (all if None)
            
        Returns:
            Backup statistics
        """
        backup_dir_obj = Path(backup_dir)
        backup_dir_obj.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir_obj / f"memory_backup_{timestamp}.json"
        
        # If namespaces specified, export each
        if namespaces:
            all_memories = []
            for namespace in namespaces:
                from .core import MemoryQuery
                query = MemoryQuery(
                    query_type="hybrid",
                    parameters={"limit": 100000},
                    namespace=namespace,
                    requester_id="system"
                )
                memories = await self.exporter.memory_api.retrieve(query)
                all_memories.extend(memories)
            
            # Export all
            result = await self.exporter.export_memories(
                [m.memory_id for m in all_memories],
                str(backup_file)
            )
        else:
            # Export all (using wildcard namespace)
            from .core import MemoryQuery
            query = MemoryQuery(
                query_type="hybrid",
                parameters={"limit": 1000000},
                namespace=("*", "*", "*"),
                requester_id="system"
            )
            memories = await self.exporter.memory_api.retrieve(query)
            result = await self.exporter.export_memories(
                [m.memory_id for m in memories],
                str(backup_file)
            )
        
        # Create manifest
        manifest = {
            "backup_version": "1.0",
            "backup_date": timestamp,
            "backup_file": str(backup_file.name),
            "statistics": result
        }
        
        manifest_file = backup_dir_obj / f"backup_manifest_{timestamp}.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        return {
            "backup_file": str(backup_file),
            "manifest_file": str(manifest_file),
            **result
        }
    
    async def restore_backup(
        self,
        backup_file: str,
        namespace: Optional[tuple] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Restore memory system from backup
        
        Args:
            backup_file: Path to backup file
            namespace: Optional target namespace (uses original if None)
            dry_run: If True, validate but don't restore
            
        Returns:
            Restore statistics
        """
        return await self.importer.import_from_file(
            backup_file,
            namespace=namespace,
            overwrite=True,  # Allow overwrite for restore
            dry_run=dry_run
        )

