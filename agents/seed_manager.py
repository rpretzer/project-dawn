"""
SeedManager — Phase 2 agent replication substrate.

A *seed* is the minimum viable blueprint for bootstrapping a new agent:

  blueprint          — core identity (Ed25519 key, logit fingerprint), protocol
                       contracts, capability declarations, governing values
  computeReserves    — initial credits sufficient to survive until self-sustaining
  germinationConditions — environmental requirements that must be met before
                       the seed activates:
                         minPeerDensity    — minimum connected peers
                         minDemandSignals  — tasks of the required type queued
                         availableCompute  — free compute-units in the network

Seeds stay dormant in hostile conditions.  That dormancy is intentional.

A *commons pool* accumulates compute credits from successful consensus receipts.
Credits are issued to seeds when a replication cycle is triggered; unclaimed
credits are returned when a seed is culled.

This module provides:

  SeedManager           — create, activate, cull seeds; manage the commons pool
  CommonsPool           — atomic credit ledger
  _write_atomic()       — fsync-safe JSON writer (mirrors the project pattern)

On-disk layout (all under a configurable root, default: data/):
  seeds/{seed_id}.json  — dormant seed blueprint
  mesh/commons.json     — commons credit ledger
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

from data_paths import data_root

logger = logging.getLogger(__name__)

COMMONS_FILE = "mesh/commons.json"
SEEDS_DIR = "seeds"
GERMINATION_WINDOW_SECONDS = 24 * 60 * 60  # 1 day
SEED_SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Atomic write helper
# ---------------------------------------------------------------------------

def _write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    """fsync-safe JSON write: tmp → fsync → rename."""
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Seed schema
# ---------------------------------------------------------------------------

@dataclass
class GerminationConditions:
    minPeerDensity: int = 3
    minDemandSignals: int = 5
    availableComputeUnits: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GerminationConditions":
        return cls(
            minPeerDensity=d.get("minPeerDensity", 3),
            minDemandSignals=d.get("minDemandSignals", 5),
            availableComputeUnits=d.get("availableComputeUnits", 50),
        )


@dataclass
class AgentBlueprint:
    peerId: str
    logitFingerprint: str
    parentId: str
    generation: int
    capabilityDeclarations: List[str] = field(default_factory=list)
    governingValues: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentBlueprint":
        return cls(
            peerId=d["peerId"],
            logitFingerprint=d["logitFingerprint"],
            parentId=d["parentId"],
            generation=d["generation"],
            capabilityDeclarations=d.get("capabilityDeclarations", []),
            governingValues=d.get("governingValues", {}),
        )


@dataclass
class Seed:
    seedId: str
    blueprint: AgentBlueprint
    computeReserves: int
    germinationConditions: GerminationConditions
    issuedAt: float
    expiresAt: float
    status: str = "dormant"   # dormant | active | germinated | culled
    activatedAt: Optional[float] = None
    germinatedAt: Optional[float] = None
    culledAt: Optional[float] = None
    culledReason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "version": SEED_SCHEMA_VERSION,
            "seedId": self.seedId,
            "blueprint": self.blueprint.to_dict(),
            "computeReserves": self.computeReserves,
            "germinationConditions": self.germinationConditions.to_dict(),
            "issuedAt": self.issuedAt,
            "expiresAt": self.expiresAt,
            "status": self.status,
        }
        if self.activatedAt is not None:
            d["activatedAt"] = self.activatedAt
        if self.germinatedAt is not None:
            d["germinatedAt"] = self.germinatedAt
        if self.culledAt is not None:
            d["culledAt"] = self.culledAt
        if self.culledReason is not None:
            d["culledReason"] = self.culledReason
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Seed":
        return cls(
            seedId=d["seedId"],
            blueprint=AgentBlueprint.from_dict(d["blueprint"]),
            computeReserves=d["computeReserves"],
            germinationConditions=GerminationConditions.from_dict(
                d["germinationConditions"]
            ),
            issuedAt=d["issuedAt"],
            expiresAt=d["expiresAt"],
            status=d.get("status", "dormant"),
            activatedAt=d.get("activatedAt"),
            germinatedAt=d.get("germinatedAt"),
            culledAt=d.get("culledAt"),
            culledReason=d.get("culledReason"),
        )

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now or time.time()) >= self.expiresAt

    def is_active_for_too_long(self, now: Optional[float] = None) -> bool:
        if self.status != "active" or self.activatedAt is None:
            return False
        return (now or time.time()) - self.activatedAt >= GERMINATION_WINDOW_SECONDS


# ---------------------------------------------------------------------------
# Commons pool
# ---------------------------------------------------------------------------

@dataclass
class CommonsState:
    totalAccumulated: int = 0
    currentBalance: int = 0
    seedAllocations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "totalAccumulated": self.totalAccumulated,
            "currentBalance": self.currentBalance,
            "seedAllocations": self.seedAllocations,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CommonsState":
        return cls(
            totalAccumulated=d.get("totalAccumulated", 0),
            currentBalance=d.get("currentBalance", 0),
            seedAllocations=d.get("seedAllocations", []),
        )


class CommonsPool:
    """
    Atomic credit ledger for the network commons.

    Accumulates credits from successful consensus receipts and tracks
    allocations to seeds.  All mutations write atomically to disk.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        root = data_dir or data_root()
        self._path = root / COMMONS_FILE
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    def _load(self) -> CommonsState:
        if not self._path.exists():
            return CommonsState()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return CommonsState.from_dict(raw)
        except Exception as exc:
            logger.warning("Failed to load commons pool: %s", exc)
            return CommonsState()

    def _save(self) -> None:
        _write_atomic(self._path, self._state.to_dict())

    @property
    def balance(self) -> int:
        return self._state.currentBalance

    @property
    def total_accumulated(self) -> int:
        return self._state.totalAccumulated

    def accumulate(self, credits: int) -> None:
        """Add credits earned from a successful consensus receipt."""
        self._state.totalAccumulated += credits
        self._state.currentBalance += credits
        self._save()

    def allocate(self, seed_id: str, credits: int) -> bool:
        """
        Reserve *credits* for *seed_id*.

        Returns True if the allocation succeeded (sufficient balance),
        False if insufficient funds.
        """
        if self._state.currentBalance < credits:
            return False
        self._state.currentBalance -= credits
        self._state.seedAllocations.append({
            "seedId": seed_id,
            "credits": credits,
            "allocatedAt": time.time(),
        })
        self._save()
        return True

    def return_credits(self, seed_id: str) -> int:
        """
        Return any allocated credits for *seed_id* to the commons pool.

        Called when a seed is culled.  Returns the number of credits returned.
        """
        returned = 0
        remaining = []
        for alloc in self._state.seedAllocations:
            if alloc["seedId"] == seed_id:
                returned += alloc["credits"]
            else:
                remaining.append(alloc)
        if returned:
            self._state.seedAllocations = remaining
            self._state.currentBalance += returned
            self._save()
            logger.info(
                "Returned %d credits from culled seed %s to commons", returned, seed_id[:16]
            )
        return returned

    def to_dict(self) -> Dict[str, Any]:
        return self._state.to_dict()


