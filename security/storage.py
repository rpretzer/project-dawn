"""
Secure Storage

Provides encryption at rest for sensitive data files.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from crypto.encryption import MessageEncryptor
from data_paths import data_root

logger = logging.getLogger(__name__)


class SecureStorage:
    """
    Secure storage with encryption at rest
    
    Encrypts sensitive data before writing to disk.
    """

    def __init__(self, storage_key: Optional[bytes] = None, data_dir: Optional[Path] = None):
        """
        Initialize secure storage
        
        Args:
            storage_key: Encryption key (32 bytes). If None, derives from master key.
            data_dir: Data directory (defaults to data_root/vault)
        """
        self.data_dir = data_dir or data_root() / "vault"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Derive storage key from master key if not provided
        if storage_key is None:
            storage_key = self._derive_storage_key()
        
        self.encryptor = MessageEncryptor(storage_key)
        logger.debug("SecureStorage initialized")

    def _derive_storage_key(self) -> bytes:
        """
        Derive storage key from master key file
        
        Returns:
            32-byte encryption key
        """
        
        # Try to get master key from environment or file
        master_key_path = self.data_dir / "master_key"
        
        if master_key_path.exists():
            # Use existing master key
            master_key = master_key_path.read_bytes()
        else:
            # Generate new master key
            master_key = os.urandom(32)
            tmp_path = master_key_path.with_suffix(".tmp")
            tmp_path.write_bytes(master_key)
            tmp_path.replace(master_key_path)
            # Set restrictive permissions (Unix only)
            try:
                os.chmod(master_key_path, 0o600)
            except Exception:
                pass
            logger.info("Generated new master key for storage encryption")
        
        # Derive storage key using HKDF
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.backends import default_backend
        
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'project-dawn-storage-v1',
            info=b'storage-encryption-key',
            backend=default_backend()
        )
        storage_key = hkdf.derive(master_key)
        return storage_key

    def save_encrypted(self, filename: str, data: Dict[str, Any]) -> None:
        """
        Save encrypted data to file
        
        Args:
            filename: Filename (relative to data_dir)
            data: Data dictionary to encrypt and save
        """
        file_path = self.data_dir / filename
        
        try:
            # Serialize data
            json_data = json.dumps(data, sort_keys=True, indent=2)
            plaintext = json_data.encode('utf-8')
            
            # Encrypt
            nonce, ciphertext = self.encryptor.encrypt(plaintext)
            
            # Create encrypted envelope
            envelope = {
                "nonce": nonce.hex(),
                "ciphertext": ciphertext.hex(),
                "format": "aes-256-gcm",
            }
            
            # Write to temporary file first (atomic write)
            tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(envelope, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            
            # Atomic replace
            os.replace(tmp_path, file_path)
            
            # Set restrictive permissions (Unix only)
            try:
                os.chmod(file_path, 0o600)
            except Exception:
                pass
            
            logger.debug(f"Saved encrypted data to {filename}")
        
        except Exception as e:
            logger.error(f"Failed to save encrypted data to {filename}: {e}", exc_info=True)
            raise

    def load_encrypted(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Load and decrypt data from file
        
        Args:
            filename: Filename (relative to data_dir)
            
        Returns:
            Decrypted data dictionary or None if error
        """
        file_path = self.data_dir / filename
        
        if not file_path.exists():
            return None
        
        try:
            # Read encrypted envelope
            envelope = json.loads(file_path.read_text(encoding="utf-8"))
            
            # Decrypt
            nonce = bytes.fromhex(envelope["nonce"])
            ciphertext = bytes.fromhex(envelope["ciphertext"])
            plaintext = self.encryptor.decrypt(nonce, ciphertext)
            
            # Deserialize
            data = json.loads(plaintext.decode('utf-8'))
            logger.debug(f"Loaded encrypted data from {filename}")
            return data
        
        except Exception as e:
            logger.warning(f"Failed to load encrypted data from {filename}: {e}")
            return None

    def file_exists(self, filename: str) -> bool:
        """Check if encrypted file exists"""
        file_path = self.data_dir / filename
        return file_path.exists()
