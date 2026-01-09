#!/usr/bin/env python3
"""
Verify release integrity using checksums and PGP signatures

This script can be embedded in the application for runtime verification.
"""

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


class IntegrityVerifier:
    """Verify file integrity using checksums and PGP signatures"""
    
    def __init__(self, public_key_path: Optional[Path] = None):
        """
        Initialize verifier
        
        Args:
            public_key_path: Path to hardcoded public key for verification
        """
        self.public_key_path = public_key_path
    
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
        
        # Import public key if provided
        if self.public_key_path and self.public_key_path.exists():
            try:
                subprocess.run(
                    ["gpg", "--import", str(self.public_key_path)],
                    check=False,
                    capture_output=True
                )
            except FileNotFoundError:
                return False, "GPG not found. Cannot verify signature."
        
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


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: python verify_integrity.py <release_directory> [public_key.asc]")
        sys.exit(1)
    
    release_dir = Path(sys.argv[1])
    if not release_dir.exists():
        print(f"Error: {release_dir} does not exist")
        sys.exit(1)
    
    public_key = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    
    verifier = IntegrityVerifier(public_key_path=public_key)
    all_valid, messages = verifier.verify_release(release_dir)
    
    print("\n".join(messages))
    
    if all_valid:
        print("\n✓ All integrity checks passed!")
        sys.exit(0)
    else:
        print("\n✗ Integrity verification failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
