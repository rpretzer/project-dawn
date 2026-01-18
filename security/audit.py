"""
Security Audit Logging

Provides comprehensive audit trail for security events.
"""

import json
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass

from data_paths import data_root

logger = logging.getLogger(__name__)

# Audit logger (separate from application logger)
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False  # Don't propagate to root logger


class AuditEventType(Enum):
    """Types of audit events"""
    # Authentication events
    PEER_CONNECT = "peer_connect"
    PEER_DISCONNECT = "peer_disconnect"
    CONNECTION_REJECTED = "connection_rejected"
    
    # Authorization events
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    
    # Trust events
    PEER_VERIFIED = "peer_verified"
    PEER_TRUSTED = "peer_trusted"
    PEER_UNTRUSTED = "peer_untrusted"
    TRUST_RECORD_CREATED = "trust_record_created"
    TRUST_RECORD_UPDATED = "trust_record_updated"
    
    # Security events
    SIGNATURE_VERIFIED = "signature_verified"
    SIGNATURE_FAILED = "signature_failed"
    KEY_EXCHANGE_COMPLETE = "key_exchange_complete"
    KEY_EXCHANGE_FAILED = "key_exchange_failed"
    
    # Data access events
    DATA_ACCESSED = "data_accessed"
    DATA_MODIFIED = "data_modified"
    DATA_DELETED = "data_deleted"
    
    # Configuration events
    CONFIG_CHANGED = "config_changed"
    PERMISSION_CHANGED = "permission_changed"


@dataclass
class AuditEvent:
    """Audit event record"""
    timestamp: float
    event_type: AuditEventType
    node_id: Optional[str] = None
    peer_node_id: Optional[str] = None
    agent_id: Optional[str] = None
    method: Optional[str] = None
    resource: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "node_id": self.node_id,
            "peer_node_id": self.peer_node_id,
            "agent_id": self.agent_id,
            "method": self.method,
            "resource": self.resource,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


class AuditLogger:
    """
    Security audit logger
    
    Logs security events to file and logger.
    """

    def __init__(self, data_dir: Optional[Path] = None, max_log_size: int = 100 * 1024 * 1024):
        """
        Initialize audit logger
        
        Args:
            data_dir: Data directory (defaults to data_root/vault)
            max_log_size: Maximum log file size before rotation (default 100MB)
        """
        self.data_dir = data_dir or data_root() / "vault"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log_path = self.data_dir / "audit.log"
        self.max_log_size = max_log_size
        
        # Setup file handler for audit log
        if not audit_logger.handlers:
            file_handler = logging.FileHandler(self.audit_log_path, encoding="utf-8")
            file_handler.setFormatter(
                logging.Formatter('%(message)s')
            )
            audit_logger.addHandler(file_handler)
        
        logger.info(f"AuditLogger initialized (log: {self.audit_log_path})")

    def log_event(
        self,
        event_type: AuditEventType,
        node_id: Optional[str] = None,
        peer_node_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        method: Optional[str] = None,
        resource: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log an audit event
        
        Args:
            event_type: Type of audit event
            node_id: Local node ID
            peer_node_id: Peer node ID (if applicable)
            agent_id: Agent ID (if applicable)
            method: Method/operation (if applicable)
            resource: Resource accessed (if applicable)
            success: Whether operation succeeded
            error: Error message (if failed)
            metadata: Additional metadata
        """
        event = AuditEvent(
            timestamp=time.time(),
            event_type=event_type,
            node_id=node_id,
            peer_node_id=peer_node_id,
            agent_id=agent_id,
            method=method,
            resource=resource,
            success=success,
            error=error,
            metadata=metadata,
        )
        
        # Log to file (JSON format)
        try:
            event_json = json.dumps(event.to_dict(), separators=(',', ':'))
            audit_logger.info(event_json)
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}", exc_info=True)
        
        # Rotate log if too large
        self._rotate_log_if_needed()

    def _rotate_log_if_needed(self) -> None:
        """Rotate audit log if it exceeds max size"""
        try:
            if self.audit_log_path.exists():
                size = self.audit_log_path.stat().st_size
                if size > self.max_log_size:
                    # Rotate log
                    rotated_path = self.audit_log_path.with_suffix(
                        f".{int(time.time())}.log"
                    )
                    self.audit_log_path.rename(rotated_path)
                    logger.info(f"Rotated audit log: {rotated_path}")
        except Exception as e:
            logger.warning(f"Failed to rotate audit log: {e}")

    def query_events(
        self,
        event_type: Optional[AuditEventType] = None,
        node_id: Optional[str] = None,
        peer_node_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 1000,
    ) -> list[AuditEvent]:
        """
        Query audit events
        
        Args:
            event_type: Filter by event type
            node_id: Filter by node ID
            peer_node_id: Filter by peer node ID
            start_time: Start timestamp
            end_time: End timestamp
            limit: Maximum number of events to return
            
        Returns:
            List of audit events
        """
        events = []
        
        if not self.audit_log_path.exists():
            return events
        
        try:
            with open(self.audit_log_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    
                    try:
                        event_data = json.loads(line)
                        event = AuditEvent(
                            timestamp=event_data["timestamp"],
                            event_type=AuditEventType(event_data["event_type"]),
                            node_id=event_data.get("node_id"),
                            peer_node_id=event_data.get("peer_node_id"),
                            agent_id=event_data.get("agent_id"),
                            method=event_data.get("method"),
                            resource=event_data.get("resource"),
                            success=event_data.get("success", True),
                            error=event_data.get("error"),
                            metadata=event_data.get("metadata"),
                        )
                        
                        # Apply filters
                        if event_type and event.event_type != event_type:
                            continue
                        if node_id and event.node_id != node_id:
                            continue
                        if peer_node_id and event.peer_node_id != peer_node_id:
                            continue
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue
                        
                        events.append(event)
                        
                        if len(events) >= limit:
                            break
                    except Exception as e:
                        logger.warning(f"Failed to parse audit log line: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Failed to query audit events: {e}", exc_info=True)
        
        return events
