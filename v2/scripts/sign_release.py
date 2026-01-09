#!/usr/bin/env python3
"""
Sign release files with PGP/GPG

Usage:
    python sign_release.py <file_to_sign> [key_id]
"""

import subprocess
import sys
from pathlib import Path


def sign_file(file_path: Path, key_id: str = None) -> Path:
    """Sign a file with GPG and return signature file path"""
    signature_file = Path(f"{file_path}.sig")
    
    cmd = ["gpg", "--detach-sign", "--armor"]
    
    if key_id:
        cmd.extend(["--default-key", key_id])
    
    cmd.append(str(file_path))
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Signed {file_path.name} with GPG")
        print(f"Signature saved to: {signature_file}")
        return signature_file
    except subprocess.CalledProcessError as e:
        print(f"Error signing file: {e}")
        print(f"GPG output: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: GPG not found. Please install GPG (GnuPG)")
        print("  - macOS: brew install gnupg")
        print("  - Linux: apt-get install gnupg (or equivalent)")
        print("  - Windows: Download from https://www.gpg4win.org/")
        sys.exit(1)


def verify_signature(file_path: Path, signature_file: Path, public_key: Path = None) -> bool:
    """Verify a GPG signature"""
    cmd = ["gpg", "--verify", str(signature_file), str(file_path)]
    
    if public_key:
        # Import public key first
        import_cmd = ["gpg", "--import", str(public_key)]
        subprocess.run(import_cmd, check=False)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✓ Signature verified for {file_path.name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Signature verification failed: {e.stderr}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sign_release.py <file_to_sign> [key_id]")
        print("\nExample:")
        print("  python sign_release.py CHECKSUM.txt")
        print("  python sign_release.py CHECKSUM.txt YOUR_KEY_ID")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"Error: {file_path} does not exist")
        sys.exit(1)
    
    key_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    signature_file = sign_file(file_path, key_id)
    print(f"\nTo verify the signature:")
    print(f"  gpg --verify {signature_file} {file_path}")
