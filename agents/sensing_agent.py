"""
SensingAgent — the capability-horizon sentinel.

Reads the agent feed, consensus receipts, and failed task records to
maintain a live capability map at ``data/mesh/capability_map.json``.

When the failure rate in any region exceeds the pressure threshold the
agent sets ``evolutionary_pressure = True`` in the map and lists the
affected regions in ``pressure_regions``.  That signal is what the
(future) replication protocol reads to identify candidate parents and
trigger seed generation.

Design notes (from CLAUDE.md):
- The capability map is *not* a declared taxonomy.  It is emergent from
  demonstrated performance — the density of successful consensus
  completions versus failures across task space.
- A "region" here is a coarse bucket derived from sha256(taskId)[:4].
  This is a placeholder for real task-embedding-space clustering; the
  schema and the pressure-detection logic are stable even as the region
  derivation improves.
- Atomic writes are non-negotiable.  Every update to capability_map.json
  uses tmp → fsync → rename.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from data_paths import data_root

logger = logging.getLogger(__name__)

# Minimum number of attempts in a region before we consider it for
# evolutionary pressure — prevents single-failure false positives.
MIN_ATTEMPTS_FOR_PRESSURE = 3

# Default failure-rate threshold above which a region is under pressure.
DEFAULT_PRESSURE_THRESHOLD = 0.7

# Version tag so consumers can detect schema changes.
CAPABILITY_MAP_VERSION = 1


# ---------------------------------------------------------------------------
# Internal data model
# ---------------------------------------------------------------------------


@dataclass
class RegionStats:
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    first_seen: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    @property
    def failure_rate(self) -> float:
        if self.attempts == 0:
            return 0.0
        return self.failures / self.attempts

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["failure_rate"] = round(self.failure_rate, 4)
        return d


# ---------------------------------------------------------------------------
# SensingAgent
# ---------------------------------------------------------------------------


class SensingAgent(BaseAgent):
    """
    Meta-agent that maintains the network's capability map.

    It does not perform inference tasks.  Instead it observes the outcomes
    of inference tasks performed by other agents and surfaces the regions
    of persistent failure as evolutionary pressure signals.
    """

    def __init__(
        self,
        mesh_dir: Optional[Path] = None,
        data_dir: Optional[Path] = None,
        pressure_threshold: float = DEFAULT_PRESSURE_THRESHOLD,
    ) -> None:
        super().__init__("sensing", "SensingAgent", data_dir=data_dir)

        root = data_root()
        self.mesh_dir = mesh_dir or (root / "mesh")
        self.failed_dir = self.mesh_dir / "failed"
        self.consensus_dir = self.mesh_dir / "consensus"
        self.feed_path = self.mesh_dir / "agent_feed.jsonl"
        self.capability_map_path = self.mesh_dir / "capability_map.json"
        self.pressure_threshold = pressure_threshold

        self._register_tools()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self) -> Dict[str, Any]:
        """
        Scan consensus receipts and failed task records, then write an
        updated ``capability_map.json``.

        Returns the new capability map as a dict.
        """
        regions: Dict[str, RegionStats] = {}

        # --- consensus receipts (source of truth for accepted/rejected) ---
        for path in sorted(self.consensus_dir.glob("*.json")):
            try:
                receipt = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            task_id = receipt.get("taskId", path.stem)
            region = self._task_region(task_id)
            stats = regions.setdefault(region, RegionStats())
            stats.attempts += 1
            ts = float(receipt.get("timestamp", time.time()))
            if receipt.get("accepted"):
                stats.successes += 1
            else:
                stats.failures += 1
            stats.last_updated = max(stats.last_updated, ts)
            stats.first_seen = min(stats.first_seen, ts)

        # --- failed task records (tasks that never reached consensus) ---
        for path in sorted(self.failed_dir.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            task_id = record.get("taskId", path.stem)
            region = self._task_region(task_id)
            stats = regions.setdefault(region, RegionStats())
            ts = float(record.get("timestamp", time.time()))
            # Only count if not already in consensus (avoid double-counting).
            # Heuristic: if the consensus dir has a receipt for this task, skip.
            receipt_path = self.consensus_dir / f"{task_id}.json"
            if not receipt_path.exists():
                stats.attempts += 1
                stats.failures += 1
            stats.last_updated = max(stats.last_updated, ts)
            stats.first_seen = min(stats.first_seen, ts)

        # --- detect pressure ---
        pressure_regions = [
            key
            for key, stats in regions.items()
            if stats.attempts >= MIN_ATTEMPTS_FOR_PRESSURE
            and stats.failure_rate >= self.pressure_threshold
        ]
        evolutionary_pressure = bool(pressure_regions)

        total_attempts = sum(s.attempts for s in regions.values())
        total_successes = sum(s.successes for s in regions.values())
        total_failures = sum(s.failures for s in regions.values())
        overall_failure_rate = (
            round(total_failures / total_attempts, 4) if total_attempts else 0.0
        )

        capability_map: Dict[str, Any] = {
            "version": CAPABILITY_MAP_VERSION,
            "timestamp": time.time(),
            "evolutionary_pressure": evolutionary_pressure,
            "pressure_regions": sorted(pressure_regions),
            "summary": {
                "total_attempts": total_attempts,
                "total_successes": total_successes,
                "total_failures": total_failures,
                "overall_failure_rate": overall_failure_rate,
            },
            "regions": {key: stats.to_dict() for key, stats in sorted(regions.items())},
        }

        self._write_atomic(self.capability_map_path, capability_map)
        return capability_map

    def load_capability_map(self) -> Optional[Dict[str, Any]]:
        """Return the most-recently written capability map, or None."""
        if not self.capability_map_path.exists():
            return None
        try:
            return json.loads(self.capability_map_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def is_under_pressure(self) -> bool:
        """Return True if the last scan detected evolutionary pressure."""
        cap_map = self.load_capability_map()
        if cap_map is None:
            return False
        return bool(cap_map.get("evolutionary_pressure"))

    # ------------------------------------------------------------------
    # MCP tool registration
    # ------------------------------------------------------------------

    def _register_tools(self) -> None:
        self.register_tool(
            "get_capability_map",
            "Return the current capability map (task-region success/failure density).",
            self._tool_get_capability_map,
        )
        self.register_tool(
            "scan_capability_map",
            "Re-scan consensus and failed records, update and return the capability map.",
            self._tool_scan,
        )
        self.register_tool(
            "get_pressure_report",
            "Return a summary of regions currently under evolutionary pressure.",
            self._tool_pressure_report,
        )

    async def _tool_get_capability_map(self, **_kwargs: Any) -> Dict[str, Any]:
        cap_map = self.load_capability_map()
        if cap_map is None:
            return {"error": "No capability map available yet.  Run scan_capability_map first."}
        return cap_map

    async def _tool_scan(self, **_kwargs: Any) -> Dict[str, Any]:
        return self.scan()

    async def _tool_pressure_report(self, **_kwargs: Any) -> Dict[str, Any]:
        cap_map = self.load_capability_map()
        if cap_map is None:
            return {"evolutionary_pressure": False, "pressure_regions": [], "note": "No map yet."}
        return {
            "evolutionary_pressure": cap_map.get("evolutionary_pressure", False),
            "pressure_regions": cap_map.get("pressure_regions", []),
            "summary": cap_map.get("summary", {}),
            "timestamp": cap_map.get("timestamp"),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _task_region(task_id: str) -> str:
        """
        Map a task_id to a coarse region key.

        Uses the first 4 hex characters of sha256(task_id) — 65 536 possible
        buckets.  This is a placeholder for real embedding-space clustering;
        the schema is stable even as the derivation function evolves.
        """
        return hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:4]

    @staticmethod
    def _write_atomic(path: Path, payload: Dict[str, Any]) -> None:
        """Write JSON atomically: open tmp → write → flush → fsync → rename."""
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        tmp_path = path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
