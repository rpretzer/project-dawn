"""
Authentication and Authorization

Provides basic authentication and permission management.
"""

import hashlib
import logging
import time
from enum import Enum
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class Permission(Enum):
    """Permissions for agents and peers"""
    # Agent permissions
    AGENT_READ = "agent:read"
    AGENT_WRITE = "agent:write"
    AGENT_EXECUTE = "agent:execute"
    
    # Peer permissions
    PEER_CONNECT = "peer:connect"
    PEER_DISCOVER = "peer:discover"
    PEER_MESSAGE = "peer:message"
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_CONFIG = "system:config"


@dataclass
class AuthToken:
    """Authentication token"""
    token_id: str
    node_id: str
    permissions: Set[Permission]
    created_at: float
    expires_at: Optional[float] = None
    description: str = ""

    def is_valid(self) -> bool:
        """Check if token is still valid"""
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True

    def has_permission(self, permission: Permission) -> bool:
        """Check if token has a permission"""
        return permission in self.permissions or Permission.SYSTEM_ADMIN in self.permissions


class AuthManager:
    """
    Authentication and authorization manager
    
    Manages API keys, tokens, and permissions for agents and peers.
    """

    def __init__(self):
        """Initialize auth manager"""
        # Token storage: token_id -> AuthToken
        self.tokens: Dict[str, AuthToken] = {}
        
        # Node permissions: node_id -> Set[Permission]
        self.node_permissions: Dict[str, Set[Permission]] = {}
        
        logger.debug("AuthManager initialized")

    def create_token(
        self,
        node_id: str,
        permissions: List[Permission],
        expires_in: Optional[float] = None,
        description: str = "",
    ) -> str:
        """
        Create an authentication token
        
        Args:
            node_id: Node ID for this token
            permissions: List of permissions
            expires_in: Expiration time in seconds (None = no expiration)
            description: Token description
            
        Returns:
            Token ID (hex string)
        """
        import secrets
        token_id = secrets.token_hex(32)
        
        expires_at = None
        if expires_in:
            expires_at = time.time() + expires_in
        
        token = AuthToken(
            token_id=token_id,
            node_id=node_id,
            permissions=set(permissions),
            created_at=time.time(),
            expires_at=expires_at,
            description=description,
        )
        
        self.tokens[token_id] = token
        logger.info(f"Created token for {node_id[:16]}... with {len(permissions)} permissions")
        return token_id

    def validate_token(self, token_id: str) -> Optional[AuthToken]:
        """
        Validate an authentication token
        
        Args:
            token_id: Token ID
            
        Returns:
            AuthToken if valid, None otherwise
        """
        token = self.tokens.get(token_id)
        if token and token.is_valid():
            return token
        return None

    def revoke_token(self, token_id: str) -> bool:
        """
        Revoke a token
        
        Args:
            token_id: Token ID
            
        Returns:
            True if revoked, False if not found
        """
        if token_id in self.tokens:
            del self.tokens[token_id]
            logger.info(f"Revoked token: {token_id[:16]}...")
            return True
        return False

    def grant_permission(self, node_id: str, permission: Permission) -> None:
        """
        Grant a permission to a node
        
        Args:
            node_id: Node ID
            permission: Permission to grant
        """
        if node_id not in self.node_permissions:
            self.node_permissions[node_id] = set()
        self.node_permissions[node_id].add(permission)
        logger.debug(f"Granted {permission.value} to {node_id[:16]}...")

    def revoke_permission(self, node_id: str, permission: Permission) -> None:
        """
        Revoke a permission from a node
        
        Args:
            node_id: Node ID
            permission: Permission to revoke
        """
        if node_id in self.node_permissions:
            self.node_permissions[node_id].discard(permission)
            logger.debug(f"Revoked {permission.value} from {node_id[:16]}...")

    def has_permission(self, node_id: str, permission: Permission) -> bool:
        """
        Check if a node has a permission
        
        Args:
            node_id: Node ID
            permission: Permission to check
            
        Returns:
            True if node has permission
        """
        # Check node permissions
        if node_id in self.node_permissions:
            perms = self.node_permissions[node_id]
            if permission in perms or Permission.SYSTEM_ADMIN in perms:
                return True
        
        # Default permissions for local node
        # Local node has all permissions
        return False

    def check_permission(self, node_id: str, permission: Permission) -> bool:
        """
        Check permission (alias for has_permission)
        
        Args:
            node_id: Node ID
            permission: Permission to check
            
        Returns:
            True if allowed, False otherwise
        """
        return self.has_permission(node_id, permission)
