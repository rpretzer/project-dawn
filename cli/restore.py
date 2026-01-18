#!/usr/bin/env python3
"""
Restore CLI Command

Restores Project Dawn data directory from a backup.
"""

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def restore_data(
    backup_path: Path,
    target_dir: Path,
    overwrite: bool = False,
) -> None:
    """
    Restore data directory from backup
    
    Args:
        backup_path: Path to backup directory
        target_dir: Target data directory
        overwrite: Overwrite existing data (default: False)
    """
    if not backup_path.exists():
        raise ValueError(f"Backup directory does not exist: {backup_path}")
    
    # Check if target exists
    if target_dir.exists() and not overwrite:
        raise ValueError(
            f"Target directory exists: {target_dir}. Use --overwrite to overwrite."
        )
    
    # Load metadata
    metadata_path = backup_path / ".backup_metadata.json"
    metadata = None
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            logger.info(f"Restoring from backup: {metadata.get('backup_name', 'unknown')}")
            logger.info(f"Backup timestamp: {metadata.get('timestamp', 'unknown')}")
        except Exception as e:
            logger.warning(f"Failed to load backup metadata: {e}")
    
    # Backup existing target if it exists
    if target_dir.exists():
        backup_existing = target_dir.parent / f"{target_dir.name}.backup"
        logger.info(f"Backing up existing data to {backup_existing}")
        if backup_existing.exists():
            shutil.rmtree(backup_existing)
        shutil.move(str(target_dir), str(backup_existing))
    
    # Restore from backup
    logger.info(f"Restoring {backup_path} to {target_dir}")
    try:
        shutil.copytree(backup_path, target_dir)
        logger.info(f"Restored {backup_path} to {target_dir}")
    except Exception as e:
        logger.error(f"Failed to restore data directory: {e}")
        # Try to restore original if backup failed
        backup_existing = target_dir.parent / f"{target_dir.name}.backup"
        if backup_existing.exists():
            logger.info(f"Restoring original data from {backup_existing}")
            shutil.move(str(backup_existing), str(target_dir))
        raise
    
    # Remove metadata from restored directory
    metadata_path_restored = target_dir / ".backup_metadata.json"
    if metadata_path_restored.exists():
        metadata_path_restored.unlink()
    
    logger.info(f"Restore completed: {target_dir}")


def list_backups(backup_dir: Path) -> None:
    """
    List available backups
    
    Args:
        backup_dir: Backup directory
    """
    if not backup_dir.exists():
        logger.warning(f"Backup directory does not exist: {backup_dir}")
        return
    
    backups = []
    for item in backup_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            metadata_path = item / ".backup_metadata.json"
            metadata = None
            if metadata_path.exists():
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            
            backups.append({
                "name": item.name,
                "path": item,
                "metadata": metadata,
            })
    
    if not backups:
        logger.info("No backups found")
        return
    
    logger.info(f"Available backups in {backup_dir}:")
    for backup in sorted(backups, key=lambda x: x["metadata"]["timestamp"] if x["metadata"] else "", reverse=True):
        name = backup["name"]
        metadata = backup["metadata"]
        if metadata:
            timestamp = metadata.get("timestamp", "unknown")
            source_dir = metadata.get("source_dir", "unknown")
            print(f"  {name} (from {timestamp}, source: {source_dir})")
        else:
            print(f"  {name} (no metadata)")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Restore Project Dawn data directory from backup")
    parser.add_argument(
        "backup_name",
        type=str,
        nargs="?",
        default=None,
        help="Backup name to restore (or 'list' to list backups)",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Backup directory (default: data_dir/../backups)",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Target data directory (default: data_root())",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing data",
    )
    
    args = parser.parse_args()
    
    # Handle list command
    if args.backup_name == "list" or args.backup_name is None:
        from data_paths import data_root
        backup_dir = args.backup_dir or data_root().parent / "backups"
        list_backups(backup_dir)
        sys.exit(0)
    
    # Determine backup directory
    if args.backup_dir:
        backup_dir = args.backup_dir
    else:
        from data_paths import data_root
        backup_dir = data_root().parent / "backups"
    
    backup_path = backup_dir / args.backup_name
    
    # Determine target directory
    if args.target:
        target_dir = args.target
    else:
        from data_paths import data_root
        target_dir = data_root()
    
    try:
        restore_data(
            backup_path=backup_path,
            target_dir=target_dir,
            overwrite=args.overwrite,
        )
        print(f"Restore completed: {target_dir}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
