"""
Data storage module for Project Dawn
Manages consciousness data persistence
"""

from pathlib import Path

# Base data directory
DATA_DIR = Path(__file__).parent

def get_consciousness_data_path(consciousness_id: str) -> Path:
    """Get the data directory path for a specific consciousness"""
    path = DATA_DIR / f"consciousness_{consciousness_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path

def list_consciousness_data_dirs() -> list:
    """List all consciousness data directories"""
    dirs = []
    for item in DATA_DIR.iterdir():
        if item.is_dir() and item.name.startswith('consciousness_'):
            dirs.append(item.name)
    return dirs

__all__ = [
    'DATA_DIR',
    'get_consciousness_data_path',
    'list_consciousness_data_dirs'
]