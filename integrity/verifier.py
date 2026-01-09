"""
Application Integrity Verifier

Provides runtime verification of application integrity using checksums and PGP signatures.
"""

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


class IntegrityVerifier:
    """Verify file integrity using checksums and PGP signatures"""
    
    def __init__(self, public_key_path: Optional[Path] = None, public_key_content: Optional[str] = None):
        """
        Initialize verifier
        
        Args:
            public_key_path: Path to public key file
            public_key_content: Public key content as string (for embedding)
        """
        self.public_key_path = public_key_path
        self.public_key_content = public_key_content
    
    def _import_public_key(self) -> bool:
        """Import public key for verification"""
        if self.public_key_content:
            # Write to temp file and import
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.asc', delete=False) as f:
                f.write(self.public_key_content)
                temp_key_path = Path(f.name)
            
            try:
                result = subprocess.run(
                    ["gpg", "--import", str(temp_key_path)],
                    check=False,
                    capture_output=True
                )
                temp_key_path.unlink()  # Clean up
                return result.returncode == 0
            except FileNotFoundError:
                return False
        elif self.public_key_path and self.public_key_path.exists():
            try:
                result = subprocess.run(
                    ["gpg", "--import", str(self.public_key_path)],
                    check=False,
                    capture_output=True
                )
                return result.returncode == 0
            except FileNotFoundError:
                return False
        return False
    
    def calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def verify_checksum(self, file_path: Path, checksum_file: Path) -> Tuple[bool, str]:
        """
        Verify file against checksum file
        
        Returns:
            (is_valid, message)
        """
        if not file_path.exists():
            return False, f"File not found: {file_path}"
        
        if not checksum_file.exists():
            return False, f"Checksum file not found: {checksum_file}"
        
        # Calculate file checksum
        file_checksum = self.calculate_sha256(file_path)
        
        # Read checksum file
        with open(checksum_file, "r") as f:
            checksum_lines = f.readlines()
        
        # Find matching checksum
        file_name = file_path.name
        for line in checksum_lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                expected_checksum = parts[0]
                checksum_file_name = parts[1]
                
                # Match by filename
                if checksum_file_name == file_name or checksum_file_name.endswith(file_name):
                    if file_checksum == expected_checksum:
                        return True, f"Checksum verified for {file_name}"
                    else:
                        return False, f"Checksum mismatch for {file_name}"
        
        return False, f"No checksum found for {file_name} in checksum file"
    
    def verify_gpg_signature(self, file_path: Path, signature_file: Path) -> Tuple[bool, str]:
        """
        Verify GPG signature
        
        Returns:
            (is_valid, message)
        """
        if not file_path.exists():
            return False, f"File not found: {file_path}"
        
        if not signature_file.exists():
            return False, f"Signature file not found: {signature_file}"
        
        # Import public key if available
        if self.public_key_path or self.public_key_content:
            self._import_public_key()
        
        # Verify signature
        try:
            result = subprocess.run(
                ["gpg", "--verify", str(signature_file), str(file_path)],
                check=True,
                capture_output=True,
                text=True
            )
            return True, f"GPG signature verified for {file_path.name}"
        except subprocess.CalledProcessError as e:
            return False, f"GPG signature verification failed: {e.stderr}"
        except FileNotFoundError:
            return False, "GPG not found. Cannot verify signature."
    
    def verify_release(self, release_dir: Path, checksum_file: str = "CHECKSUM.txt", 
                      signature_file: str = "CHECKSUM.txt.sig") -> Tuple[bool, list]:
        """
        Verify entire release directory
        
        Returns:
            (all_valid, list_of_messages)
        """
        messages = []
        all_valid = True
        
        checksum_path = release_dir / checksum_file
        signature_path = release_dir / signature_file
        
        # Verify checksum file signature first
        if signature_path.exists():
            is_valid, msg = self.verify_gpg_signature(checksum_path, signature_path)
            messages.append(msg)
            if not is_valid:
                all_valid = False
                return all_valid, messages
        else:
            messages.append("Warning: No signature file found")
        
        # Verify individual files
        if checksum_path.exists():
            with open(checksum_path, "r") as f:
                checksum_lines = f.readlines()
            
            for line in checksum_lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    file_name = parts[1]
                    file_path = release_dir / file_name
                    
                    if file_path.exists():
                        is_valid, msg = self.verify_checksum(file_path, checksum_path)
                        messages.append(msg)
                        if not is_valid:
                            all_valid = False
        else:
            messages.append("Error: Checksum file not found")
            all_valid = False
        
        return all_valid, messages


def verify_application_integrity(
    app_dir: Optional[Path] = None,
    public_key_content: Optional[str] = None,
    public_key_path: Optional[Path] = None,
    fail_on_error: bool = True
) -> Tuple[bool, list]:
    """
    Verify application integrity on startup
    
    Args:
        app_dir: Application directory (defaults to script directory)
        public_key_content: Hardcoded public key content
        public_key_path: Path to public key file
        fail_on_error: If True, exit on verification failure
        
    Returns:
        (is_valid, list_of_messages)
    """
    if app_dir is None:
        # Default to script directory
        app_dir = Path(__file__).parent.parent
    
    verifier = IntegrityVerifier(
        public_key_path=public_key_path,
        public_key_content=public_key_content
    )
    
    is_valid, messages = verifier.verify_release(app_dir)
    
    if not is_valid and fail_on_error:
        print("=" * 60)
        print("INTEGRITY VERIFICATION FAILED")
        print("=" * 60)
        for msg in messages:
            print(f"  {msg}")
        print("=" * 60)
        print("Application will not start due to integrity check failure.")
        print("This may indicate the application has been tampered with.")
        sys.exit(1)
    
    return is_valid, messages


# Example: Hardcoded public key (to be replaced with actual key)
# This should be embedded in the application for runtime verification
DEFAULT_PUBLIC_KEY = """
-----BEGIN PGP PUBLIC KEY BLOCK-----
(Replace with actual public key)
-----END PGP PUBLIC KEY BLOCK-----
"""
