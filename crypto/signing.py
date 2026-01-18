"""
Digital Signatures

Message signing and verification using Ed25519.
"""

import base64
import binascii
import hashlib
import logging
from pathlib import Path
from typing import Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature
from .identity import NodeIdentity

logger = logging.getLogger(__name__)

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class MessageSigner:
    """
    Message signing and verification
    
    Uses Ed25519 for fast, secure signatures.
    """
    
    def __init__(self, identity: NodeIdentity):
        """
        Initialize message signer
        
        Args:
            identity: Node identity with signing capability
        """
        if not identity.can_sign():
            raise ValueError("Identity must have private key for signing")
        self.identity = identity
        logger.debug(f"MessageSigner initialized for node {identity.get_node_id_short()}")
    
    def sign(self, message: bytes) -> bytes:
        """
        Sign a message
        
        Args:
            message: Message to sign (bytes)
            
        Returns:
            Signature (64 bytes)
        """
        signature = self.identity.private_key.sign(message)
        logger.debug(f"Signed message ({len(message)} bytes), signature: {len(signature)} bytes")
        return signature
    
    def sign_string(self, message: str) -> bytes:
        """
        Sign a string message
        
        Args:
            message: Message to sign (string)
            
        Returns:
            Signature (64 bytes)
        """
        return self.sign(message.encode('utf-8'))
    
    def verify(self, message: bytes, signature: bytes, public_key: Optional[ed25519.Ed25519PublicKey] = None) -> bool:
        """
        Verify a message signature
        
        Args:
            message: Original message (bytes)
            signature: Signature to verify (64 bytes)
            public_key: Public key to verify against. If None, uses identity's public key.
            
        Returns:
            True if signature is valid, False otherwise
        """
        if public_key is None:
            public_key = self.identity.public_key
        
        try:
            public_key.verify(signature, message)
            logger.debug("Signature verification successful")
            return True
        except InvalidSignature:
            logger.warning("Signature verification failed")
            return False
    
    def verify_string(self, message: str, signature: bytes, public_key: Optional[ed25519.Ed25519PublicKey] = None) -> bool:
        """
        Verify a string message signature
        
        Args:
            message: Original message (string)
            signature: Signature to verify (64 bytes)
            public_key: Public key to verify against
            
        Returns:
            True if signature is valid, False otherwise
        """
        return self.verify(message.encode('utf-8'), signature, public_key)
    
    @staticmethod
    def verify_with_public_key_bytes(message: bytes, signature: bytes, public_key_bytes: bytes) -> bool:
        """
        Verify signature using public key bytes
        
        Args:
            message: Original message (bytes)
            signature: Signature to verify (64 bytes)
            public_key_bytes: Public key as bytes (32 bytes)
            
        Returns:
            True if signature is valid, False otherwise
        """
        from cryptography.hazmat.primitives.asymmetric import ed25519
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        try:
            public_key.verify(signature, message)
            return True
        except InvalidSignature:
            return False


def create_signed_message(message: bytes, signer: MessageSigner) -> dict:
    """
    Create a signed message envelope
    
    Args:
        message: Message to sign (bytes)
        signer: MessageSigner instance
        
    Returns:
        Dictionary with message, signature, and sender info
    """
    signature = signer.sign(message)
    return {
        "message": message.hex() if isinstance(message, bytes) else message,
        "signature": signature.hex(),
        "sender": signer.identity.get_node_id(),
        "sender_short": signer.identity.get_node_id_short(),
    }


def verify_signed_message(envelope: dict, public_key_bytes: bytes) -> Optional[bytes]:
    """
    Verify and extract message from signed envelope
    
    Args:
        envelope: Signed message envelope (dict with message, signature, sender)
        public_key_bytes: Public key as bytes (32 bytes)
        
    Returns:
        Original message bytes if valid, None otherwise
    """
    try:
        # Decode hex strings
        if isinstance(envelope["message"], str):
            message = bytes.fromhex(envelope["message"])
        else:
            message = envelope["message"]
        
        signature = bytes.fromhex(envelope["signature"])
        
        # Verify signature
        if MessageSigner.verify_with_public_key_bytes(message, signature, public_key_bytes):
            return message
        else:
            logger.warning("Invalid signature in message envelope")
            return None
    except (KeyError, ValueError) as e:
        logger.error(f"Error verifying signed message: {e}")
        return None


def _base58_encode(data: bytes) -> str:
    if not data:
        return ""
    num = int.from_bytes(data, "big")
    encoded = ""
    while num > 0:
        num, rem = divmod(num, 58)
        encoded = _BASE58_ALPHABET[rem] + encoded
    padding = 0
    for byte in data:
        if byte == 0:
            padding += 1
        else:
            break
    return _BASE58_ALPHABET[0] * padding + encoded


def _extract_pgp_public_key_bytes(armored: str) -> bytes:
    lines = [
        line.strip()
        for line in armored.splitlines()
        if line.strip() and not line.startswith("-----")
    ]
    payload_lines = [line for line in lines if not line.startswith("=")]
    if not payload_lines:
        raise ValueError("No PGP payload found in armored key")
    payload = "".join(payload_lines)
    try:
        return base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid base64 payload in armored key") from exc


def derive_peer_id_from_pgp_public_key(armored: str) -> str:
    """
    Derive a sovereign PeerID from a PGP public key block.
    """
    key_bytes = _extract_pgp_public_key_bytes(armored)
    digest = hashlib.sha256(key_bytes).digest()
    return _base58_encode(digest)


def derive_peer_id_from_pgp_public_key_file(path: Path) -> str:
    """
    Derive a sovereign PeerID from a PGP public key file.
    """
    armored = Path(path).read_text(encoding="utf-8")
    return derive_peer_id_from_pgp_public_key(armored)


def pgp_fingerprint_from_public_key(armored: str) -> str:
    """
    Derive a stable fingerprint for a PGP public key.
    """
    key_bytes = _extract_pgp_public_key_bytes(armored)
    return hashlib.sha256(key_bytes).hexdigest()


def pgp_fingerprint_from_public_key_file(path: Path) -> str:
    """
    Derive a stable fingerprint for a PGP public key file.
    """
    armored = Path(path).read_text(encoding="utf-8")
    return pgp_fingerprint_from_public_key(armored)
