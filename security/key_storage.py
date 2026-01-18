"""
Secure Key Storage

Provides secure storage for private keys with optional passphrase protection.
"""

import base64
import logging
import os
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from data_paths import data_root

logger = logging.getLogger(__name__)


class SecureKeyStorage:
    """
    Secure key storage with optional passphrase protection
    
    Encrypts private keys before storing on disk.
    """

    def __init__(self, vault_dir: Optional[Path] = None):
        """
        Initialize secure key storage
        
        Args:
            vault_dir: Vault directory (defaults to data_root/vault)
        """
        self.vault_dir = vault_dir or data_root() / "vault"
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("SecureKeyStorage initialized")

    def _derive_key_from_passphrase(self, passphrase: str, salt: bytes) -> bytes:
        """
        Derive encryption key from passphrase using PBKDF2
        
        Args:
            passphrase: Passphrase string
            salt: Salt bytes
            
        Returns:
            32-byte encryption key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,  # PBKDF2 iterations
            backend=default_backend()
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def save_key(
        self,
        key_name: str,
        private_key: bytes,
        passphrase: Optional[str] = None,
    ) -> Path:
        """
        Save private key with optional passphrase protection
        
        Args:
            key_name: Key name (e.g., "node_identity")
            private_key: Private key bytes
            passphrase: Optional passphrase for encryption
            
        Returns:
            Path to saved key file
        """
        key_path = self.vault_dir / f"{key_name}.key"
        salt_path = self.vault_dir / f"{key_name}.salt"
        
        try:
            if passphrase:
                # Encrypt with passphrase
                salt = os.urandom(16)
                key = self._derive_key_from_passphrase(passphrase, salt)
                
                aesgcm = AESGCM(key)
                nonce = os.urandom(12)
                ciphertext = aesgcm.encrypt(nonce, private_key, None)
                
                # Save encrypted key
                key_data = {
                    "nonce": base64.b64encode(nonce).decode('ascii'),
                    "ciphertext": base64.b64encode(ciphertext).decode('ascii'),
                    "format": "aes-256-gcm-pbkdf2",
                }
                
                # Save salt separately
                tmp_salt = salt_path.with_suffix(".salt.tmp")
                tmp_salt.write_bytes(salt)
                tmp_salt.replace(salt_path)
                
                logger.debug(f"Saved key {key_name} with passphrase protection")
            else:
                # Store unencrypted (fallback - less secure)
                key_data = {
                    "key": base64.b64encode(private_key).decode('ascii'),
                    "format": "base64",
                }
                logger.warning(f"Saved key {key_name} without passphrase protection (not recommended)")
            
            # Atomic write
            tmp_path = key_path.with_suffix(".key.tmp")
            import json
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(key_data, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, key_path)
            
            # Set restrictive permissions
            try:
                os.chmod(key_path, 0o600)
                if salt_path.exists():
                    os.chmod(salt_path, 0o600)
            except Exception:
                pass
            
            logger.info(f"Saved key {key_name} to {key_path}")
            return key_path
        
        except Exception as e:
            logger.error(f"Failed to save key {key_name}: {e}", exc_info=True)
            raise

    def load_key(self, key_name: str, passphrase: Optional[str] = None) -> Optional[bytes]:
        """
        Load private key with optional passphrase
        
        Args:
            key_name: Key name (e.g., "node_identity")
            passphrase: Passphrase if key is encrypted
            
        Returns:
            Private key bytes or None if error
        """
        key_path = self.vault_dir / f"{key_name}.key"
        salt_path = self.vault_dir / f"{key_name}.salt"
        
        if not key_path.exists():
            return None
        
        try:
            import json
            key_data = json.loads(key_path.read_text(encoding="utf-8"))
            
            if key_data.get("format") == "aes-256-gcm-pbkdf2":
                # Decrypt with passphrase
                if not passphrase:
                    logger.error(f"Key {key_name} is encrypted but no passphrase provided")
                    return None
                
                if not salt_path.exists():
                    logger.error(f"Salt file missing for key {key_name}")
                    return None
                
                salt = salt_path.read_bytes()
                key = self._derive_key_from_passphrase(passphrase, salt)
                
                nonce = base64.b64decode(key_data["nonce"])
                ciphertext = base64.b64decode(key_data["ciphertext"])
                
                aesgcm = AESGCM(key)
                private_key = aesgcm.decrypt(nonce, ciphertext, None)
                
                logger.debug(f"Loaded encrypted key {key_name}")
                return private_key
            
            elif key_data.get("format") == "base64":
                # Unencrypted (legacy)
                private_key = base64.b64decode(key_data["key"])
                logger.debug(f"Loaded unencrypted key {key_name}")
                return private_key
            
            else:
                logger.error(f"Unknown key format for {key_name}")
                return None
        
        except Exception as e:
            logger.error(f"Failed to load key {key_name}: {e}", exc_info=True)
            return None
