"""
InnovationAgent — frontier scout for the Project Dawn mesh.

The innovation agent is a taskless exploration agent.  Unlike the compute
nodes that wait for assigned work units, the InnovationAgent generates its
own *probes* — synthetic task-shaped inputs designed to explore regions of
task space that the capability map shows as blank (neither successes nor
failures yet, i.e. uncharted territory).

The data that probes generate:
- Expand the capability map before demand arrives.
- Ensure the network can respond to novel task types without a crisis-
  triggered evolutionary burst (the SensingAgent won't detect pressure
  in blank regions; the InnovationAgent turns blank space into signal).
- Represent the network's autonomous intellectual life.

**This is a skeleton implementation.**  The probe generation strategy
(embedding-space sampling, capability vocabulary expansion, cross-domain
novelty scoring) is left for Phase 2.  The skeleton establishes:

  - The agent structure (BaseAgent subclass with MCP tools).
  - The commons-balance gate (exploration is funded by surplus only).
  - The probe() / report() pattern used by the run loop.
  - The feed event schema for innovation activity.
  - The capability map integration (writing probe results to the map).

Phase 2 extensions should subclass InnovationAgent and override
_generate_probe_work_unit() to implement real probe synthesis.

On-disk layout (under data/):
  mesh/innovation/
    probes.jsonl   — append-only log of all probes attempted
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from data_paths import data_root

logger = logging.getLogger(__name__)

# Minimum commons balance (compute credits) before this agent activates.
# Exploration is funded by surplus — never at the cost of normal compute.
DEFAULT_COMMONS_FLOOR = 100

# Maximum probes per poll cycle so the agent doesn't monopolise the inbox.
MAX_PROBES_PER_CYCLE = 3

PROBE_LOG_VERSION = 1


# ---------------------------------------------------------------------------
# Probe record
# ---------------------------------------------------------------------------

@dataclass
class ProbeRecord:
    probeId: str
    region: str                  # coarse capability region (sha256[:4] of task type)
    workUnitTaskId: str          # taskId submitted to the inbox
    status: str                  # "pending" | "success" | "failure"
    issuedAt: float
    resolvedAt: Optional[float] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# InnovationAgent
# ---------------------------------------------------------------------------

class InnovationAgent(BaseAgent):
    """
    Taskless frontier scout.

    Instantiate in the orchestrator alongside SensingAgent:

        innovation_agent = InnovationAgent(
            mesh_dir=self.mesh_dir,
            commons_balance_fn=lambda: self._replication_agent.commons.balance,
        )

    Then call ``await innovation_agent.probe(inbox_dir)`` from the run loop
    when the commons balance exceeds the floor.
    """

    def __init__(
        self,
        mesh_dir: Optional[Path] = None,
        commons_balance_fn: Optional[Any] = None,
        commons_floor: int = DEFAULT_COMMONS_FLOOR,
        data_dir: Optional[Path] = None,
    ):
        super().__init__(
            agent_id="innovation_agent",
            name="InnovationAgent",
            data_dir=data_dir,
            persist_state=False,
        )
        root = data_dir or data_root()
        self.mesh_dir = mesh_dir or root / "mesh"
        self.capability_map_path = self.mesh_dir / "capability_map.json"
        self._innovation_dir = self.mesh_dir / "innovation"
        self._innovation_dir.mkdir(parents=True, exist_ok=True)
        self._probe_log_path = self._innovation_dir / "probes.jsonl"

        self._commons_balance_fn = commons_balance_fn  # callable → int
        self.commons_floor = commons_floor

        # Pending probes: taskId → ProbeRecord (resolved on report())
        self._pending: Dict[str, ProbeRecord] = {}

        self._register_tools()

    # ------------------------------------------------------------------
    # MCP tools
    # ------------------------------------------------------------------

    def _register_tools(self) -> None:
        self.register_tool(
            "innovation/status",
            "Return the InnovationAgent's current status and pending probe count.",
            self._tool_status,
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        )
        self.register_tool(
            "innovation/probe_history",
            "Return the last N probe records from the log.",
            self._tool_probe_history,
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                },
                "additionalProperties": False,
            },
        )

    async def _tool_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        balance = self._commons_balance() if self._commons_balance_fn else None
        return {
            "active": self._is_active(),
            "commons_balance": balance,
            "commons_floor": self.commons_floor,
            "pending_probes": len(self._pending),
        }

    async def _tool_probe_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(params.get("limit", 10))
        records = self._read_probe_log(limit)
        return {"probes": records}

    # ------------------------------------------------------------------
    # Core probe / report API
    # ------------------------------------------------------------------

    def probe(self, inbox_dir: Path) -> List[ProbeRecord]:
        """
        Generate and submit probes to the inbox.

        Called by the orchestrator run loop when the commons balance is
        above the floor.  Returns the list of ProbeRecords issued this cycle.

        This implementation generates simple token-sequence probes targeting
        blank regions of the capability map.  Phase 2 should override
        _generate_probe_work_unit() with real embedding-space sampling.
        """
        if not self._is_active():
            return []

        blank_regions = self._find_blank_regions()
        if not blank_regions:
            logger.debug("InnovationAgent: no blank regions to probe this cycle")
            return []

        issued: List[ProbeRecord] = []
        for region in blank_regions[:MAX_PROBES_PER_CYCLE]:
            work_unit = self._generate_probe_work_unit(region)
            task_id = work_unit["taskId"]
            probe_id = hashlib.sha256(f"{region}:{task_id}".encode()).hexdigest()[:16]

            record = ProbeRecord(
                probeId=probe_id,
                region=region,
                workUnitTaskId=task_id,
                status="pending",
                issuedAt=time.time(),
            )
            self._pending[task_id] = record
            self._write_probe_log(record)

            # Write work unit to inbox for the orchestrator's normal compute loop.
            inbox_path = inbox_dir / f"{task_id}.json"
            tmp_path = inbox_path.with_suffix(".json.tmp")
            data = json.dumps(work_unit, sort_keys=True, separators=(",", ":"))
            with open(tmp_path, "w", encoding="utf-8") as fh:
                fh.write(data)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, inbox_path)

            logger.info(
                "InnovationAgent: probe issued region=%s taskId=%s",
                region, task_id,
            )
            issued.append(record)

        return issued

    def report(self, task_id: str, success: bool, notes: str = "") -> Optional[ProbeRecord]:
        """
        Record the outcome of a probe task.

        Called by the orchestrator after consensus is reached for a task that
        was issued by this agent.  Updates the probe log and the capability map.
        """
        record = self._pending.pop(task_id, None)
        if not record:
            return None

        record.status = "success" if success else "failure"
        record.resolvedAt = time.time()
        record.notes = notes
        self._write_probe_log(record)
        self._update_capability_map(record)
        return record

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        """Return True if the commons balance is above the floor."""
        if self._commons_balance_fn is None:
            return True  # no balance gate configured — always active (e.g. in tests)
        return self._commons_balance() >= self.commons_floor

    def _commons_balance(self) -> int:
        try:
            return int(self._commons_balance_fn())
        except Exception:
            return 0

    def _find_blank_regions(self) -> List[str]:
        """
        Return regions of task space with no recorded attempts.

        In this skeleton, "regions" are 4-hex-char buckets derived from
        SHA-256 of a synthetic task type string.  The real implementation
        should derive regions from task-embedding space.

        A region is "blank" if it appears in neither the successes nor the
        failures of the capability map.
        """
        all_regions = [f"{i:04x}" for i in range(0, 256)]  # 256 coarse buckets
        cap_map = self._load_capability_map()
        observed = set(cap_map.get("regions", {}).keys()) if cap_map else set()
        blank = [r for r in all_regions if r not in observed]
        return blank

    def _generate_probe_work_unit(self, region: str) -> Dict[str, Any]:
        """
        Synthesise a work unit that probes the given capability region.

        Skeleton implementation: generates a deterministic token sequence
        seeded from the region string.  The sequence is short and artificial
        but exercises the full proof pipeline.

        Phase 2 override: sample a point in embedding space near the region
        centroid, generate a plausible natural-language prompt, and encode it
        as token IDs using the node's tokeniser.
        """
        seed = int(hashlib.sha256(f"probe:{region}:{time.time()}".encode()).hexdigest()[:8], 16)
        task_id = f"probe-{region}-{seed:08x}"
        # Minimal token sequences — 5 input tokens, 5 output tokens.
        input_tokens = [(seed + i) % 50256 for i in range(5)]
        output_tokens = [(seed + 5 + i) % 50256 for i in range(5)]
        return {
            "taskId": task_id,
            "taskType": "logit_proof",
            "source": "innovation_agent",
            "probeRegion": region,
            "expiresAt": time.time() + 3600,
            "inputBlob": {
                "inputTokens": input_tokens,
                "outputTokens": output_tokens,
                "seed": seed % (2**31),
                "sampleRate": 1.0,
                "topK": 5,
            },
        }

    def _update_capability_map(self, record: ProbeRecord) -> None:
        """
        Write probe outcome into capability_map.json.

        Uses the same atomic write pattern as SensingAgent so both agents
        can coexist without corruption.
        """
        cap_map = self._load_capability_map() or {
            "version": 1,
            "updatedAt": time.time(),
            "regions": {},
            "evolutionary_pressure": False,
            "pressure_regions": [],
        }
        regions = cap_map.setdefault("regions", {})
        entry = regions.setdefault(record.region, {
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "first_seen": time.time(),
            "source": "innovation_agent",
        })
        entry["attempts"] += 1
        if record.status == "success":
            entry["successes"] += 1
        else:
            entry["failures"] += 1
        entry["last_updated"] = time.time()
        cap_map["updatedAt"] = time.time()

        self._write_atomic(self.capability_map_path, cap_map)

    def _load_capability_map(self) -> Optional[Dict[str, Any]]:
        if not self.capability_map_path.exists():
            return None
        try:
            return json.loads(self.capability_map_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_probe_log(self, record: ProbeRecord) -> None:
        """Append a probe record to the probe log (append-only JSONL)."""
        line = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        with open(self._probe_log_path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.write("\n")

    def _read_probe_log(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self._probe_log_path.exists():
            return []
        lines = self._probe_log_path.read_text(encoding="utf-8").splitlines()
        records = []
        for line in reversed(lines):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(records) >= limit:
                break
        return records

    def _write_atomic(self, path: Path, payload: Dict[str, Any]) -> None:
        """fsync-safe JSON write: tmp → fsync → rename."""
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        tmp = path.with_suffix(path.suffix + ".tmp")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
