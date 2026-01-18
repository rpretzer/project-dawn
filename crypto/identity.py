"""
Node Identity Management

Handles cryptographic identity for nodes using Ed25519 keypairs.
"""

import logging
from typing import Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)


class NodeIdentity:
    """
    Node cryptographic identity
    
    Uses Ed25519 for signing and verification.
    Public key serves as node ID.
    """
    
    def __init__(self, private_key: Optional[ed25519.Ed25519PrivateKey] = None):
        """
        Initialize node identity
        
        Args:
            private_key: Optional existing private key. If None, generates new keypair.
        """
        if private_key is None:
            self._private_key = ed25519.Ed25519PrivateKey.generate()
            logger.debug("Generated new Ed25519 keypair")
        else:
            self._private_key = private_key
            logger.debug("Using provided Ed25519 private key")
        
        self._public_key = self._private_key.public_key()
    
    @property
    def private_key(self) -> ed25519.Ed25519PrivateKey:
        """Get private key"""
        return self._private_key
    
    @property
    def public_key(self) -> ed25519.Ed25519PublicKey:
        """Get public key"""
        return self._public_key
    
    def get_node_id(self) -> str:
        """
        Get node ID from public key
        
        Returns:
            Node ID as hex string (64 characters)
        """
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return public_bytes.hex()
    
    def get_node_id_short(self) -> str:
        """
        Get short node ID (first 16 characters)
        
        Returns:
            Short node ID
        """
        return self.get_node_id()[:16]
    
    def serialize_private_key(self) -> bytes:
        """
        Serialize private key to bytes
        
        Returns:
            Private key as bytes (32 bytes)
        """
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    def serialize_public_key(self) -> bytes:
        """
        Serialize public key to bytes
        
        Returns:
            Public key as bytes (32 bytes)
        """
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    @classmethod
    def from_private_key_bytes(cls, private_key_bytes: bytes) -> "NodeIdentity":
        """
        Create NodeIdentity from private key bytes
        
        Args:
            private_key_bytes: Private key as bytes (32 bytes)
            
        Returns:
            NodeIdentity instance
        """
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        return cls(private_key)
    
    @classmethod
    def from_public_key_bytes(cls, public_key_bytes: bytes) -> "NodeIdentity":
        """
        Create NodeIdentity from public key bytes (read-only, no signing)
        
        Args:
            public_key_bytes: Public key as bytes (32 bytes)
            
        Returns:
            NodeIdentity instance (can verify but not sign)
        """
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        # Create a dummy private key - this identity can only verify, not sign
        identity = cls.__new__(cls)
        identity._public_key = public_key
        identity._private_key = None  # No private key, read-only
        return identity
    
    def can_sign(self) -> bool:
        """Check if this identity can sign messages"""
        return self._private_key is not None
    
    def __repr__(self) -> str:
        node_id = self.get_node_id_short()
        can_sign = "signing" if self.can_sign() else "read-only"
        return f"NodeIdentity(node_id={node_id}, {can_sign})"