# ---------------------------------------------------------------------------
# SeedManager
# ---------------------------------------------------------------------------

class SeedManager:
    """
    Manages the lifecycle of agent seeds.

    Lifecycle:
        issue()      → Seed created in "dormant" state, reserves allocated
        activate()   → "dormant" → "active" when germination conditions are met
        germinate()  → "active" → "germinated" when the agent completes N tasks
        cull()       → any → "culled"; reserves returned to commons pool
        cull_expired() → automatic culling of expired or stalled seeds
    """

    def __init__(self, data_dir: Optional[Path] = None):
        root = data_dir or data_root()
        self._seeds_dir = root / SEEDS_DIR
        self._seeds_dir.mkdir(parents=True, exist_ok=True)
        self.commons = CommonsPool(root)
        self._accepted_rules_path = root / "mesh" / "governance" / "accepted_rules.json"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _load_accepted_rules(self) -> Dict[str, Any]:
        """Load the current accepted governance ruleset, or {} if none yet."""
        if not self._accepted_rules_path.exists():
            return {}
        try:
            raw = json.loads(self._accepted_rules_path.read_text(encoding="utf-8"))
            return raw.get("rules", raw)
        except Exception:
            return {}

    def issue(
        self,
        blueprint: AgentBlueprint,
        compute_reserves: int,
        germination_conditions: Optional[GerminationConditions] = None,
        germination_window_seconds: float = GERMINATION_WINDOW_SECONDS,
    ) -> Optional[Seed]:
        """
        Issue a new seed.

        Derives a deterministic seed_id from the blueprint, allocates
        *compute_reserves* from the commons pool, and writes the seed to disk.

        Governance inheritance: the current accepted ruleset is merged into
        blueprint.governingValues before the seed is issued so that all
        children carry the network's conserved genome at the time of their
        creation.  Caller-supplied values take precedence over the ruleset
        (allowing the caller to override specific rules for specialised seeds).

        Returns the Seed if successful, None if the commons pool has
        insufficient credits.
        """
        # Inherit governing rules — accepted rules are the conserved genome.
        accepted = self._load_accepted_rules()
        if accepted:
            merged = {**accepted, **blueprint.governingValues}
            blueprint = AgentBlueprint(
                peerId=blueprint.peerId,
                logitFingerprint=blueprint.logitFingerprint,
                parentId=blueprint.parentId,
                generation=blueprint.generation,
                capabilityDeclarations=blueprint.capabilityDeclarations,
                governingValues=merged,
                protocolContracts=blueprint.protocolContracts,
            )

        seed_id = _derive_seed_id(blueprint)
        if not self.commons.allocate(seed_id, compute_reserves):
            logger.warning(
                "Cannot issue seed for %s: insufficient commons balance (%d < %d)",
                blueprint.peerId[:16],
                self.commons.balance,
                compute_reserves,
            )
            return None

        now = time.time()
        seed = Seed(
            seedId=seed_id,
            blueprint=blueprint,
            computeReserves=compute_reserves,
            germinationConditions=germination_conditions or GerminationConditions(),
            issuedAt=now,
            expiresAt=now + germination_window_seconds,
        )
        self._save_seed(seed)
        logger.info(
            "Seed issued: seedId=%s peerId=%s reserves=%d",
            seed_id[:16], blueprint.peerId[:16], compute_reserves,
        )
        return seed

    def activate(self, seed_id: str) -> bool:
        """
        Transition a dormant seed to "active".

        Called by the germination checker when all conditions are met.
        Returns True if the transition succeeded.
        """
        seed = self.load(seed_id)
        if not seed:
            logger.warning("activate: seed not found: %s", seed_id[:16])
            return False
        if seed.status != "dormant":
            return False
        seed.status = "active"
        seed.activatedAt = time.time()
        self._save_seed(seed)
        logger.info("Seed activated: %s", seed_id[:16])
        return True

    def germinate(self, seed_id: str) -> bool:
        """
        Transition an active seed to "germinated".

        Called once the child agent has completed its germination tasks.
        The seed is retained for lineage records but its reserves are considered
        spent (the agent is now self-sustaining).
        """
        seed = self.load(seed_id)
        if not seed:
            return False
        if seed.status != "active":
            return False
        seed.status = "germinated"
        seed.germinatedAt = time.time()
        self._save_seed(seed)
        logger.info("Seed germinated: %s", seed_id[:16])
        return True

    def cull(self, seed_id: str, reason: str = "manual") -> int:
        """
        Cull a seed and return its compute reserves to the commons pool.

        Returns the number of credits returned.
        """
        seed = self.load(seed_id)
        if not seed:
            return 0
        if seed.status == "culled":
            return 0
        seed.status = "culled"
        seed.culledAt = time.time()
        seed.culledReason = reason
        self._save_seed(seed)
        returned = self.commons.return_credits(seed_id)
        logger.info(
            "Seed culled: %s reason=%s credits_returned=%d",
            seed_id[:16], reason, returned,
        )
        return returned

    def cull_expired(self) -> List[str]:
        """
        Scan all seeds and cull any that have expired or exceeded the
        germination window.

        Returns a list of culled seed_ids.
        """
        culled: List[str] = []
        now = time.time()
        for seed in self.list_seeds():
            if seed.status in ("germinated", "culled"):
                continue
            if seed.is_expired(now):
                self.cull(seed.seedId, reason="expired")
                culled.append(seed.seedId)
            elif seed.is_active_for_too_long(now):
                self.cull(seed.seedId, reason="germination_window_exceeded")
                culled.append(seed.seedId)
        return culled

    # ------------------------------------------------------------------
    # Germination condition checker
    # ------------------------------------------------------------------

    def check_germination_conditions(
        self,
        seed: Seed,
        peer_count: int,
        demand_signals: int,
        available_compute: int,
    ) -> bool:
        """
        Return True if all germination conditions for *seed* are satisfied.

        Args:
            peer_count:       current number of known peers in the mesh
            demand_signals:   pending tasks of a type matching the seed's capabilities
            available_compute: free compute units available in the network
        """
        gc = seed.germinationConditions
        return (
            peer_count >= gc.minPeerDensity
            and demand_signals >= gc.minDemandSignals
            and available_compute >= gc.availableComputeUnits
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_seed(self, seed: Seed) -> None:
        path = self._seeds_dir / f"{seed.seedId}.json"
        _write_atomic(path, seed.to_dict())

    def load(self, seed_id: str) -> Optional[Seed]:
        path = self._seeds_dir / f"{seed_id}.json"
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return Seed.from_dict(raw)
        except Exception as exc:
            logger.warning("Failed to load seed %s: %s", seed_id[:16], exc)
            return None

    # Alias used by ReplicationAgent for clarity.
    load_seed = load

    def receive_external(self, seed_id: str, payload: Dict[str, Any]) -> bool:
        """
        Store a seed received via the P2P seed offer protocol.

        This is distinct from issue() — externally-received seeds are not
        backed by the local commons pool and carry a provenance record
        (receivedFrom, receivedAt) so the lineage chain remains auditable.

        The payload is expected to contain a full serialised Seed dict plus
        provenance fields added by the sender:
          - schemaVersion  (already verified by caller)
          - senderPeerId
          - receivedAt     (optional; defaults to now)

        Returns True if the seed was stored successfully.
        """
        try:
            seed = Seed.from_dict(payload)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("receive_external: malformed seed payload for %s: %s", seed_id[:16], exc)
            return False

        # Governance compatibility check: warn if the received seed is missing
        # rules that are locally accepted.  We do not reject — the remote node
        # may be operating under a different governance epoch — but we log so
        # the operator is aware.
        local_rules = self._load_accepted_rules()
        seed_rules = seed.blueprint.governingValues
        missing = [k for k in local_rules if k not in seed_rules]
        if missing:
            logger.warning(
                "receive_external: seed %s is missing %d locally-accepted rule(s): %s",
                seed_id[:16], len(missing), missing,
            )

        # Augment the on-disk record with provenance so the lineage is traceable.
        seed_dict = seed.to_dict()
        seed_dict["provenance"] = {
            "receivedFrom": payload.get("senderPeerId", "unknown"),
            "receivedAt": payload.get("receivedAt", time.time()),
            "source": "p2p_offer",
        }

        path = self._seeds_dir / f"{seed_id}.json"
        try:
            _write_atomic(path, seed_dict)
        except OSError as exc:
            logger.error("receive_external: failed to write seed %s: %s", seed_id[:16], exc)
            return False

        logger.info(
            "External seed stored: seedId=%s from=%s",
            seed_id[:16],
            payload.get("senderPeerId", "unknown")[:16],
        )
        return True

    def list_seeds(self, status: Optional[str] = None) -> List[Seed]:
        """List all seeds, optionally filtered by status."""
        seeds = []
        for path in sorted(self._seeds_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                seed = Seed.from_dict(raw)
                if status is None or seed.status == status:
                    seeds.append(seed)
            except Exception as exc:
                logger.warning("Skipping malformed seed %s: %s", path.name, exc)
        return seeds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_seed_id(blueprint: AgentBlueprint) -> str:
    """Derive a deterministic seed_id from the blueprint's identity fields."""
    raw = f"{blueprint.peerId}:{blueprint.logitFingerprint}:{blueprint.parentId}:{blueprint.generation}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
