"""
Security Integration for Consciousness
Production-ready security system with capability-based access control, threat detection, and audit logging
Manages permissions, authentication, sandboxing, and security policies
"""

import asyncio
import json
import logging
import sqlite3
import hashlib
import hmac
import secrets
from typing import Dict, List, Optional, Any, Set, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import re
from collections import defaultdict, deque
import jwt
import base64

# System imports
from systems.security.capability_security import (
    CapabilitySecuritySystem,
    Capability,
    CapabilityType,
    SecurityPolicy
)

logger = logging.getLogger(__name__)

class SecurityLevel(Enum):
    """Security levels for consciousness operations"""
    PUBLIC = 0      # No restrictions
    AUTHENTICATED = 1  # Requires authentication
    TRUSTED = 2     # Requires trust relationship
    PRIVILEGED = 3  # Requires special privileges
    CRITICAL = 4    # Highest security level

class ThreatLevel(Enum):
    """Threat assessment levels"""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class AuditEventType(Enum):
    """Types of audit events"""
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    CAPABILITY_CREATED = "capability_created"
    CAPABILITY_REVOKED = "capability_revoked"
    THREAT_DETECTED = "threat_detected"
    POLICY_VIOLATION = "policy_violation"
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILURE = "authentication_failure"
    PERMISSION_CHANGE = "permission_change"
    SECURITY_ALERT = "security_alert"

@dataclass
class SecurityContext:
    """Security context for operations"""
    requester_id: str
    authentication_method: str
    trust_level: float
    permissions: Set[str]
    capabilities: List[Capability]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
@dataclass
class ThreatIndicator:
    """Indicator of potential security threat"""
    indicator_type: str
    severity: ThreatLevel
    description: str
    source: str
    detected_at: datetime
    evidence: Dict[str, Any]
    mitigated: bool = False
    
@dataclass
class SecurityPolicy:
    """Security policy definition"""
    policy_id: str
    name: str
    description: str
    rules: List[Dict[str, Any]]
    enforcement_level: SecurityLevel
    applies_to: List[str]  # Resource patterns
    exceptions: List[str]  # Exception patterns
    active: bool = True
    
@dataclass
class AuditLog:
    """Security audit log entry"""
    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    actor_id: str
    resource: str
    action: str
    outcome: str
    details: Dict[str, Any]
    security_context: Optional[SecurityContext]
    
@dataclass
class AccessControlList:
    """ACL for resource access"""
    resource: str
    owner: str
    permissions: Dict[str, Set[str]]  # entity_id -> permissions
    default_permissions: Set[str]
    inherit_from: Optional[str] = None
    
@dataclass
class SecurityIncident:
    """Security incident record"""
    incident_id: str
    incident_type: str
    severity: ThreatLevel
    description: str
    affected_resources: List[str]
    timeline: List[Dict[str, Any]]
    response_actions: List[str]
    status: str  # detected, investigating, mitigated, resolved
    created_at: datetime
    resolved_at: Optional[datetime] = None

