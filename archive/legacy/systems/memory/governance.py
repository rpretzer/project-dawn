"""
Memory Governance - Access control, compliance, and policy enforcement
"""

import re
import time
import logging
import sqlite3
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
from collections import defaultdict
import json

from .core import MemCube, MemoryState

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Evaluates access control policies"""
    
    def __init__(self, policy_config: Dict[str, Any]):
        self.policies = policy_config
        self.permission_model = policy_config.get("access_control_model", "rbac")
        
        # Default roles and permissions
        self.default_permissions = {
            "owner": ["read", "write", "delete", "share", "delegate"],
            "collaborator": ["read", "write", "share"],
            "viewer": ["read"],
            "system": ["read", "write", "delete", "audit"]
        }
    
    async def evaluate(self, 
                      user_identity: str, 
                      memory: MemCube, 
                      operation: str,
                      context: Dict[str, Any]) -> bool:
        """Evaluate if user has permission for operation"""
        # Check direct permissions
        for role, permissions in memory.access_control.items():
            if operation in permissions:
                if role == "owner" and user_identity == memory.origin_signature:
                    return True
                elif role == user_identity:
                    return True
                elif role in ["public", "anyone"] and operation == "read":
                    return True
        
        # Check namespace-based permissions
        if memory.namespace[0] == user_identity:
            # User owns the namespace
            return operation in self.default_permissions.get("owner", [])
        
        # Check context-based permissions
        if context.get("system_operation"):
            return True
        
        return False


class AuditLogger:
    """Logs all memory access for compliance"""
    
    def __init__(self, audit_config: Dict[str, Any]):
        self.config = audit_config
        self.backend = audit_config.get("backend", "sqlite")
        
        if self.backend == "sqlite":
            self.db_path = Path(audit_config.get("path", "data/audit.db"))
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_database()
    
    def _init_database(self):
        """Initialize audit database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS access_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    user_identity TEXT NOT NULL,
                    memory_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    permitted INTEGER NOT NULL,
                    context TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user ON access_log(user_identity)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory ON access_log(memory_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON access_log(timestamp)
            """)
    
    async def log_access_attempt(self,
                               user_identity: str,
                               memory_id: str,
                               operation: str,
                               permitted: bool,
                               context: Dict[str, Any]):
        """Log access attempt"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO access_log 
                (timestamp, user_identity, memory_id, operation, permitted, context, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                time.time(),
                user_identity,
                memory_id,
                operation,
                1 if permitted else 0,
                json.dumps(context),
                context.get("ip_address", "unknown"),
                context.get("user_agent", "unknown")
            ))
    
    async def get_access_history(self, 
                               user_identity: Optional[str] = None,
                               memory_id: Optional[str] = None,
                               limit: int = 100) -> List[Dict[str, Any]]:
        """Get access history"""
        conditions = []
        params = []
        
        if user_identity:
            conditions.append("user_identity = ?")
            params.append(user_identity)
        
        if memory_id:
            conditions.append("memory_id = ?")
            params.append(memory_id)
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"""
                SELECT * FROM access_log 
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            """, params + [limit])
            
            return [dict(row) for row in cursor]


class ComplianceChecker:
    """Checks for compliance violations"""
    
    def __init__(self):
        # PII patterns (simplified - in production use more comprehensive patterns)
        self.pii_patterns = {
            "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "phone": re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            "credit_card": re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')
        }
        
        # Sensitive content patterns
        self.sensitive_patterns = {
            "password": re.compile(r'password\s*[:=]\s*\S+', re.IGNORECASE),
            "api_key": re.compile(r'api[_-]?key\s*[:=]\s*\S+', re.IGNORECASE),
            "secret": re.compile(r'secret\s*[:=]\s*\S+', re.IGNORECASE)
        }
    
    def detect_pii(self, content: str) -> Dict[str, List[str]]:
        """Detect PII in content"""
        detected = defaultdict(list)
        
        for pii_type, pattern in self.pii_patterns.items():
            matches = pattern.findall(content)
            if matches:
                detected[pii_type].extend(matches)
        
        return dict(detected)
    
    def detect_sensitive(self, content: str) -> Dict[str, List[str]]:
        """Detect sensitive information"""
        detected = defaultdict(list)
        
        for info_type, pattern in self.sensitive_patterns.items():
            matches = pattern.findall(content)
            if matches:
                detected[info_type].extend(matches)
        
        return dict(detected)
    
    def redact_content(self, content: str, pii_data: Dict[str, List[str]]) -> str:
        """Redact PII from content"""
        redacted = content
        
        for pii_type, values in pii_data.items():
            for value in values:
                if pii_type == "email":
                    # Keep domain for context
                    parts = value.split('@')
                    if len(parts) == 2:
                        redacted_email = f"***@{parts[1]}"
                        redacted = redacted.replace(value, redacted_email)
                else:
                    # Replace with type indicator
                    redacted = redacted.replace(value, f"[REDACTED_{pii_type.upper()}]")
        
        return redacted


