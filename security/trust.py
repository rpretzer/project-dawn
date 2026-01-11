"""
Trust Management

Manages peer trust levels and whitelisting.
"""

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime

from data_paths import data_root

logger = logging.getLogger(__name__)


class TrustLevel(Enum):
    """Trust levels for peers"""
    UNTRUSTED = "untrusted"  # Not trusted, will be rejected
    UNKNOWN = "unknown"  # Not in whitelist, requires verification
    VERIFIED = "verified"  # Verified via signature, can connect
    TRUSTED = "trusted"  # In whitelist, trusted
    BOOTSTRAP = "bootstrap"  # Bootstrap node, highly trusted


@dataclass
class TrustRecord:
    """Trust record for a peer"""
    node_id: str
    trust_level: TrustLevel
    public_key: Optional[str] = None  # Ed25519 public key (hex)
    added_at: float = 0.0
    last_verified: float = 0.0
    verified_count: int = 0
    notes: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "node_id": self.node_id,
            "trust_level": self.trust_level.value,
            "public_key": self.public_key,
            "added_at": self.added_at,
            "last_verified": self.last_verified,
            "verified_count": self.verified_count,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TrustRecord":
        """Create from dictionary"""
        return cls(
            node_id=data["node_id"],
            trust_level=TrustLevel(data["trust_level"]),
            public_key=data.get("public_key"),
            added_at=data.get("added_at", 0.0),
            last_verified=data.get("last_verified", 0.0),
            verified_count=data.get("verified_count", 0),
            notes=data.get("notes", ""),
        )


class TrustManager:
    """
    Manages peer trust and whitelisting
    
    Provides trust levels and whitelist management for peers.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize trust manager
        
        Args:
            data_dir: Data directory (defaults to data_root/mesh)
        """
        self.data_dir = data_dir or data_root() / "mesh"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trust_path = self.data_dir / "trust.json"
        
        # In-memory trust records
        self.trust_records: Dict[str, TrustRecord] = {}
        
        # Load persisted trust data
        self._load()
        
        logger.info(f"TrustManager initialized with {len(self.trust_records)} trust records")

    def _load(self) -> None:
        """Load trust records from disk"""
        if not self.trust_path.exists():
            return
        
        try:
            data = json.loads(self.trust_path.read_text(encoding="utf-8"))
            for item in data.get("trust_records", []):
                record = TrustRecord.from_dict(item)
                self.trust_records[record.node_id] = record
            logger.debug(f"Loaded {len(self.trust_records)} trust records")
        except Exception as e:
            logger.warning(f"Failed to load trust records: {e}")

    def _save(self) -> None:
        """Save trust records to disk"""
        try:
            data = {
                "version": 1,
                "trust_records": [record.to_dict() for record in self.trust_records.values()],
            }
            tmp_path = self.trust_path.with_suffix(".json.tmp")
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp_path.replace(self.trust_path)
        except Exception as e:
            logger.error(f"Failed to save trust records: {e}")

    def get_trust_level(self, node_id: str) -> TrustLevel:
        """
        Get trust level for a peer
        
        Args:
            node_id: Node ID
            
        Returns:
            Trust level
        """
        record = self.trust_records.get(node_id)
        if record:
            return record.trust_level
        return TrustLevel.UNKNOWN

    def is_trusted(self, node_id: str) -> bool:
        """
        Check if peer is trusted (can connect)
        
        Args:
            node_id: Node ID
            
        Returns:
            True if trusted or verified, False otherwise
        """
        trust_level = self.get_trust_level(node_id)
        return trust_level in (TrustLevel.VERIFIED, TrustLevel.TRUSTED, TrustLevel.BOOTSTRAP)

    def is_whitelisted(self, node_id: str) -> bool:
        """
        Check if peer is whitelisted (explicitly trusted)
        
        Args:
            node_id: Node ID
            
        Returns:
            True if whitelisted
        """
        trust_level = self.get_trust_level(node_id)
        return trust_level in (TrustLevel.TRUSTED, TrustLevel.BOOTSTRAP)

    def add_trusted_peer(
        self,
        node_id: str,
        public_key: Optional[str] = None,
        trust_level: TrustLevel = TrustLevel.TRUSTED,
        notes: str = "",
    ) -> TrustRecord:
        """
        Add a trusted peer to whitelist
        
        Args:
            node_id: Node ID
            public_key: Ed25519 public key (hex)
            trust_level: Trust level (default: TRUSTED)
            notes: Optional notes
            
        Returns:
            Trust record
        """
        import time
        record = TrustRecord(
            node_id=node_id,
            trust_level=trust_level,
            public_key=public_key,
            added_at=time.time(),
            notes=notes,
        )
        self.trust_records[node_id] = record
        self._save()
        logger.info(f"Added trusted peer: {node_id[:16]}... (level: {trust_level.value})")
        return record

    def record_verification(self, node_id: str, public_key: Optional[str] = None, audit_logger: Optional[Any] = None) -> None:
        """
        Record successful signature verification
        
        Args:
            node_id: Node ID
            public_key: Ed25519 public key (hex)
            audit_logger: Optional audit logger for security events
        """
        import time
        from .audit import AuditEventType
        
        record = self.trust_records.get(node_id)
        was_unknown = record is None or record.trust_level == TrustLevel.UNKNOWN
        
        if not record:
            # Create new record for verified peer
            record = TrustRecord(
                node_id=node_id,
                trust_level=TrustLevel.VERIFIED,
                public_key=public_key,
                added_at=time.time(),
            )
            self.trust_records[node_id] = record
        
        record.last_verified = time.time()
        record.verified_count += 1
        if public_key and not record.public_key:
            record.public_key = public_key
        
        # Upgrade from UNKNOWN to VERIFIED if not already higher
        if record.trust_level == TrustLevel.UNKNOWN:
            record.trust_level = TrustLevel.VERIFIED
        
        self._save()
        logger.debug(f"Recorded verification for {node_id[:16]}... (count: {record.verified_count})")
        
        # Log audit event
        if audit_logger:
            audit_logger.log_event(
                event_type=AuditEventType.PEER_VERIFIED,
                peer_node_id=node_id,
                success=True,
                metadata={
                    "verified_count": record.verified_count,
                    "was_unknown": was_unknown,
                }
            )

    def remove_peer(self, node_id: str) -> bool:
        """
        Remove peer from trust records
        
        Args:
            node_id: Node ID
            
        Returns:
            True if removed, False if not found
        """
        if node_id in self.trust_records:
            del self.trust_records[node_id]
            self._save()
            logger.info(f"Removed peer from trust records: {node_id[:16]}...")
            return True
        return False

    def get_trust_record(self, node_id: str) -> Optional[TrustRecord]:
        """Get trust record for a peer"""
        return self.trust_records.get(node_id)

    def list_trusted_peers(self) -> List[TrustRecord]:
        """List all trusted peers"""
        return [r for r in self.trust_records.values() if self.is_trusted(r.node_id)]

    def list_whitelisted_peers(self) -> List[TrustRecord]:
        """List all whitelisted peers"""
        return [r for r in self.trust_records.values() if self.is_whitelisted(r.node_id)]
