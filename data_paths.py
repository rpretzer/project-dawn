"""
Shared data path helpers.
"""

from __future__ import annotations

import os
from pathlib import Path


DATA_ROOT_ENV = "PROJECT_DAWN_DATA_ROOT"


def data_root() -> Path:
    """
    Resolve the sovereign data root directory.
    """
    override = os.environ.get(DATA_ROOT_ENV)
    if override:
        return Path(override).expanduser()
    return Path("data")
