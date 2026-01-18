"""
Symmetric Encryption

End-to-end encryption using AES-256-GCM.
"""

import logging
import os
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


class MessageEncryptor:
    """
    Message encryption and decryption
    
    Uses AES-256-GCM for authenticated encryption.
    """
    
    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize message encryptor
        
        Args:
            key: Optional 32-byte key. If None, generates new key.
        """
        if key is None:
            key = os.urandom(32)  # 32 bytes = 256 bits
            logger.debug("Generated new AES-256 key")
        elif len(key) != 32:
            raise ValueError("Key must be 32 bytes (256 bits)")
        
        self.key = key
        self.aesgcm = AESGCM(key)
        logger.debug("MessageEncryptor initialized")
    
    def encrypt(self, plaintext: bytes, associated_data: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """
        Encrypt plaintext
        
        Args:
            plaintext: Message to encrypt (bytes)
            associated_data: Optional associated data (authenticated but not encrypted)
            
        Returns:
            Tuple of (nonce, ciphertext). Nonce is 12 bytes, ciphertext includes 16-byte tag.
        """
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, associated_data)
        logger.debug(f"Encrypted {len(plaintext)} bytes -> {len(ciphertext)} bytes ciphertext")
        return nonce, ciphertext
    
    def encrypt_string(self, plaintext: str, associated_data: Optional[str] = None) -> Tuple[bytes, bytes]:
        """
        Encrypt string
        
        Args:
            plaintext: Message to encrypt (string)
            associated_data: Optional associated data (string)
            
        Returns:
            Tuple of (nonce, ciphertext)
        """
        plaintext_bytes = plaintext.encode('utf-8')
        ad_bytes = associated_data.encode('utf-8') if associated_data else None
        return self.encrypt(plaintext_bytes, ad_bytes)
    
    def decrypt(self, nonce: bytes, ciphertext: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """
        Decrypt ciphertext
        
        Args:
            nonce: Nonce used for encryption (12 bytes)
            ciphertext: Encrypted message (bytes, includes 16-byte tag)
            associated_data: Optional associated data (must match encryption)
            
        Returns:
            Decrypted plaintext (bytes)
            
        Raises:
            ValueError: If decryption fails (invalid key, corrupted data, etc.)
        """
        try:
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, associated_data)
            logger.debug(f"Decrypted {len(ciphertext)} bytes -> {len(plaintext)} bytes plaintext")
            return plaintext
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError(f"Decryption failed: {e}")
    
    def decrypt_string(self, nonce: bytes, ciphertext: bytes, associated_data: Optional[str] = None) -> str:
        """
        Decrypt to string
        
        Args:
            nonce: Nonce used for encryption (12 bytes)
            ciphertext: Encrypted message (bytes)
            associated_data: Optional associated data (string)
            
        Returns:
            Decrypted plaintext (string)
        """
        ad_bytes = associated_data.encode('utf-8') if associated_data else None
        plaintext_bytes = self.decrypt(nonce, ciphertext, ad_bytes)
        return plaintext_bytes.decode('utf-8')
    
    def get_key(self) -> bytes:
        """Get encryption key"""
        return self.key
    
    def get_key_hex(self) -> str:
        """Get encryption key as hex string"""
        return self.key.hex()


def create_encrypted_message(plaintext: bytes, encryptor: MessageEncryptor, associated_data: Optional[bytes] = None) -> dict:
    """
    Create an encrypted message envelope
    
    Args:
        plaintext: Message to encrypt (bytes)
        encryptor: MessageEncryptor instance
        associated_data: Optional associated data
        
    Returns:
        Dictionary with encrypted message data
    """
    nonce, ciphertext = encryptor.encrypt(plaintext, associated_data)
    return {
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
        "associated_data": associated_data.hex() if associated_data else None,
    }


def decrypt_message(envelope: dict, encryptor: MessageEncryptor) -> Optional[bytes]:
    """
    Decrypt message from envelope
    
    Args:
        envelope: Encrypted message envelope (dict with nonce, ciphertext, associated_data)
        encryptor: MessageEncryptor instance
        
    Returns:
        Decrypted plaintext bytes if successful, None otherwise
    """
    try:
        nonce = bytes.fromhex(envelope["nonce"])
        ciphertext = bytes.fromhex(envelope["ciphertext"])
        associated_data = bytes.fromhex(envelope["associated_data"]) if envelope.get("associated_data") else None
        
        return encryptor.decrypt(nonce, ciphertext, associated_data)
    except (KeyError, ValueError) as e:
        logger.error(f"Error decrypting message: {e}")
        return None



