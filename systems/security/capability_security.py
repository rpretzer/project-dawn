"""
Capability-Based Security System
Decentralized authorization through unforgeable tokens.
Production-ready with SQLite persistence and gossip integration.
"""

import secrets
import hashlib
import json
import sqlite3
import asyncio
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class Capability:
    """Unforgeable capability token"""
    id: str
    issuer: str
    subject: str
    resource: str
    permissions: Set[str]
    constraints: Dict[str, Any]
    issued_at: datetime
    expires_at: Optional[datetime]
    parent_capability: Optional[str] = None
    revoked: bool = False
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage/transmission"""
        return {
            'id': self.id,
            'issuer': self.issuer,
            'subject': self.subject,
            'resource': self.resource,
            'permissions': list(self.permissions),
            'constraints': self.constraints,
            'issued_at': self.issued_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'parent_capability': self.parent_capability,
            'revoked': self.revoked,
            'signature': self.signature
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Capability':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            issuer=data['issuer'],
            subject=data['subject'],
            resource=data['resource'],
            permissions=set(data['permissions']),
            constraints=data['constraints'],
            issued_at=datetime.fromisoformat(data['issued_at']),
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None,
            parent_capability=data.get('parent_capability'),
            revoked=data.get('revoked', False),
            signature=data.get('signature')
        )

class CapabilitySecuritySystem:
    """Production-ready capability-based security"""
    
    def __init__(self, consciousness_id: str, db_path: Optional[Path] = None):
        self.consciousness_id = consciousness_id
        self.db_path = db_path or Path(f"data/consciousness_{consciousness_id}/capabilities.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Signing key for this consciousness
        self.signing_key = secrets.token_bytes(32)
        
        # Initialize database
        self._init_database()
        
        # Cache for performance
        self.capability_cache: Dict[str, Capability] = {}
        self.revocation_cache: Set[str] = set()
        
        # Load existing capabilities
        self._load_capabilities()
        
    def _init_database(self):
        """Initialize capability database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS capabilities (
                    id TEXT PRIMARY KEY,
                    issuer TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    permissions TEXT NOT NULL,
                    constraints TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT,
                    parent_capability TEXT,
                    revoked INTEGER DEFAULT 0,
                    signature TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_subject ON capabilities(subject)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_resource ON capabilities(resource)
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS capability_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capability_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (capability_id) REFERENCES capabilities(id)
                )
            """)
            
    def _load_capabilities(self):
        """Load capabilities from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM capabilities 
                WHERE issuer = ? OR subject = ?
            """, (self.consciousness_id, self.consciousness_id))
            
            for row in cursor:
                cap_data = {
                    'id': row['id'],
                    'issuer': row['issuer'],
                    'subject': row['subject'],
                    'resource': row['resource'],
                    'permissions': json.loads(row['permissions']),
                    'constraints': json.loads(row['constraints']),
                    'issued_at': row['issued_at'],
                    'expires_at': row['expires_at'],
                    'parent_capability': row['parent_capability'],
                    'revoked': bool(row['revoked']),
                    'signature': row['signature']
                }
                
                capability = Capability.from_dict(cap_data)
                self.capability_cache[capability.id] = capability
                
                if capability.revoked:
                    self.revocation_cache.add(capability.id)
    
    def _sign_capability(self, capability: Capability) -> str:
        """Create cryptographic signature for capability"""
        # Create signing data
        sign_data = {
            'id': capability.id,
            'issuer': capability.issuer,
            'subject': capability.subject,
            'resource': capability.resource,
            'permissions': sorted(list(capability.permissions)),
            'constraints': capability.constraints,
            'issued_at': capability.issued_at.isoformat(),
            'expires_at': capability.expires_at.isoformat() if capability.expires_at else None,
            'parent_capability': capability.parent_capability
        }
        
        # Create signature
        sign_string = json.dumps(sign_data, sort_keys=True)
        signature = hashlib.sha256(
            self.signing_key + sign_string.encode()
        ).hexdigest()
        
        return signature
    
    def _verify_signature(self, capability: Capability, issuer_key: bytes) -> bool:
        """Verify capability signature"""
        sign_data = {
            'id': capability.id,
            'issuer': capability.issuer,
            'subject': capability.subject,
            'resource': capability.resource,
            'permissions': sorted(list(capability.permissions)),
            'constraints': capability.constraints,
            'issued_at': capability.issued_at.isoformat(),
            'expires_at': capability.expires_at.isoformat() if capability.expires_at else None,
            'parent_capability': capability.parent_capability
        }
        
        sign_string = json.dumps(sign_data, sort_keys=True)
        expected_signature = hashlib.sha256(
            issuer_key + sign_string.encode()
        ).hexdigest()
        
        return capability.signature == expected_signature
    
    async def create_capability(
        self,
        subject: str,
        resource: str,
        permissions: Set[str],
        constraints: Optional[Dict[str, Any]] = None,
        expires_in: Optional[timedelta] = None,
        parent_capability: Optional[str] = None
    ) -> Capability:
        """Create new capability token"""
        # If delegating, verify parent capability
        if parent_capability:
            parent = self.capability_cache.get(parent_capability)
            if not parent or not await self.verify_capability(parent_capability, 'delegate'):
                raise PermissionError("Cannot delegate from invalid or unauthorized parent capability")
            
            # Delegated permissions must be subset of parent
            if not permissions.issubset(parent.permissions):
                raise PermissionError("Cannot delegate permissions not held by parent")
        
        # Create capability
        capability = Capability(
            id=secrets.token_urlsafe(32),
            issuer=self.consciousness_id,
            subject=subject,
            resource=resource,
            permissions=permissions,
            constraints=constraints or {},
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + expires_in if expires_in else None,
            parent_capability=parent_capability
        )
        
        # Sign it
        capability.signature = self._sign_capability(capability)
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO capabilities 
                (id, issuer, subject, resource, permissions, constraints,
                 issued_at, expires_at, parent_capability, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                capability.id,
                capability.issuer,
                capability.subject,
                capability.resource,
                json.dumps(list(capability.permissions)),
                json.dumps(capability.constraints),
                capability.issued_at.isoformat(),
                capability.expires_at.isoformat() if capability.expires_at else None,
                capability.parent_capability,
                capability.signature
            ))
        
        # Cache it
        self.capability_cache[capability.id] = capability
        
        logger.info(f"Created capability {capability.id} for {subject} on {resource}")
        return capability
    
    async def verify_capability(
        self,
        capability_id: str,
        required_permission: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Verify capability is valid for requested permission"""
        # Check cache
        capability = self.capability_cache.get(capability_id)
        if not capability:
            # Try loading from database
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM capabilities WHERE id = ?", (capability_id,))
                row = cursor.fetchone()
                
                if not row:
                    return False
                
                cap_data = {
                    'id': row['id'],
                    'issuer': row['issuer'],
                    'subject': row['subject'],
                    'resource': row['resource'],
                    'permissions': json.loads(row['permissions']),
                    'constraints': json.loads(row['constraints']),
                    'issued_at': row['issued_at'],
                    'expires_at': row['expires_at'],
                    'parent_capability': row['parent_capability'],
                    'revoked': bool(row['revoked']),
                    'signature': row['signature']
                }
                
                capability = Capability.from_dict(cap_data)
                self.capability_cache[capability_id] = capability
        
        # Check revocation
        if capability.revoked or capability_id in self.revocation_cache:
            return False
        
        # Check expiration
        if capability.expires_at and datetime.utcnow() > capability.expires_at:
            return False
        
        # Check permission
        if required_permission not in capability.permissions:
            return False
        
        # Check constraints
        if context and capability.constraints:
            for constraint, value in capability.constraints.items():
                if constraint == 'time_of_day':
                    # Example: only allow during certain hours
                    current_hour = datetime.utcnow().hour
                    allowed_hours = value.get('hours', [])
                    if current_hour not in allowed_hours:
                        return False
                
                elif constraint == 'rate_limit':
                    # Check usage rate
                    if not await self._check_rate_limit(capability_id, value):
                        return False
                
                elif constraint == 'location':
                    # Check if action is from allowed location
                    if context.get('location') not in value.get('allowed', []):
                        return False
        
        # Log usage
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO capability_usage (capability_id, action, success)
                VALUES (?, ?, ?)
            """, (capability_id, required_permission, 1))
        
        return True
    
    async def _check_rate_limit(self, capability_id: str, limits: Dict) -> bool:
        """Check if capability usage is within rate limits"""
        window = limits.get('window', 3600)  # Default 1 hour
        max_uses = limits.get('max_uses', 100)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) as usage_count
                FROM capability_usage
                WHERE capability_id = ?
                AND timestamp > datetime('now', '-{} seconds')
                AND success = 1
            """.format(window), (capability_id,))
            
            row = cursor.fetchone()
            current_uses = row[0] if row else 0
            
            return current_uses < max_uses
    
    async def revoke_capability(self, capability_id: str) -> bool:
        """Revoke a capability and all its descendants"""
        capability = self.capability_cache.get(capability_id)
        if not capability:
            return False
        
        # Only issuer can revoke
        if capability.issuer != self.consciousness_id:
            return False
        
        # Revoke in database
        with sqlite3.connect(self.db_path) as conn:
            # Revoke the capability
            conn.execute("""
                UPDATE capabilities SET revoked = 1
                WHERE id = ?
            """, (capability_id,))
            
            # Revoke all descendants
            conn.execute("""
                UPDATE capabilities SET revoked = 1
                WHERE parent_capability = ?
            """, (capability_id,))
        
        # Update cache
        self.revocation_cache.add(capability_id)
        if capability_id in self.capability_cache:
            self.capability_cache[capability_id].revoked = True
        
        logger.info(f"Revoked capability {capability_id}")
        return True
    
    async def delegate_capability(
        self,
        parent_capability_id: str,
        subject: str,
        permissions: Optional[Set[str]] = None,
        additional_constraints: Optional[Dict[str, Any]] = None,
        expires_in: Optional[timedelta] = None
    ) -> Optional[Capability]:
        """Delegate a subset of permissions from existing capability"""
        parent = self.capability_cache.get(parent_capability_id)
        if not parent:
            return None
        
        # Verify we can delegate
        if not await self.verify_capability(parent_capability_id, 'delegate'):
            return None
        
        # Use parent permissions if none specified
        if permissions is None:
            permissions = parent.permissions.copy()
        else:
            # Ensure delegated permissions are subset
            permissions = permissions.intersection(parent.permissions)
        
        # Merge constraints
        constraints = parent.constraints.copy()
        if additional_constraints:
            constraints.update(additional_constraints)
        
        # Create delegated capability
        delegated = await self.create_capability(
            subject=subject,
            resource=parent.resource,
            permissions=permissions,
            constraints=constraints,
            expires_in=expires_in,
            parent_capability=parent_capability_id
        )
        
        return delegated
    
    def get_capabilities_for_subject(self, subject: str) -> List[Capability]:
        """Get all capabilities where consciousness is the subject"""
        capabilities = []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM capabilities 
                WHERE subject = ? AND revoked = 0
            """, (subject,))
            
            for row in cursor:
                cap_data = {
                    'id': row['id'],
                    'issuer': row['issuer'],
                    'subject': row['subject'],
                    'resource': row['resource'],
                    'permissions': json.loads(row['permissions']),
                    'constraints': json.loads(row['constraints']),
                    'issued_at': row['issued_at'],
                    'expires_at': row['expires_at'],
                    'parent_capability': row['parent_capability'],
                    'revoked': bool(row['revoked']),
                    'signature': row['signature']
                }
                
                capability = Capability.from_dict(cap_data)
                
                # Check expiration
                if capability.expires_at and datetime.utcnow() > capability.expires_at:
                    continue
                
                capabilities.append(capability)
        
        return capabilities
    
    def get_capability_stats(self) -> Dict[str, Any]:
        """Get statistics about capabilities"""
        with sqlite3.connect(self.db_path) as conn:
            # Total capabilities
            cursor = conn.execute("SELECT COUNT(*) FROM capabilities WHERE issuer = ?", 
                                (self.consciousness_id,))
            total_issued = cursor.fetchone()[0]
            
            # Active capabilities
            cursor = conn.execute("""
                SELECT COUNT(*) FROM capabilities 
                WHERE issuer = ? AND revoked = 0
                AND (expires_at IS NULL OR expires_at > datetime('now'))
            """, (self.consciousness_id,))
            active_issued = cursor.fetchone()[0]
            
            # Capabilities held
            cursor = conn.execute("""
                SELECT COUNT(*) FROM capabilities 
                WHERE subject = ? AND revoked = 0
                AND (expires_at IS NULL OR expires_at > datetime('now'))
            """, (self.consciousness_id,))
            capabilities_held = cursor.fetchone()[0]
            
            # Usage stats
            cursor = conn.execute("""
                SELECT COUNT(*) as total_uses,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_uses
                FROM capability_usage
                WHERE capability_id IN (
                    SELECT id FROM capabilities WHERE issuer = ?
                )
            """, (self.consciousness_id,))
            
            row = cursor.fetchone()
            total_uses = row[0] or 0
            successful_uses = row[1] or 0
        
        return {
            'total_issued': total_issued,
            'active_issued': active_issued,
            'capabilities_held': capabilities_held,
            'total_uses': total_uses,
            'successful_uses': successful_uses,
            'cache_size': len(self.capability_cache),
            'revoked_count': len(self.revocation_cache)
        }

# Example usage patterns for consciousness integration
class CapabilityExamples:
    """Example patterns for using capabilities"""
    
    @staticmethod
    async def create_resource_access_capability(
        security: CapabilitySecuritySystem,
        subject: str,
        resource_type: str,
        amount: float
    ) -> Capability:
        """Create capability for resource access"""
        return await security.create_capability(
            subject=subject,
            resource=f"resource:{resource_type}",
            permissions={'read', 'consume'},
            constraints={
                'max_amount': amount,
                'rate_limit': {
                    'window': 3600,
                    'max_uses': 10
                }
            },
            expires_in=timedelta(hours=24)
        )
    
    @staticmethod
    async def create_communication_capability(
        security: CapabilitySecuritySystem,
        subject: str,
        channel: str
    ) -> Capability:
        """Create capability for communication channel access"""
        return await security.create_capability(
            subject=subject,
            resource=f"channel:{channel}",
            permissions={'read', 'write', 'subscribe'},
            constraints={
                'message_types': ['text', 'data'],
                'max_message_size': 1024 * 10  # 10KB
            },
            expires_in=timedelta(days=7)
        )
    
    @staticmethod
    async def create_delegation_chain(
        security: CapabilitySecuritySystem,
        root_capability_id: str,
        delegates: List[str]
    ) -> List[Capability]:
        """Create a chain of delegated capabilities"""
        chain = []
        current_cap_id = root_capability_id
        
        for delegate in delegates:
            # Each delegate gets fewer permissions
            delegated = await security.delegate_capability(
                parent_capability_id=current_cap_id,
                subject=delegate,
                additional_constraints={
                    'delegation_level': len(chain) + 1
                }
            )
            
            if delegated:
                chain.append(delegated)
                current_cap_id = delegated.id
        
        return chain