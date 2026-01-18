#!/usr/bin/env python3
"""
Sign release files with PGP/GPG

Usage:
    python sign_release.py <file_to_sign> [key_id]
"""

import subprocess
import sys
from pathlib import Path


def sign_file(file_path: Path, key_id: Optional[str] = None) -> Path:
    """Sign a file with GPG"""
    signature_file = file_path.with_suffix(file_path.suffix + ".sig")
    cmd = ["gpg", "--detach-sign", "--armor"]
    if key_id:
        cmd.extend(["--local-user", key_id])
    cmd.append(str(file_path))
    
    print(f"Signing {file_path.name}...")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Signed {file_path.name} with GPG")
        print(f"Signature saved to: {signature_file}")
        return signature_file
    except subprocess.CalledProcessError as e:
        print(f"Error signing file: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: gpg command not found. Is GnuPG installed?", file=sys.stderr)
        sys.exit(1)


def verify_signature(file_path: Path, signature_file: Path) -> bool:
    """Verify a GPG signature"""
    cmd = ["gpg", "--verify", str(signature_file), str(file_path)]
    print(f"Verifying signature for {file_path.name}...")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
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
    print("\nTo verify the signature:")
    print(f"  gpg --verify {signature_file} {file_path}")
