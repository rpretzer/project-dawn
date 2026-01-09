"""
Cryptographic Primitives for Project Dawn V2

Provides node identity, signing, encryption, and key exchange.
"""

from .identity import NodeIdentity
from .signing import MessageSigner, create_signed_message, verify_signed_message
from .encryption import MessageEncryptor, create_encrypted_message, decrypt_message
from .key_exchange import KeyExchange, perform_key_exchange
from .utils import (
    generate_random_bytes,
    hash_bytes,
    hash_string,
    constant_time_compare,
    derive_key_from_password,
    secure_compare,
    generate_nonce,
    generate_salt,
)

__all__ = [
    # Identity
    "NodeIdentity",
    
    # Signing
    "MessageSigner",
    "create_signed_message",
    "verify_signed_message",
    
    # Encryption
    "MessageEncryptor",
    "create_encrypted_message",
    "decrypt_message",
    
    # Key Exchange
    "KeyExchange",
    "perform_key_exchange",
    
    # Utilities
    "generate_random_bytes",
    "hash_bytes",
    "hash_string",
    "constant_time_compare",
    "derive_key_from_password",
    "secure_compare",
    "generate_nonce",
    "generate_salt",
]