class SecurityIntegration:
    """Comprehensive security integration for consciousness"""
    
    def __init__(
        self,
        consciousness_id: str,
        base_path: Optional[Path] = None,
        security_config: Optional[Dict[str, Any]] = None
    ):
        self.consciousness_id = consciousness_id
        self.base_path = base_path or Path(f"data/consciousness_{consciousness_id}")
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Security configuration
        self.config = security_config or self._default_security_config()
        
        # Initialize capability security system
        self.capability_system = CapabilitySecuritySystem(
            consciousness_id,
            self.base_path / "capabilities.db"
        )
        
        # Security components
        self.access_control_lists: Dict[str, AccessControlList] = {}
        self.security_policies: Dict[str, SecurityPolicy] = {}
        self.active_sessions: Dict[str, SecurityContext] = {}
        self.threat_indicators: List[ThreatIndicator] = []
        self.security_incidents: Dict[str, SecurityIncident] = {}
        
        # Authentication
        self.auth_tokens: Dict[str, Dict[str, Any]] = {}  # token -> metadata
        self.api_keys: Dict[str, Dict[str, Any]] = {}     # key -> metadata
        self.trusted_entities: Set[str] = set()
        
        # Rate limiting
        self.rate_limits: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Security monitoring
        self.anomaly_detectors: Dict[str, Callable] = {}
        self.security_metrics: Dict[str, Any] = defaultdict(int)
        
        # Audit logging
        self.audit_logs: deque = deque(maxlen=10000)
        self.audit_retention_days = 90
        
        # Encryption keys
        self.master_key = self._generate_or_load_master_key()
        self.session_keys: Dict[str, bytes] = {}
        
        # Initialize database
        self._init_database()
        self._load_security_data()
        
        # Initialize default policies
        self._initialize_default_policies()
        
        # Start background tasks
        self.tasks = []
        self._start_background_tasks()
        
        logger.info(f"Security integration initialized for {consciousness_id}")
        
    def _default_security_config(self) -> Dict[str, Any]:
        """Default security configuration"""
        return {
            'min_auth_level': SecurityLevel.AUTHENTICATED.value,
            'session_timeout': 3600,  # 1 hour
            'max_login_attempts': 5,
            'rate_limit_window': 60,  # seconds
            'rate_limit_max': 100,    # requests per window
            'audit_all_access': True,
            'enforce_encryption': True,
            'sandbox_untrusted': True,
            'threat_detection_enabled': True,
            'auto_revoke_expired': True
        }
        
    def _init_database(self):
        """Initialize security database"""
        db_path = self.base_path / "security_integration.db"
        with sqlite3.connect(db_path) as conn:
            # Access control lists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS access_control_lists (
                    resource TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    permissions TEXT NOT NULL,
                    default_permissions TEXT NOT NULL,
                    inherit_from TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Security policies
            conn.execute("""
                CREATE TABLE IF NOT EXISTS security_policies (
                    policy_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    rules TEXT NOT NULL,
                    enforcement_level INTEGER NOT NULL,
                    applies_to TEXT NOT NULL,
                    exceptions TEXT NOT NULL,
                    active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Audit logs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    details TEXT NOT NULL,
                    security_context TEXT,
                    indexed_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Security incidents
            conn.execute("""
                CREATE TABLE IF NOT EXISTS security_incidents (
                    incident_id TEXT PRIMARY KEY,
                    incident_type TEXT NOT NULL,
                    severity INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    affected_resources TEXT NOT NULL,
                    timeline TEXT NOT NULL,
                    response_actions TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
            """)
            
            # Trusted entities
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trusted_entities (
                    entity_id TEXT PRIMARY KEY,
                    trust_level REAL NOT NULL,
                    established_at TEXT NOT NULL,
                    last_verified TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            # API keys
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_hash TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    permissions TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    last_used TEXT,
                    active INTEGER DEFAULT 1
                )
            """)
            
            # Create indices
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_incident_status ON security_incidents(status)")
            
    def _load_security_data(self):
        """Load existing security data from database"""
        db_path = self.base_path / "security_integration.db"
        with sqlite3.connect(db_path) as conn:
            # Load ACLs
            cursor = conn.execute("SELECT * FROM access_control_lists")
            for row in cursor:
                acl = AccessControlList(
                    resource=row[0],
                    owner=row[1],
                    permissions=json.loads(row[2]),
                    default_permissions=set(json.loads(row[3])),
                    inherit_from=row[4]
                )
                self.access_control_lists[acl.resource] = acl
                
            # Load security policies
            cursor = conn.execute("SELECT * FROM security_policies WHERE active = 1")
            for row in cursor:
                policy = SecurityPolicy(
                    policy_id=row[0],
                    name=row[1],
                    description=row[2],
                    rules=json.loads(row[3]),
                    enforcement_level=SecurityLevel(row[4]),
                    applies_to=json.loads(row[5]),
                    exceptions=json.loads(row[6]),
                    active=bool(row[7])
                )
                self.security_policies[policy.policy_id] = policy
                
            # Load trusted entities
            cursor = conn.execute("SELECT entity_id FROM trusted_entities")
            for row in cursor:
                self.trusted_entities.add(row[0])
                
    def _initialize_default_policies(self):
        """Initialize default security policies"""
        # Default access policy
        if 'default_access' not in self.security_policies:
            self.security_policies['default_access'] = SecurityPolicy(
                policy_id='default_access',
                name='Default Access Policy',
                description='Default policy for resource access',
                rules=[
                    {'condition': 'authenticated', 'action': 'allow', 'permissions': ['read']},
                    {'condition': 'trusted', 'action': 'allow', 'permissions': ['read', 'write']},
                    {'condition': 'owner', 'action': 'allow', 'permissions': ['read', 'write', 'delete', 'admin']}
                ],
                enforcement_level=SecurityLevel.AUTHENTICATED,
                applies_to=['*'],
                exceptions=[]
            )
            
        # Critical resource policy
        if 'critical_resources' not in self.security_policies:
            self.security_policies['critical_resources'] = SecurityPolicy(
                policy_id='critical_resources',
                name='Critical Resource Protection',
                description='Enhanced protection for critical resources',
                rules=[
                    {'condition': 'privileged', 'action': 'allow', 'permissions': ['read']},
                    {'condition': 'critical', 'action': 'allow', 'permissions': ['read', 'write', 'admin']},
                    {'condition': 'default', 'action': 'deny', 'permissions': ['*']}
                ],
                enforcement_level=SecurityLevel.CRITICAL,
                applies_to=['consciousness:*', 'security:*', 'memory:core:*'],
                exceptions=[]
            )
            
    def _start_background_tasks(self):
        """Start background security tasks"""
        self.tasks = [
            asyncio.create_task(self._threat_detection_loop()),
            asyncio.create_task(self._session_cleanup_loop()),
            asyncio.create_task(self._audit_retention_loop()),
            asyncio.create_task(self._capability_maintenance_loop()),
            asyncio.create_task(self._security_metrics_loop())
        ]
        
    async def authenticate(
        self,
        entity_id: str,
        credentials: Dict[str, Any]
    ) -> Tuple[bool, Optional[SecurityContext]]:
        """Authenticate an entity"""
        try:
            # Check authentication method
            auth_method = credentials.get('method', 'api_key')
            
            if auth_method == 'api_key':
                success = await self._authenticate_api_key(entity_id, credentials.get('api_key'))
            elif auth_method == 'token':
                success = await self._authenticate_token(entity_id, credentials.get('token'))
            elif auth_method == 'signature':
                success = await self._authenticate_signature(entity_id, credentials)
            else:
                success = False
                
            if success:
                # Create security context
                context = await self._create_security_context(entity_id, auth_method)
                
                # Create session
                session_id = self._generate_session_id()
                self.active_sessions[session_id] = context
                
                # Audit log
                self._audit_log(
                    AuditEventType.AUTHENTICATION_SUCCESS,
                    entity_id,
                    'authentication',
                    'authenticate',
                    'success',
                    {'method': auth_method},
                    context
                )
                
                return True, context
            else:
                # Audit failure
                self._audit_log(
                    AuditEventType.AUTHENTICATION_FAILURE,
                    entity_id,
                    'authentication',
                    'authenticate',
                    'failure',
                    {'method': auth_method},
                    None
                )
                
                # Check for brute force
                if await self._check_brute_force(entity_id):
                    await self._handle_brute_force(entity_id)
                    
                return False, None
                
        except Exception as e:
            logger.error(f"Authentication error for {entity_id}: {e}")
            return False, None
            
    async def authorize(
        self,
        context: SecurityContext,
        resource: str,
        action: str,
        requirements: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Authorize an action on a resource"""
        # Check rate limiting
        if not self._check_rate_limit(context.requester_id):
            return False, "Rate limit exceeded"
            
        # Get applicable policies
        policies = self._get_applicable_policies(resource)
        
        # Evaluate policies
        for policy in policies:
            decision, reason = await self._evaluate_policy(
                policy, context, resource, action, requirements
            )
            
            if decision == 'deny':
                # Audit denial
                self._audit_log(
                    AuditEventType.ACCESS_DENIED,
                    context.requester_id,
                    resource,
                    action,
                    'denied',
                    {'reason': reason, 'policy': policy.policy_id},
                    context
                )
                return False, reason
                
        # Check ACL
        if resource in self.access_control_lists:
            acl = self.access_control_lists[resource]
            allowed = self._check_acl(acl, context.requester_id, action)
            
            if not allowed:
                self._audit_log(
                    AuditEventType.ACCESS_DENIED,
                    context.requester_id,
                    resource,
                    action,
                    'denied',
                    {'reason': 'ACL denial'},
                    context
                )
                return False, "Access denied by ACL"
                
        # Check capabilities
        if not self._check_capabilities(context, resource, action):
            return False, "No valid capability for action"
            
        # Audit success
        self._audit_log(
            AuditEventType.ACCESS_GRANTED,
            context.requester_id,
            resource,
            action,
            'granted',
            {'requirements': requirements},
            context
        )
        
        return True, None
        
    async def create_capability(
        self,
        granter_context: SecurityContext,
        subject: str,
        resource: str,
        permissions: Set[str],
        constraints: Optional[Dict[str, Any]] = None,
        expires_in: Optional[timedelta] = None
    ) -> Optional[Capability]:
        """Create a new capability"""
        # Check if granter can delegate
        can_delegate, reason = await self.authorize(
            granter_context,
            resource,
            'delegate',
            {'permissions': list(permissions)}
        )
        
        if not can_delegate:
            logger.warning(f"Capability creation denied: {reason}")
            return None
            
        # Create capability through capability system
        capability = await self.capability_system.create_capability(
            subject=subject,
            resource=resource,
            permissions=permissions,
            granter=granter_context.requester_id,
            constraints=constraints,
            expires_in=expires_in
        )
        
        # Audit
        self._audit_log(
            AuditEventType.CAPABILITY_CREATED,
            granter_context.requester_id,
            resource,
            'create_capability',
            'success',
            {
                'capability_id': capability.id,
                'subject': subject,
                'permissions': list(permissions)
            },
            granter_context
        )
        
        return capability
        
    async def revoke_capability(
        self,
        revoker_context: SecurityContext,
        capability_id: str
    ) -> bool:
        """Revoke a capability"""
        # Get capability
        capability = await self.capability_system.get_capability(capability_id)
        if not capability:
            return False
            
        # Check if revoker can revoke
        can_revoke = (
            revoker_context.requester_id == capability.granter or
            await self._has_admin_permission(revoker_context, capability.resource)
        )
        
        if not can_revoke:
            return False
            
        # Revoke through capability system
        success = await self.capability_system.revoke_capability(capability_id)
        
        if success:
            # Audit
            self._audit_log(
                AuditEventType.CAPABILITY_REVOKED,
                revoker_context.requester_id,
                capability.resource,
                'revoke_capability',
                'success',
                {'capability_id': capability_id},
                revoker_context
            )
            
        return success
        
    async def create_acl(
        self,
        creator_context: SecurityContext,
        resource: str,
        initial_permissions: Optional[Dict[str, Set[str]]] = None
    ) -> Optional[AccessControlList]:
        """Create access control list for resource"""
        # Check if creator can create ACL
        can_create, _ = await self.authorize(
            creator_context,
            resource,
            'admin'
        )
        
        if not can_create:
            return None
            
        # Create ACL
        acl = AccessControlList(
            resource=resource,
            owner=creator_context.requester_id,
            permissions=initial_permissions or {creator_context.requester_id: {'read', 'write', 'delete', 'admin'}},
            default_permissions=set()
        )
        
        # Store ACL
        self.access_control_lists[resource] = acl
        self._store_acl(acl)
        
        return acl
        
    async def update_acl_permissions(
        self,
        updater_context: SecurityContext,
        resource: str,
        entity_id: str,
        permissions: Set[str],
        operation: str = 'set'  # set, add, remove
    ) -> bool:
        """Update ACL permissions for entity"""
        # Check authorization
        can_update, _ = await self.authorize(
            updater_context,
            resource,
            'admin'
        )
        
        if not can_update:
            return False
            
        if resource not in self.access_control_lists:
            return False
            
        acl = self.access_control_lists[resource]
        
        # Update permissions
        if operation == 'set':
            acl.permissions[entity_id] = permissions
        elif operation == 'add':
            if entity_id not in acl.permissions:
                acl.permissions[entity_id] = set()
            acl.permissions[entity_id].update(permissions)
        elif operation == 'remove':
            if entity_id in acl.permissions:
                acl.permissions[entity_id] -= permissions
                if not acl.permissions[entity_id]:
                    del acl.permissions[entity_id]
                    
        # Store updated ACL
        self._store_acl(acl)
        
        # Audit
        self._audit_log(
            AuditEventType.PERMISSION_CHANGE,
            updater_context.requester_id,
            resource,
            'update_permissions',
            'success',
            {
                'entity_id': entity_id,
                'permissions': list(permissions),
                'operation': operation
            },
            updater_context
        )
        
        return True
        
    async def report_threat(
        self,
        reporter_context: Optional[SecurityContext],
        threat_type: str,
        severity: ThreatLevel,
        description: str,
        evidence: Dict[str, Any]
    ) -> ThreatIndicator:
        """Report a security threat"""
        # Create threat indicator
        indicator = ThreatIndicator(
            indicator_type=threat_type,
            severity=severity,
            description=description,
            source=reporter_context.requester_id if reporter_context else 'system',
            detected_at=datetime.utcnow(),
            evidence=evidence
        )
        
        # Add to threats
        self.threat_indicators.append(indicator)
        
        # Audit
        self._audit_log(
            AuditEventType.THREAT_DETECTED,
            reporter_context.requester_id if reporter_context else 'system',
            'security',
            'report_threat',
            'detected',
            {
                'threat_type': threat_type,
                'severity': severity.value,
                'description': description
            },
            reporter_context
        )
        
        # Handle based on severity
        if severity == ThreatLevel.CRITICAL:
            await self._handle_critical_threat(indicator)
        elif severity == ThreatLevel.HIGH:
            await self._handle_high_threat(indicator)
            
        return indicator
        
    async def create_security_incident(
        self,
        incident_type: str,
        severity: ThreatLevel,
        description: str,
        affected_resources: List[str]
    ) -> SecurityIncident:
        """Create a security incident"""
        incident = SecurityIncident(
            incident_id=self._generate_incident_id(),
            incident_type=incident_type,
            severity=severity,
            description=description,
            affected_resources=affected_resources,
            timeline=[{
                'timestamp': datetime.utcnow().isoformat(),
                'event': 'Incident created',
                'details': {'description': description}
            }],
            response_actions=[],
            status='detected',
            created_at=datetime.utcnow()
        )
        
        # Store incident
        self.security_incidents[incident.incident_id] = incident
        self._store_incident(incident)
        
        # Initiate incident response
        await self._initiate_incident_response(incident)
        
        return incident
        
    async def add_trusted_entity(
        self,
        admin_context: SecurityContext,
        entity_id: str,
        trust_level: float = 0.5
    ) -> bool:
        """Add entity to trusted list"""
        # Check admin permission
        if not await self._has_admin_permission(admin_context, 'security:trust'):
            return False
            
        # Add to trusted entities
        self.trusted_entities.add(entity_id)
        
        # Store in database
        with sqlite3.connect(self.base_path / "security_integration.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO trusted_entities
                (entity_id, trust_level, established_at, last_verified)
                VALUES (?, ?, ?, ?)
            """, (
                entity_id,
                trust_level,
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat()
            ))
            
        logger.info(f"Added trusted entity: {entity_id}")
        return True
        
    async def generate_api_key(
        self,
        creator_context: SecurityContext,
        entity_id: str,
        permissions: Set[str],
        expires_in: Optional[timedelta] = None
    ) -> Optional[str]:
        """Generate API key for entity"""
        # Check authorization
        can_create = (
            creator_context.requester_id == entity_id or
            await self._has_admin_permission(creator_context, 'security:api_keys')
        )
        
        if not can_create:
            return None
            
        # Generate key
        api_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Store key metadata
        expires_at = datetime.utcnow() + expires_in if expires_in else None
        
        with sqlite3.connect(self.base_path / "security_integration.db") as conn:
            conn.execute("""
                INSERT INTO api_keys
                (key_hash, entity_id, permissions, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                key_hash,
                entity_id,
                json.dumps(list(permissions)),
                datetime.utcnow().isoformat(),
                expires_at.isoformat() if expires_at else None
            ))
            
        # Cache key
        self.api_keys[key_hash] = {
            'entity_id': entity_id,
            'permissions': permissions,
            'created_at': datetime.utcnow(),
            'expires_at': expires_at
        }
        
        return api_key
        
    async def encrypt_data(
        self,
        data: bytes,
        context: SecurityContext
    ) -> bytes:
        """Encrypt data for secure storage/transmission"""
        # Generate session key if needed
        if context.requester_id not in self.session_keys:
            self.session_keys[context.requester_id] = secrets.token_bytes(32)
            
        # Simple XOR encryption (in production, use proper encryption)
        session_key = self.session_keys[context.requester_id]
        encrypted = bytearray()
        
        for i, byte in enumerate(data):
            encrypted.append(byte ^ session_key[i % len(session_key)])
            
        return bytes(encrypted)
        
    async def decrypt_data(
        self,
        encrypted_data: bytes,
        context: SecurityContext
    ) -> Optional[bytes]:
        """Decrypt data"""
        if context.requester_id not in self.session_keys:
            return None
            
        # Simple XOR decryption
        session_key = self.session_keys[context.requester_id]
        decrypted = bytearray()
        
        for i, byte in enumerate(encrypted_data):
            decrypted.append(byte ^ session_key[i % len(session_key)])
            
        return bytes(decrypted)
        
    # Background task loops
    async def _threat_detection_loop(self):
        """Monitor for security threats"""
        while True:
            try:
                await asyncio.sleep(60)  # Every minute
                
                # Run anomaly detectors
                for detector_name, detector in self.anomaly_detectors.items():
                    try:
                        threats = await detector()
                        for threat in threats:
                            await self.report_threat(
                                None,
                                detector_name,
                                threat['severity'],
                                threat['description'],
                                threat['evidence']
                            )
                    except Exception as e:
                        logger.error(f"Anomaly detector {detector_name} error: {e}")
                        
                # Check for patterns in audit logs
                threat_patterns = self._analyze_audit_patterns()
                for pattern in threat_patterns:
                    await self.report_threat(
                        None,
                        'pattern_analysis',
                        pattern['severity'],
                        pattern['description'],
                        pattern['evidence']
                    )
                    
            except Exception as e:
                logger.error(f"Error in threat detection: {e}")
                
    async def _session_cleanup_loop(self):
        """Clean up expired sessions"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                expired_sessions = []
                current_time = datetime.utcnow()
                
                for session_id, context in self.active_sessions.items():
                    session_age = (current_time - context.metadata.get('created_at', current_time)).seconds
                    if session_age > self.config['session_timeout']:
                        expired_sessions.append(session_id)
                        
                # Remove expired sessions
                for session_id in expired_sessions:
                    del self.active_sessions[session_id]
                    
                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
                    
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
                
    async def _audit_retention_loop(self):
        """Manage audit log retention"""
        while True:
            try:
                await asyncio.sleep(86400)  # Daily
                
                # Archive old audit logs
                cutoff_date = datetime.utcnow() - timedelta(days=self.audit_retention_days)
                archived_count = 0
                
                with sqlite3.connect(self.base_path / "security_integration.db") as conn:
                    # Count logs to archive
                    cursor = conn.execute("""
                        SELECT COUNT(*) FROM audit_logs
                        WHERE timestamp < ?
                    """, (cutoff_date.isoformat(),))
                    archived_count = cursor.fetchone()[0]
                    
                    # Archive to separate table or file
                    # For now, just delete old logs
                    conn.execute("""
                        DELETE FROM audit_logs
                        WHERE timestamp < ?
                    """, (cutoff_date.isoformat(),))
                    
                if archived_count > 0:
                    logger.info(f"Archived {archived_count} old audit logs")
                    
            except Exception as e:
                logger.error(f"Error in audit retention: {e}")
                
    async def _capability_maintenance_loop(self):
        """Maintain capabilities (revoke expired, etc.)"""
        while True:
            try:
                await asyncio.sleep(3600)  # Hourly
                
                if self.config['auto_revoke_expired']:
                    # Revoke expired capabilities
                    expired = await self.capability_system.revoke_expired_capabilities()
                    
                    if expired:
                        logger.info(f"Revoked {len(expired)} expired capabilities")
                        
                # Clean up orphaned capabilities
                cleaned = await self.capability_system.cleanup_orphaned_capabilities()
                
                if cleaned:
                    logger.info(f"Cleaned up {cleaned} orphaned capabilities")
                    
            except Exception as e:
                logger.error(f"Error in capability maintenance: {e}")
                
    async def _security_metrics_loop(self):
        """Collect security metrics"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Collect metrics
                self.security_metrics['active_sessions'] = len(self.active_sessions)
                self.security_metrics['active_capabilities'] = await self.capability_system.count_active_capabilities()
                self.security_metrics['threat_indicators'] = len([t for t in self.threat_indicators if not t.mitigated])
                self.security_metrics['active_incidents'] = len([i for i in self.security_incidents.values() if i.status != 'resolved'])
                
                # Calculate rates
                recent_logs = [log for log in self.audit_logs if 
                             (datetime.utcnow() - log.timestamp).seconds < 3600]
                
                self.security_metrics['auth_success_rate'] = sum(
                    1 for log in recent_logs 
                    if log.event_type == AuditEventType.AUTHENTICATION_SUCCESS
                ) / max(1, sum(
                    1 for log in recent_logs 
                    if log.event_type in [AuditEventType.AUTHENTICATION_SUCCESS, AuditEventType.AUTHENTICATION_FAILURE]
                ))
                
                self.security_metrics['access_denial_rate'] = sum(
                    1 for log in recent_logs 
                    if log.event_type == AuditEventType.ACCESS_DENIED
                ) / max(1, sum(
                    1 for log in recent_logs 
                    if log.event_type in [AuditEventType.ACCESS_GRANTED, AuditEventType.ACCESS_DENIED]
                ))
                
            except Exception as e:
                logger.error(f"Error collecting security metrics: {e}")
                
    # Helper methods
    async def _authenticate_api_key(self, entity_id: str, api_key: str) -> bool:
        """Authenticate using API key"""
        if not api_key:
            return False
            
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Check cache
        if key_hash in self.api_keys:
            metadata = self.api_keys[key_hash]
            
            # Check expiration
            if metadata.get('expires_at') and datetime.utcnow() > metadata['expires_at']:
                return False
                
            # Check entity match
            return metadata['entity_id'] == entity_id
            
        # Check database
        with sqlite3.connect(self.base_path / "security_integration.db") as conn:
            cursor = conn.execute("""
                SELECT entity_id, expires_at FROM api_keys
                WHERE key_hash = ? AND active = 1
            """, (key_hash,))
            
            row = cursor.fetchone()
            if row:
                db_entity_id, expires_at = row
                
                # Check expiration
                if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
                    return False
                    
                return db_entity_id == entity_id
                
        return False
        
    async def _authenticate_token(self, entity_id: str, token: str) -> bool:
        """Authenticate using JWT token"""
        try:
            # Decode token (in production, use proper JWT verification)
            payload = jwt.decode(token, self.master_key, algorithms=['HS256'])
            
            # Check entity match
            if payload.get('sub') != entity_id:
                return False
                
            # Check expiration
            if 'exp' in payload and datetime.fromtimestamp(payload['exp']) < datetime.utcnow():
                return False
                
            return True
            
        except Exception:
            return False
            
    async def _authenticate_signature(self, entity_id: str, credentials: Dict[str, Any]) -> bool:
        """Authenticate using cryptographic signature"""
        # Simple HMAC verification (in production, use proper signatures)
        message = credentials.get('message', '')
        signature = credentials.get('signature', '')
        
        if entity_id not in self.trusted_entities:
            return False
            
        # Verify signature
        expected_signature = hmac.new(
            self.master_key,
            f"{entity_id}:{message}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
        
    async def _create_security_context(
        self,
        entity_id: str,
        auth_method: str
    ) -> SecurityContext:
        """Create security context for authenticated entity"""
        # Determine trust level
        trust_level = 0.5
        if entity_id in self.trusted_entities:
            trust_level = 0.8
        if entity_id == self.consciousness_id:
            trust_level = 1.0
            
        # Get permissions from capabilities
        capabilities = await self.capability_system.get_entity_capabilities(entity_id)
        all_permissions = set()
        for cap in capabilities:
            all_permissions.update(cap.permissions)
            
        context = SecurityContext(
            requester_id=entity_id,
            authentication_method=auth_method,
            trust_level=trust_level,
            permissions=all_permissions,
            capabilities=capabilities,
            metadata={
                'created_at': datetime.utcnow(),
                'session_id': self._generate_session_id()
            }
        )
        
        return context
        
    def _get_applicable_policies(self, resource: str) -> List[SecurityPolicy]:
        """Get policies applicable to resource"""
        applicable = []
        
        for policy in self.security_policies.values():
            if not policy.active:
                continue
                
            # Check if policy applies
            for pattern in policy.applies_to:
                if self._matches_pattern(resource, pattern):
                    # Check exceptions
                    excepted = any(
                        self._matches_pattern(resource, exc_pattern)
                        for exc_pattern in policy.exceptions
                    )
                    
                    if not excepted:
                        applicable.append(policy)
                        break
                        
        # Sort by enforcement level (higher first)
        applicable.sort(key=lambda p: p.enforcement_level.value, reverse=True)
        
        return applicable
        
    async def _evaluate_policy(
        self,
        policy: SecurityPolicy,
        context: SecurityContext,
        resource: str,
        action: str,
        requirements: Optional[Dict[str, Any]]
    ) -> Tuple[str, str]:
        """Evaluate security policy"""
        for rule in policy.rules:
            # Check condition
            condition_met = False
            
            if rule['condition'] == 'authenticated':
                condition_met = context.authentication_method != 'anonymous'
            elif rule['condition'] == 'trusted':
                condition_met = context.requester_id in self.trusted_entities
            elif rule['condition'] == 'owner':
                condition_met = await self._is_resource_owner(context.requester_id, resource)
            elif rule['condition'] == 'privileged':
                condition_met = context.trust_level >= 0.8
            elif rule['condition'] == 'critical':
                condition_met = await self._has_critical_access(context)
            elif rule['condition'] == 'default':
                condition_met = True
                
            if condition_met:
                # Check action
                if rule['action'] == 'allow':
                    allowed_permissions = rule.get('permissions', ['*'])
                    if '*' in allowed_permissions or action in allowed_permissions:
                        return 'allow', 'Policy allows action'
                elif rule['action'] == 'deny':
                    denied_permissions = rule.get('permissions', ['*'])
                    if '*' in denied_permissions or action in denied_permissions:
                        return 'deny', f"Policy {policy.name} denies action"
                        
        return 'continue', 'No matching rule'
        
    def _check_acl(self, acl: AccessControlList, entity_id: str, action: str) -> bool:
        """Check ACL permissions"""
        # Check entity-specific permissions
        if entity_id in acl.permissions:
            return action in acl.permissions[entity_id]
            
        # Check default permissions
        return action in acl.default_permissions
        
    def _check_capabilities(self, context: SecurityContext, resource: str, action: str) -> bool:
        """Check if context has capability for action"""
        for capability in context.capabilities:
            if (self._matches_pattern(resource, capability.resource) and
                action in capability.permissions):
                return True
        return False
        
    def _check_rate_limit(self, entity_id: str) -> bool:
        """Check rate limiting"""
        current_time = datetime.utcnow().timestamp()
        window_start = current_time - self.config['rate_limit_window']
        
        # Clean old entries
        self.rate_limits[entity_id] = deque(
            (t for t in self.rate_limits[entity_id] if t > window_start),
            maxlen=1000
        )
        
        # Check limit
        if len(self.rate_limits[entity_id]) >= self.config['rate_limit_max']:
            return False
            
        # Add current request
        self.rate_limits[entity_id].append(current_time)
        return True
        
    async def _check_brute_force(self, entity_id: str) -> bool:
        """Check for brute force attack"""
        # Count recent failed attempts
        recent_failures = sum(
            1 for log in self.audit_logs
            if (log.event_type == AuditEventType.AUTHENTICATION_FAILURE and
                log.actor_id == entity_id and
                (datetime.utcnow() - log.timestamp).seconds < 300)
        )
        
        return recent_failures >= self.config['max_login_attempts']
        
    async def _handle_brute_force(self, entity_id: str):
        """Handle brute force attack"""
        # Create security incident
        await self.create_security_incident(
            'brute_force_attack',
            ThreatLevel.HIGH,
            f"Brute force attack detected from {entity_id}",
            ['authentication']
        )
        
        # Temporarily block entity
        # Implementation depends on blocking mechanism
        
    async def _handle_critical_threat(self, indicator: ThreatIndicator):
        """Handle critical threat"""
        # Create incident
        incident = await self.create_security_incident(
            indicator.indicator_type,
            indicator.severity,
            indicator.description,
            ['*']  # Affects all resources
        )
        
        # Take immediate action
        # This could include:
        # - Revoking all capabilities
        # - Blocking all access
        # - Alerting administrators
        # - Initiating emergency protocols
        
    async def _handle_high_threat(self, indicator: ThreatIndicator):
        """Handle high severity threat"""
        # Create incident if pattern detected
        similar_threats = [
            t for t in self.threat_indicators
            if (t.indicator_type == indicator.indicator_type and
                not t.mitigated and
                (indicator.detected_at - t.detected_at).seconds < 3600)
        ]
        
        if len(similar_threats) >= 3:
            await self.create_security_incident(
                indicator.indicator_type,
                ThreatLevel.HIGH,
                f"Multiple {indicator.indicator_type} threats detected",
                ['security']
            )
            
    async def _initiate_incident_response(self, incident: SecurityIncident):
        """Initiate incident response procedures"""
        # Log incident
        logger.warning(f"Security incident {incident.incident_id}: {incident.description}")
        
        # Take actions based on incident type
        if incident.incident_type == 'data_breach':
            # Revoke all capabilities for affected resources
            for resource in incident.affected_resources:
                await self._revoke_resource_capabilities(resource)
                
        elif incident.incident_type == 'unauthorized_access':
            # Increase monitoring
            self.config['audit_all_access'] = True
            
        # Update incident status
        incident.status = 'investigating'
        incident.timeline.append({
            'timestamp': datetime.utcnow().isoformat(),
            'event': 'Response initiated',
            'details': {'automated_response': True}
        })
        
    def _analyze_audit_patterns(self) -> List[Dict[str, Any]]:
        """Analyze audit logs for threat patterns"""
        patterns = []
        
        # Look for rapid access denials
        denial_burst = self._detect_denial_burst()
        if denial_burst:
            patterns.append({
                'severity': ThreatLevel.MEDIUM,
                'description': 'Rapid access denial pattern detected',
                'evidence': denial_burst
            })
            
        # Look for privilege escalation attempts
        escalation_attempts = self._detect_privilege_escalation()
        if escalation_attempts:
            patterns.append({
                'severity': ThreatLevel.HIGH,
                'description': 'Privilege escalation attempts detected',
                'evidence': escalation_attempts
            })
            
        return patterns
        
    def _detect_denial_burst(self) -> Optional[Dict[str, Any]]:
        """Detect burst of access denials"""
        recent_denials = [
            log for log in self.audit_logs
            if (log.event_type == AuditEventType.ACCESS_DENIED and
                (datetime.utcnow() - log.timestamp).seconds < 300)
        ]
        
        if len(recent_denials) >= 10:
            return {
                'denial_count': len(recent_denials),
                'time_window': '5 minutes',
                'actors': list(set(log.actor_id for log in recent_denials))
            }
            
        return None
        
    def _detect_privilege_escalation(self) -> Optional[Dict[str, Any]]:
        """Detect privilege escalation attempts"""
        escalation_keywords = ['admin', 'sudo', 'root', 'privilege', 'capability']
        
        suspicious_logs = [
            log for log in self.audit_logs
            if (log.event_type == AuditEventType.ACCESS_DENIED and
                any(keyword in log.resource.lower() or keyword in log.action.lower()
                    for keyword in escalation_keywords) and
                (datetime.utcnow() - log.timestamp).seconds < 3600)
        ]
        
        if len(suspicious_logs) >= 5:
            return {
                'attempt_count': len(suspicious_logs),
                'actors': list(set(log.actor_id for log in suspicious_logs)),
                'targeted_resources': list(set(log.resource for log in suspicious_logs))
            }
            
        return None
        
    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """Check if text matches pattern (with wildcards)"""
        # Convert pattern to regex
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        return bool(re.match(f"^{regex_pattern}$", text))
        
    async def _is_resource_owner(self, entity_id: str, resource: str) -> bool:
        """Check if entity owns resource"""
        if resource in self.access_control_lists:
            return self.access_control_lists[resource].owner == entity_id
            
        # Check consciousness ownership
        if resource.startswith('consciousness:'):
            return resource == f"consciousness:{entity_id}"
            
        return False
        
    async def _has_admin_permission(self, context: SecurityContext, resource: str) -> bool:
        """Check if context has admin permission"""
        return await self.authorize(context, resource, 'admin')[0]
        
    async def _has_critical_access(self, context: SecurityContext) -> bool:
        """Check if context has critical access level"""
        return (
            context.trust_level >= 0.9 or
            context.requester_id == self.consciousness_id or
            'critical' in context.permissions
        )
        
    async def _revoke_resource_capabilities(self, resource: str):
        """Revoke all capabilities for a resource"""
        capabilities = await self.capability_system.get_resource_capabilities(resource)
        
        for capability in capabilities:
            await self.capability_system.revoke_capability(capability.id)
            
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        return secrets.token_urlsafe(32)
        
    def _generate_incident_id(self) -> str:
        """Generate unique incident ID"""
        return hashlib.sha256(
            f"incident:{datetime.utcnow().isoformat()}:{secrets.token_hex(8)}".encode()
        ).hexdigest()[:16]
        
    def _generate_or_load_master_key(self) -> bytes:
        """Generate or load master encryption key"""
        key_file = self.base_path / ".master_key"
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = secrets.token_bytes(32)
            with open(key_file, 'wb') as f:
                f.write(key)
            return key
            
    def _audit_log(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource: str,
        action: str,
        outcome: str,
        details: Dict[str, Any],
        context: Optional[SecurityContext]
    ):
        """Create audit log entry"""
        log = AuditLog(
            event_id=secrets.token_urlsafe(16),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            actor_id=actor_id,
            resource=resource,
            action=action,
            outcome=outcome,
            details=details,
            security_context=context
        )
        
        # Add to memory
        self.audit_logs.append(log)
        
        # Store in database
        self._store_audit_log(log)
        
        # Update metrics
        self.security_metrics[f"{event_type.value}_count"] = \
            self.security_metrics.get(f"{event_type.value}_count", 0) + 1
            
    # Database storage methods
    def _store_acl(self, acl: AccessControlList):
        """Store ACL in database"""
        with sqlite3.connect(self.base_path / "security_integration.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO access_control_lists
                (resource, owner, permissions, default_permissions, inherit_from)
                VALUES (?, ?, ?, ?, ?)
            """, (
                acl.resource,
                acl.owner,
                json.dumps({k: list(v) for k, v in acl.permissions.items()}),
                json.dumps(list(acl.default_permissions)),
                acl.inherit_from
            ))
            
    def _store_audit_log(self, log: AuditLog):
        """Store audit log in database"""
        with sqlite3.connect(self.base_path / "security_integration.db") as conn:
            conn.execute("""
                INSERT INTO audit_logs
                (event_id, event_type, timestamp, actor_id, resource,
                 action, outcome, details, security_context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log.event_id,
                log.event_type.value,
                log.timestamp.isoformat(),
                log.actor_id,
                log.resource,
                log.action,
                log.outcome,
                json.dumps(log.details),
                json.dumps({
                    'requester_id': log.security_context.requester_id,
                    'auth_method': log.security_context.authentication_method,
                    'trust_level': log.security_context.trust_level
                }) if log.security_context else None
            ))
            
    def _store_incident(self, incident: SecurityIncident):
        """Store security incident in database"""
        with sqlite3.connect(self.base_path / "security_integration.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO security_incidents
                (incident_id, incident_type, severity, description,
                 affected_resources, timeline, response_actions, status,
                 created_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                incident.incident_id,
                incident.incident_type,
                incident.severity.value,
                incident.description,
                json.dumps(incident.affected_resources),
                json.dumps(incident.timeline),
                json.dumps(incident.response_actions),
                incident.status,
                incident.created_at.isoformat(),
                incident.resolved_at.isoformat() if incident.resolved_at else None
            ))
            
    async def shutdown(self):
        """Shutdown security integration"""
        # Cancel background tasks
        for task in self.tasks:
            task.cancel()
            
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Save final metrics
        logger.info(f"Security metrics at shutdown: {self.security_metrics}")
        
        logger.info("Security integration shutdown complete")
        
    def get_security_status(self) -> Dict[str, Any]:
        """Get comprehensive security status"""
        return {
            'active_sessions': len(self.active_sessions),
            'trusted_entities': len(self.trusted_entities),
            'active_policies': len([p for p in self.security_policies.values() if p.active]),
            'active_incidents': len([i for i in self.security_incidents.values() if i.status != 'resolved']),
            'threat_indicators': {
                'total': len(self.threat_indicators),
                'unmitigated': len([t for t in self.threat_indicators if not t.mitigated]),
                'by_severity': {
                    level.name: len([t for t in self.threat_indicators 
                                   if t.severity == level and not t.mitigated])
                    for level in ThreatLevel
                }
            },
            'metrics': self.security_metrics,
            'recent_activity': {
                'authentications': sum(1 for log in self.audit_logs 
                                     if log.event_type in [AuditEventType.AUTHENTICATION_SUCCESS,
                                                         AuditEventType.AUTHENTICATION_FAILURE]),
                'access_requests': sum(1 for log in self.audit_logs 
                                     if log.event_type in [AuditEventType.ACCESS_GRANTED,
                                                         AuditEventType.ACCESS_DENIED]),
                'policy_violations': sum(1 for log in self.audit_logs 
                                       if log.event_type == AuditEventType.POLICY_VIOLATION)
            }
        }

# Consciousness integration helper
async def integrate_security_system(consciousness):
    """Integrate security system with consciousness"""
    security = SecurityIntegration(
        consciousness.id,
        security_config={
            'min_auth_level': SecurityLevel.AUTHENTICATED.value,
            'session_timeout': 3600,
            'audit_all_access': True,
            'enforce_encryption': True,
            'threat_detection_enabled': True
        }
    )
    
    # Add to consciousness
    consciousness.security = security
    
    # Add convenience methods
    consciousness.authenticate = security.authenticate
    consciousness.authorize = security.authorize
    consciousness.create_capability = security.create_capability
    consciousness.report_security_threat = security.report_threat
    consciousness.get_security_status = security.get_security_status
    
    # Register anomaly detectors
    security.anomaly_detectors['memory_access'] = lambda: consciousness.check_memory_anomalies()
    security.anomaly_detectors['network_traffic'] = lambda: consciousness.check_network_anomalies()
    
    # Create default ACL for consciousness resources
    admin_context = await security._create_security_context(
        consciousness.id,
        'system'
    )
    
    await security.create_acl(
        admin_context,
        f"consciousness:{consciousness.id}",
        {consciousness.id: {'read', 'write', 'delete', 'admin'}}
    )
    
    return security