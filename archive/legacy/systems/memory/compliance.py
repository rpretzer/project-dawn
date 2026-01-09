"""
GDPR/CCPA Compliance Helpers
Utilities for data privacy compliance (right to deletion, data export, consent tracking)
"""

import time
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime

from .core import MemCube
from .vault import MemVault
from .interface import MemoryAPI

logger = logging.getLogger(__name__)


@dataclass
class ComplianceRequest:
    """Represents a compliance request (deletion, export, etc.)"""
    request_id: str
    request_type: str  # "deletion", "export", "access", "portability"
    user_id: str
    namespace: Optional[tuple]
    status: str = "pending"  # "pending", "processing", "completed", "failed"
    created_at: float = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.metadata is None:
            self.metadata = {}


class ComplianceHelper:
    """
    GDPR/CCPA compliance utilities
    
    Supports:
    - Right to deletion (GDPR Article 17)
    - Right to data portability (GDPR Article 20)
    - Right to access (GDPR Article 15)
    - Consent tracking
    """
    
    def __init__(self, memory_api: MemoryAPI, vault: MemVault):
        self.memory_api = memory_api
        self.vault = vault
        self.compliance_requests: Dict[str, ComplianceRequest] = {}
    
    async def delete_user_data(
        self,
        user_id: str,
        namespace: Optional[tuple] = None,
        hard_delete: bool = False
    ) -> Dict[str, Any]:
        """
        Delete all user data (GDPR Right to Deletion / Right to be Forgotten)
        
        Args:
            user_id: User identifier
            namespace: Optional namespace filter (all if None)
            hard_delete: If True, permanently delete (False = anonymize/archive)
            
        Returns:
            Deletion statistics
        """
        from .core import MemoryQuery
        
        # Find all memories for user
        query = MemoryQuery(
            query_type="hybrid",
            parameters={"limit": 100000},
            namespace=namespace or (user_id, "*", "*"),
            requester_id="system"
        )
        
        memories = await self.memory_api.retrieve(query)
        
        # Filter to user's memories
        user_memories = [
            m for m in memories
            if m.namespace[0] == user_id or m.origin_signature == f"user:{user_id}"
        ]
        
        deleted_count = 0
        anonymized_count = 0
        
        for memory in user_memories:
            if hard_delete:
                # Permanent deletion
                await self.memory_api.delete(memory.memory_id)
                deleted_count += 1
            else:
                # Anonymize: replace content with placeholder, keep structure for audit
                memory.content = "[REDACTED - User data deleted per GDPR Article 17]"
                memory.origin_signature = "anonymized"
                memory.compliance_tags.append("gdpr_deleted")
                await self.memory_api.vault.store(memory)
                anonymized_count += 1
        
        logger.info(
            f"Deleted user data for {user_id}: "
            f"{deleted_count} hard deleted, {anonymized_count} anonymized"
        )
        
        return {
            "user_id": user_id,
            "total_memories": len(user_memories),
            "deleted_count": deleted_count,
            "anonymized_count": anonymized_count,
            "hard_delete": hard_delete
        }
    
    async def export_user_data(
        self,
        user_id: str,
        output_path: str,
        format: str = "json",
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Export all user data (GDPR Right to Data Portability)
        
        Args:
            user_id: User identifier
            output_path: Output file path
            format: Export format ("json", "jsonl")
            include_metadata: Whether to include full metadata
            
        Returns:
            Export statistics
        """
        from .export_import import MemoryExporter
        
        exporter = MemoryExporter(self.memory_api)
        
        # Export user namespace
        namespace = (user_id, "*", "*")
        result = await exporter.export_namespace(
            namespace,
            output_path,
            format=format,
            include_metadata=include_metadata
        )
        
        logger.info(f"Exported user data for {user_id} to {output_path}")
        
        return {
            "user_id": user_id,
            **result
        }
    
    async def get_user_data_summary(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get summary of user data (GDPR Right to Access)
        
        Args:
            user_id: User identifier
            
        Returns:
            Data summary
        """
        from .core import MemoryQuery
        
        query = MemoryQuery(
            query_type="hybrid",
            parameters={"limit": 100000},
            namespace=(user_id, "*", "*"),
            requester_id="system"
        )
        
        memories = await self.memory_api.retrieve(query)
        
        # Categorize by type
        by_type = {}
        by_semantic = {}
        total_size = 0
        
        for memory in memories:
            # By memory type
            mem_type = memory.memory_type.value
            by_type[mem_type] = by_type.get(mem_type, 0) + 1
            
            # By semantic type
            sem_type = memory.semantic_type
            by_semantic[sem_type] = by_semantic.get(sem_type, 0) + 1
            
            # Estimate size
            content_size = len(str(memory.content)) if memory.content else 0
            total_size += content_size
        
        # Find PII/compliance tags
        pii_count = sum(1 for m in memories if "pii" in m.compliance_tags)
        confidential_count = sum(1 for m in memories if "confidential" in m.compliance_tags)
        
        return {
            "user_id": user_id,
            "total_memories": len(memories),
            "by_type": by_type,
            "by_semantic_type": by_semantic,
            "estimated_size_bytes": total_size,
            "pii_memories": pii_count,
            "confidential_memories": confidential_count,
            "oldest_memory": min((m.timestamp for m in memories), default=None),
            "newest_memory": max((m.timestamp for m in memories), default=None),
            "exported_at": datetime.utcnow().isoformat()
        }
    
    async def track_consent(
        self,
        user_id: str,
        consent_type: str,
        granted: bool,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Track user consent for data processing
        
        Args:
            user_id: User identifier
            consent_type: Type of consent (e.g., "data_processing", "analytics")
            granted: Whether consent was granted
            metadata: Additional consent metadata
            
        Returns:
            Consent record ID
        """
        from .memory.hierarchy import MemoryHierarchy
        
        consent_content = {
            "consent_type": consent_type,
            "granted": granted,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        
        consent_memory = MemoryHierarchy.create_user_memory(
            content=consent_content,
            user_id=user_id,
            semantic_type="consent",
            context="compliance",
            compliance_tags=["consent", "gdpr"],
            priority=8  # High priority for compliance
        )
        
        consent_id = await self.memory_api.store(consent_memory)
        
        logger.info(
            f"Tracked consent for {user_id}: {consent_type} = {granted} "
            f"(memory_id: {consent_id})"
        )
        
        return consent_id
    
    async def check_consent(
        self,
        user_id: str,
        consent_type: str
    ) -> Optional[bool]:
        """
        Check if user has granted consent
        
        Args:
            user_id: User identifier
            consent_type: Type of consent to check
            
        Returns:
            True if granted, False if denied, None if not found
        """
        from .core import MemoryQuery
        
        query = MemoryQuery(
            query_type="hybrid",
            parameters={
                "text": f"consent {consent_type}",
                "limit": 10
            },
            namespace=(user_id, "compliance", "*"),
            requester_id="system"
        )
        
        memories = await self.memory_api.retrieve(query)
        
        # Find most recent consent
        consent_memories = [
            m for m in memories
            if m.semantic_type == "consent"
            and isinstance(m.content, dict)
            and m.content.get("consent_type") == consent_type
        ]
        
        if not consent_memories:
            return None
        
        # Get most recent
        latest = max(consent_memories, key=lambda m: m.timestamp)
        return latest.content.get("granted") if isinstance(latest.content, dict) else None
    
    async def anonymize_pii(
        self,
        user_id: str,
        namespace: Optional[tuple] = None
    ) -> Dict[str, Any]:
        """
        Anonymize PII in user memories (partial deletion)
        
        Args:
            user_id: User identifier
            namespace: Optional namespace filter
            
        Returns:
            Anonymization statistics
        """
        from .core import MemoryQuery
        
        query = MemoryQuery(
            query_type="hybrid",
            parameters={"limit": 100000},
            namespace=namespace or (user_id, "*", "*"),
            requester_id="system"
        )
        
        memories = await self.memory_api.retrieve(query)
        
        # Find memories with PII
        pii_memories = [
            m for m in memories
            if "pii" in m.compliance_tags
        ]
        
        anonymized_count = 0
        
        for memory in pii_memories:
            # Simple anonymization: replace content
            # In production, would use NER to identify and replace specific PII
            content_str = str(memory.content)
            if content_str:
                # Mark as anonymized
                memory.content = "[PII REDACTED]"
                memory.compliance_tags.append("anonymized")
                await self.memory_api.vault.store(memory)
                anonymized_count += 1
        
        logger.info(f"Anonymized {anonymized_count} PII memories for {user_id}")
        
        return {
            "user_id": user_id,
            "anonymized_count": anonymized_count,
            "total_pii_memories": len(pii_memories)
        }

