#!/usr/bin/env python3
"""
Generate SHA-256 checksum for release files

Usage:
    python generate_checksum.py <file_or_directory> [output_file]
"""

import hashlib
import sys
import os
from pathlib import Path


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def generate_checksum(target: Path, output_file: Path = None) -> None:
    """Generate checksum file for target file or directory"""
    checksums = []
    
    if target.is_file():
        # Single file
        checksum = calculate_sha256(target)
        checksums.append(f"{checksum}  {target.name}")
        print(f"Generated checksum for {target.name}")
    elif target.is_dir():
        # Directory - checksum all files
        for file_path in sorted(target.rglob("*")):
            if file_path.is_file():
                checksum = calculate_sha256(file_path)
                relative_path = file_path.relative_to(target)
                checksums.append(f"{checksum}  {relative_path}")
                print(f"Generated checksum for {relative_path}")
    else:
        print(f"Error: {target} is not a file or directory")
        sys.exit(1)
    
    # Write checksum file
    if output_file is None:
        output_file = target.parent / "CHECKSUM.txt"
    
    with open(output_file, "w") as f:
        f.write("\n".join(checksums))
        f.write("\n")
    
    print(f"\nChecksum file written to: {output_file}")
    print(f"Total files: {len(checksums)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_checksum.py <file_or_directory> [output_file]")
        sys.exit(1)
    
    target = Path(sys.argv[1])
    if not target.exists():
        print(f"Error: {target} does not exist")
        sys.exit(1)
    
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    generate_checksum(target, output_file)