class MemGovernance:
    """Memory access control and compliance enforcement"""
    
    def __init__(self, policy_config: Dict[str, Any], audit_config: Dict[str, Any]):
        self.policy_engine = PolicyEngine(policy_config)
        self.audit_logger = AuditLogger(audit_config)
        self.compliance_checker = ComplianceChecker()
        
        # Caches
        self.permission_cache = {}  # (user, memory_id, operation) -> bool
        self.compliance_cache = {}  # memory_id -> compliance_status
        
        # Configuration
        self.config = {
            "enable_pii_detection": policy_config.get("enable_pii_detection", True),
            "auto_redact": policy_config.get("auto_redact", True),
            "cache_ttl": policy_config.get("cache_ttl", 300),  # 5 minutes
            "strict_mode": policy_config.get("strict_mode", False)
        }
    
    async def check_access(self, 
                         user_identity: str, 
                         memory: MemCube, 
                         operation: str,
                         context: Dict[str, Any]) -> bool:
        """Check if user has access permission"""
        # Check cache
        cache_key = (user_identity, memory.memory_id, operation)
        if cache_key in self.permission_cache:
            cached_result, cached_time = self.permission_cache[cache_key]
            if time.time() - cached_time < self.config["cache_ttl"]:
                return cached_result
        
        # Evaluate permission
        permitted = await self.policy_engine.evaluate(
            user_identity,
            memory,
            operation,
            context
        )
        
        # Log access attempt
        await self.audit_logger.log_access_attempt(
            user_identity,
            memory.memory_id,
            operation,
            permitted,
            context
        )
        
        # Cache result
        self.permission_cache[cache_key] = (permitted, time.time())
        
        return permitted
    
    async def apply_policies(self, memory: MemCube) -> MemCube:
        """Apply governance policies to memory"""
        # Check for expired memories
        if memory.is_expired():
            memory.transition_state(MemoryState.ARCHIVED)
        
        # Apply compliance checks
        if self.config["enable_pii_detection"]:
            memory = await self.redact_sensitive_content(memory)
        
        # Apply retention policies
        memory = await self._apply_retention_policy(memory)
        
        return memory
    
    async def redact_sensitive_content(self, memory: MemCube) -> MemCube:
        """Detect and redact sensitive content"""
        if not isinstance(memory.content, str):
            return memory
        
        # Check cache
        if memory.memory_id in self.compliance_cache:
            cached_status, cached_time = self.compliance_cache[memory.memory_id]
            if time.time() - cached_time < self.config["cache_ttl"]:
                if cached_status == "clean":
                    return memory
        
        # Detect PII
        pii_detected = self.compliance_checker.detect_pii(memory.content)
        sensitive_detected = self.compliance_checker.detect_sensitive(memory.content)
        
        if pii_detected or sensitive_detected:
            # Add compliance tags
            if "pii" not in memory.compliance_tags:
                memory.compliance_tags.append("pii")
            
            # Redact if enabled
            if self.config["auto_redact"]:
                memory.content = self.compliance_checker.redact_content(
                    memory.content,
                    pii_detected
                )
                
                # Log redaction
                logger.info(f"Redacted PII from memory {memory.memory_id}")
            
            self.compliance_cache[memory.memory_id] = ("redacted", time.time())
        else:
            self.compliance_cache[memory.memory_id] = ("clean", time.time())
        
        return memory
    
    async def _apply_retention_policy(self, memory: MemCube) -> MemCube:
        """Apply data retention policies"""
        # Check if memory should be retained
        if "legal_hold" in memory.compliance_tags:
            # Don't delete memories under legal hold
            memory.ttl = None
        
        elif "temporary" in memory.compliance_tags and not memory.ttl:
            # Set default TTL for temporary data
            memory.ttl = 86400  # 24 hours
        
        return memory
    
    async def check_compliance_violation(self, memory: MemCube) -> Optional[str]:
        """Check for compliance violations"""
        violations = []
        
        # Check size limits
        if isinstance(memory.content, str) and len(memory.content) > 10 * 1024 * 1024:
            violations.append("exceeds_size_limit")
        
        # Check forbidden content
        if self.config["strict_mode"]:
            if isinstance(memory.content, str):
                forbidden_terms = ["confidential", "restricted", "classified"]
                content_lower = memory.content.lower()
                for term in forbidden_terms:
                    if term in content_lower and "authorized" not in memory.compliance_tags:
                        violations.append(f"contains_forbidden_term:{term}")
        
        # Check namespace violations
        if memory.namespace[0] == "system" and memory.origin_signature != "system":
            violations.append("unauthorized_system_namespace")
        
        return violations[0] if violations else None
    
    def clear_cache(self):
        """Clear permission and compliance caches"""
        self.permission_cache.clear()
        self.compliance_cache.clear()
        logger.info("Governance caches cleared")
    
    async def generate_compliance_report(self, 
                                       start_time: float,
                                       end_time: float) -> Dict[str, Any]:
        """Generate compliance report for time period"""
        # Get audit logs
        with sqlite3.connect(self.audit_logger.db_path) as conn:
            cursor = conn.execute("""
                SELECT operation, permitted, COUNT(*) as count
                FROM access_log
                WHERE timestamp BETWEEN ? AND ?
                GROUP BY operation, permitted
            """, (start_time, end_time))
            
            access_stats = {}
            for row in cursor:
                key = f"{row[0]}_{'permitted' if row[1] else 'denied'}"
                access_stats[key] = row[2]
        
        return {
            "period": {
                "start": datetime.fromtimestamp(start_time).isoformat(),
                "end": datetime.fromtimestamp(end_time).isoformat()
            },
            "access_statistics": access_stats,
            "cache_stats": {
                "permission_cache_size": len(self.permission_cache),
                "compliance_cache_size": len(self.compliance_cache)
            }
        }
    
    def get_governance_stats(self) -> Dict[str, Any]:
        """Get governance statistics"""
        return {
            "permission_cache_size": len(self.permission_cache),
            "compliance_cache_size": len(self.compliance_cache),
            "config": self.config
        }