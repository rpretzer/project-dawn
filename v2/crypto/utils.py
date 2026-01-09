"""
Cryptographic Utilities

Helper functions for cryptographic operations.
"""

import hashlib
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def generate_random_bytes(length: int) -> bytes:
    """
    Generate cryptographically secure random bytes
    
    Args:
        length: Number of bytes to generate
        
    Returns:
        Random bytes
    """
    return os.urandom(length)


def hash_bytes(data: bytes, algorithm: str = "sha256") -> bytes:
    """
    Hash data using specified algorithm
    
    Args:
        data: Data to hash (bytes)
        algorithm: Hash algorithm ("sha256", "sha512", "blake2b")
        
    Returns:
        Hash digest (bytes)
    """
    if algorithm == "sha256":
        return hashlib.sha256(data).digest()
    elif algorithm == "sha512":
        return hashlib.sha512(data).digest()
    elif algorithm == "blake2b":
        return hashlib.blake2b(data).digest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def hash_string(data: str, algorithm: str = "sha256") -> str:
    """
    Hash string and return hex digest
    
    Args:
        data: String to hash
        algorithm: Hash algorithm
        
    Returns:
        Hash digest as hex string
    """
    data_bytes = data.encode('utf-8')
    return hash_bytes(data_bytes, algorithm).hex()


def constant_time_compare(a: bytes, b: bytes) -> bool:
    """
    Constant-time comparison of two byte strings
    
    Prevents timing attacks.
    
    Args:
        a: First byte string
        b: Second byte string
        
    Returns:
        True if equal, False otherwise
    """
    if len(a) != len(b):
        return False
    
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    
    return result == 0


def derive_key_from_password(password: str, salt: bytes, length: int = 32) -> bytes:
    """
    Derive key from password using PBKDF2
    
    Args:
        password: Password string
        salt: Salt bytes (should be random, 16+ bytes)
        length: Desired key length in bytes
        
    Returns:
        Derived key (bytes)
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=100000,  # High iteration count for security
        backend=default_backend()
    )
    
    password_bytes = password.encode('utf-8')
    key = kdf.derive(password_bytes)
    logger.debug(f"Derived {length}-byte key from password using PBKDF2")
    return key


def secure_compare(a: str, b: str) -> bool:
    """
    Secure string comparison (constant-time)
    
    Args:
        a: First string
        b: Second string
        
    Returns:
        True if equal, False otherwise
    """
    a_bytes = a.encode('utf-8')
    b_bytes = b.encode('utf-8')
    return constant_time_compare(a_bytes, b_bytes)


def generate_nonce(length: int = 12) -> bytes:
    """
    Generate cryptographically secure nonce
    
    Args:
        length: Nonce length in bytes (default 12 for GCM)
        
    Returns:
        Random nonce
    """
    return os.urandom(length)


def generate_salt(length: int = 16) -> bytes:
    """
    Generate cryptographically secure salt
    
    Args:
        length: Salt length in bytes (default 16)
        
    Returns:
        Random salt
    """
    return os.urandom(length)



