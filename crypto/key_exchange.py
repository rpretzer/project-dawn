"""
Key Exchange

Diffie-Hellman key exchange using X25519 for establishing shared secrets.
"""

import logging
from typing import Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)


class KeyExchange:
    """
    Key exchange using X25519 (Curve25519)
    
    Establishes shared secrets between two parties.
    """
    
    def __init__(self, private_key: Optional[x25519.X25519PrivateKey] = None):
        """
        Initialize key exchange
        
        Args:
            private_key: Optional existing private key. If None, generates new keypair.
        """
        if private_key is None:
            self._private_key = x25519.X25519PrivateKey.generate()
            logger.debug("Generated new X25519 keypair")
        else:
            self._private_key = private_key
            logger.debug("Using provided X25519 private key")
        
        self._public_key = self._private_key.public_key()
    
    @property
    def private_key(self) -> x25519.X25519PrivateKey:
        """Get private key"""
        return self._private_key
    
    @property
    def public_key(self) -> x25519.X25519PublicKey:
        """Get public key"""
        return self._public_key
    
    def get_public_key_bytes(self) -> bytes:
        """
        Get public key as bytes
        
        Returns:
            Public key as bytes (32 bytes)
        """
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def get_private_key_bytes(self) -> bytes:
        """
        Get private key as bytes
        
        Returns:
            Private key as bytes (32 bytes)
        """
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    def derive_shared_secret(self, peer_public_key: x25519.X25519PublicKey, salt: Optional[bytes] = None, info: Optional[bytes] = None) -> bytes:
        """
        Derive shared secret from peer's public key
        
        Args:
            peer_public_key: Peer's X25519 public key
            salt: Optional salt for HKDF (32 bytes recommended)
            info: Optional context info for HKDF
            
        Returns:
            Shared secret (32 bytes)
        """
        # Perform X25519 key exchange
        shared_key = self._private_key.exchange(peer_public_key)
        
        # Use HKDF to derive a 32-byte key from the shared secret
        # This provides additional security and ensures consistent key length
        salt = salt or b'project-dawn-v2-key-exchange'  # Default salt
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=info or b'',
            backend=default_backend()
        )
        
        derived_key = hkdf.derive(shared_key)
        logger.debug("Derived shared secret via X25519 + HKDF")
        return derived_key
    
    def derive_shared_secret_from_bytes(self, peer_public_key_bytes: bytes, salt: Optional[bytes] = None, info: Optional[bytes] = None) -> bytes:
        """
        Derive shared secret from peer's public key bytes
        
        Args:
            peer_public_key_bytes: Peer's public key as bytes (32 bytes)
            salt: Optional salt for HKDF
            info: Optional context info for HKDF
            
        Returns:
            Shared secret (32 bytes)
        """
        peer_public_key = x25519.X25519PublicKey.from_public_bytes(peer_public_key_bytes)
        return self.derive_shared_secret(peer_public_key, salt, info)
    
    @classmethod
    def from_private_key_bytes(cls, private_key_bytes: bytes) -> "KeyExchange":
        """
        Create KeyExchange from private key bytes
        
        Args:
            private_key_bytes: Private key as bytes (32 bytes)
            
        Returns:
            KeyExchange instance
        """
        private_key = x25519.X25519PrivateKey.from_private_bytes(private_key_bytes)
        return cls(private_key)
    
    @classmethod
    def from_public_key_bytes(cls, public_key_bytes: bytes) -> "KeyExchange":
        """
        Create KeyExchange from public key bytes (read-only, no key exchange)
        
        Args:
            public_key_bytes: Public key as bytes (32 bytes)
            
        Returns:
            KeyExchange instance (can only be used for verification, not key exchange)
        """
        public_key = x25519.X25519PublicKey.from_public_bytes(public_key_bytes)
        exchange = cls.__new__(cls)
        exchange._public_key = public_key
        exchange._private_key = None  # No private key, read-only
        return exchange


def perform_key_exchange(alice: KeyExchange, bob: KeyExchange, salt: Optional[bytes] = None, info: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """
    Perform key exchange between two parties
    
    Both parties derive the same shared secret.
    
    Args:
        alice: First party's KeyExchange instance
        bob: Second party's KeyExchange instance
        salt: Optional salt for HKDF
        info: Optional context info for HKDF
        
    Returns:
        Tuple of (alice_secret, bob_secret) - should be identical
    """
    alice_secret = alice.derive_shared_secret(bob.public_key, salt, info)
    bob_secret = bob.derive_shared_secret(alice.public_key, salt, info)
    
    if alice_secret != bob_secret:
        raise ValueError("Key exchange failed: secrets don't match")
    
    logger.debug("Key exchange successful, shared secret derived")
    return alice_secret, bob_secret



