#!/usr/bin/env python3
"""
Backup CLI Command

Backs up Project Dawn data directory to a backup location.
"""

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from data_paths import data_root

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def backup_data(
    source_dir: Path,
    backup_dir: Path,
    backup_name: Optional[str] = None,
    exclude_patterns: Optional[list] = None,
) -> Path:
    """
    Backup data directory to backup location
    
    Args:
        source_dir: Source data directory
        backup_dir: Backup directory
        backup_name: Backup name (defaults to timestamp)
        exclude_patterns: Patterns to exclude (e.g., ["*.log", "*.tmp"])
        
    Returns:
        Path to backup directory
    """
    if not source_dir.exists():
        raise ValueError(f"Source directory does not exist: {source_dir}")
    
    # Create backup name
    if backup_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"dawn_backup_{timestamp}"
    
    backup_path = backup_dir / backup_name
    backup_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Backing up {source_dir} to {backup_path}")
    
    # Create metadata
    metadata = {
        "backup_name": backup_name,
        "timestamp": datetime.now().isoformat(),
        "source_dir": str(source_dir),
        "backup_dir": str(backup_path),
    }
    
    # Copy data directory
    try:
        shutil.copytree(
            source_dir,
            backup_path,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*(exclude_patterns or [])),
        )
        logger.info(f"Copied {source_dir} to {backup_path}")
    except Exception as e:
        logger.error(f"Failed to copy data directory: {e}")
        raise
    
    # Save metadata
    metadata_path = backup_path / ".backup_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    logger.info(f"Saved backup metadata to {metadata_path}")
    
    logger.info(f"Backup completed: {backup_path}")
    return backup_path


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Backup Project Dawn data directory")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Source data directory (default: data_root())",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Backup directory (default: source_dir/../backups)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Backup name (default: dawn_backup_TIMESTAMP)",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="*",
        default=["*.log", "*.tmp", "__pycache__", "*.pyc"],
        help="Patterns to exclude (default: *.log, *.tmp, __pycache__, *.pyc)",
    )
    
    args = parser.parse_args()
    
    # Determine source directory
    source_dir = args.source or data_root()
    
    # Determine backup directory
    if args.backup_dir:
        backup_dir = args.backup_dir
    else:
        backup_dir = source_dir.parent / "backups"
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        backup_path = backup_data(
            source_dir=source_dir,
            backup_dir=backup_dir,
            backup_name=args.name,
            exclude_patterns=args.exclude,
        )
        print(f"Backup completed: {backup_path}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
