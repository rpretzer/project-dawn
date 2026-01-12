"""
Peer Validator

Validates peers before adding them to the registry.
"""

import logging
from typing import Optional
from crypto import MessageSigner
from crypto.identity import NodeIdentity
from .trust import TrustManager, TrustLevel

logger = logging.getLogger(__name__)


class PeerValidator:
    """
    Validates peers before registration
    
    Performs signature verification and trust checks.
    """

    def __init__(self, trust_manager: TrustManager, local_identity: NodeIdentity, audit_logger=None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize peer validator
        
        Args:
            trust_manager: Trust manager instance
            local_identity: Local node identity
            audit_logger: Audit logger (optional, for backward compatibility)
            config: Security configuration (optional, will load from config if not provided)
        """
        self.trust_manager = trust_manager
        self.local_identity = local_identity
        self.audit_logger = audit_logger
        
        # Load config
        if config is None:
            try:
                from config import get_config
                config = get_config().security
            except Exception:
                config = {}
        
        self.reject_unknown = config.get("reject_unknown", False)
        logger.debug(f"PeerValidator initialized (reject_unknown={self.reject_unknown})")

    def validate_peer_signature(
        self,
        node_id: str,
        message: bytes,
        signature: bytes,
        public_key_bytes: Optional[bytes] = None,
    ) -> bool:
        """
        Validate a peer's signature
        
        Args:
            node_id: Node ID claiming to have signed
            message: Original message
            signature: Signature bytes
            public_key_bytes: Public key bytes (if not in trust records)
            
        Returns:
            True if signature is valid
        """
        # Try to get public key from trust records
        trust_record = self.trust_manager.get_trust_record(node_id)
        if trust_record and trust_record.public_key:
            try:
                public_key_hex = trust_record.public_key
                public_key_bytes_from_record = bytes.fromhex(public_key_hex)
                if MessageSigner.verify_with_public_key_bytes(
                    message, signature, public_key_bytes_from_record
                ):
                    # Record successful verification
                    self.trust_manager.record_verification(node_id, trust_record.public_key, self.audit_logger)
                    logger.debug(f"Verified signature for {node_id[:16]}... (from trust record)")
                    return True
            except Exception as e:
                logger.warning(f"Failed to verify signature with trust record: {e}")

        # Try with provided public key
        if public_key_bytes:
            try:
                if MessageSigner.verify_with_public_key_bytes(message, signature, public_key_bytes):
                    # Record successful verification
                    public_key_hex = public_key_bytes.hex()
                    self.trust_manager.record_verification(node_id, public_key_hex, self.audit_logger)
                    logger.debug(f"Verified signature for {node_id[:16]}... (from provided key)")
                    return True
            except Exception as e:
                logger.warning(f"Failed to verify signature with provided key: {e}")

        logger.warning(f"Failed to verify signature for {node_id[:16]}...")
        return False

    def can_connect(self, node_id: str) -> bool:
        """
        Check if a peer can connect based on trust level
        
        Args:
            node_id: Node ID
            
        Returns:
            True if peer can connect
        """
        trust_level = self.trust_manager.get_trust_level(node_id)
        
        # Reject untrusted peers
        if trust_level == TrustLevel.UNTRUSTED:
            logger.warning(f"Rejecting connection from untrusted peer: {node_id[:16]}...")
            return False
        
        # Reject unknown peers if configured
        if self.reject_unknown and trust_level == TrustLevel.UNKNOWN:
            logger.warning(f"Rejecting connection from unknown peer: {node_id[:16]}... (reject_unknown enabled)")
            return False
        
        # Allow trusted, verified, and bootstrap peers
        if trust_level in (TrustLevel.TRUSTED, TrustLevel.VERIFIED, TrustLevel.BOOTSTRAP):
            return True
        
        # Unknown peers: check reject_unknown config
        if trust_level == TrustLevel.UNKNOWN:
            if self.reject_unknown:
                logger.warning(f"Rejecting connection from unknown peer: {node_id[:16]}... (reject_unknown enabled)")
                return False
            logger.info(f"Allowing connection from unknown peer (will require verification): {node_id[:16]}...")
            return True
        
        return False

    def should_verify_signature(self, node_id: str) -> bool:
        """
        Check if signature verification is required for a peer
        
        Args:
            node_id: Node ID
            
        Returns:
            True if signature should be verified
        """
        trust_level = self.trust_manager.get_trust_level(node_id)
        
        # Always verify unknown peers
        if trust_level == TrustLevel.UNKNOWN:
            return True
        
        # Verify verified peers periodically
        if trust_level == TrustLevel.VERIFIED:
            return True
        
        # Trusted and bootstrap peers: optional verification
        if trust_level in (TrustLevel.TRUSTED, TrustLevel.BOOTSTRAP):
            return False
        
        # Untrusted: don't verify (will be rejected anyway)
        return False
