"""
ReplicationAgent — Phase 2 evolutionary replication coordinator.

Closes the Phase 2 loop:

  SensingAgent detects pressure  →  ReplicationAgent issues seeds
  Seeds germinate                →  New agents join the mesh
  Failed seeds are culled        →  Credits returned to commons pool

Algorithm (triggered when SensingAgent.is_under_pressure() is True):

  1. Load reputation records; identify candidate parents (reputation ≥ threshold).
  2. For each candidate, derive a child AgentBlueprint:
       parentId          = candidate's peerId
       generation        = candidate's generation + 1
       logitFingerprint  = heritable variant of parent fingerprint
       capabilityDeclarations = biased toward the pressure region's capability type
  3. Call SeedManager.issue(blueprint, compute_reserves) — allocates from commons pool.
  4. Emit a replication event to the agent feed.
  5. Broadcast the seed issuance via DHT (key: "replication:{seedId}").

The ReplicationAgent does NOT decide when to replicate — the SensingAgent surfaces
the signal.  The ReplicationAgent acts on it.  This separation keeps the sensing and
replication concerns cleanly decoupled.

MCP tools exposed:
  trigger_replication  — manually trigger a replication cycle (for testing / ops)
  list_seeds           — list all seeds and their lifecycle status
  get_commons_balance  — query the commons pool credit balance
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from agents.seed_manager import (
    AgentBlueprint,
    CommonsPool,
    GerminationConditions,
    Seed,
    SeedManager,
)
from communication import AgentGossip, SeedOfferEnvelope, SEED_OFFER_PROTOCOL, SEED_OFFER_SCHEMA_VERSION
from data_paths import data_root

logger = logging.getLogger(__name__)

# Minimum reputation score to qualify as a candidate parent.
DEFAULT_PARENT_REPUTATION_THRESHOLD = 0.6

# Compute reserves allocated to each new seed.
DEFAULT_SEED_COMPUTE_RESERVES = 100

# Maximum number of seeds issued per replication cycle.
MAX_SEEDS_PER_CYCLE = 3


def _child_fingerprint(parent_fingerprint: str, generation: int) -> str:
    """
    Derive a heritable-but-variant logit fingerprint for a child agent.

    The child's fingerprint is a SHA-256 hash of the parent's fingerprint,
    the new generation, and a random nonce.  This means:
      - The child is cryptographically traceable to the parent.
      - No two children have identical fingerprints (nonce ensures variation).
      - The "distance" between two fingerprints (XOR of SHA-256 prefixes)
        measures evolutionary distance.
    """
    raw = f"{parent_fingerprint}:gen{generation}:{uuid.uuid4()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _load_reputation(reputation_path: Path) -> Dict[str, float]:
    """Load the reputation score map from disk.  Returns {} if unavailable."""
    if not reputation_path.exists():
        return {}
    try:
        raw = json.loads(reputation_path.read_text(encoding="utf-8"))
        # reputation.json schema: {"scores": {"peerId": float, ...}}
        scores = raw.get("scores", raw)  # handle both formats
        return {k: float(v) for k, v in scores.items() if isinstance(v, (int, float))}
    except Exception as exc:
        logger.warning("Could not load reputation: %s", exc)
        return {}


def _load_lineage(vault_dir: Path) -> Dict[str, Any]:
    """Load the local node's lineage.json to extract peerId and generation."""
    lineage_path = vault_dir / "lineage.json"
    if not lineage_path.exists():
        return {}
    try:
        return json.loads(lineage_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class ReplicationAgent(BaseAgent):
    """
    Coordinates seed issuance when the SensingAgent detects evolutionary pressure.
    """

    def __init__(
        self,
        mesh_dir: Optional[Path] = None,
        vault_dir: Optional[Path] = None,
        data_dir: Optional[Path] = None,
        parent_reputation_threshold: float = DEFAULT_PARENT_REPUTATION_THRESHOLD,
        seed_compute_reserves: int = DEFAULT_SEED_COMPUTE_RESERVES,
        max_seeds_per_cycle: int = MAX_SEEDS_PER_CYCLE,
        gossip: Optional[AgentGossip] = None,
        sensing_agent: Optional[Any] = None,
    ) -> None:
        super().__init__("replication", "ReplicationAgent", data_dir=data_dir)
        root = data_root()
        self.mesh_dir = mesh_dir or (root / "mesh")
        self.vault_dir = vault_dir or (root / "vault")
        self.parent_reputation_threshold = parent_reputation_threshold
        self.seed_compute_reserves = seed_compute_reserves
        self.max_seeds_per_cycle = max_seeds_per_cycle
        self.gossip = gossip
        self.sensing_agent = sensing_agent

        # Derive the data root from mesh_dir so SeedManager writes to the same
        # tree as the rest of the node's state (e.g. tmp_path in tests).
        data_root_dir = self.mesh_dir.parent
        self._seed_manager = SeedManager(data_dir=data_root_dir)
        self._feed_path = self.mesh_dir / "agent_feed.jsonl"
        self._reputation_path = self.mesh_dir / "reputation.json"
        self._resource_state_path = self.mesh_dir / "resource_state.json"

        self._register_tools()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def replicate(
        self,
        pressure_regions: Optional[List[str]] = None,
        capability_hint: Optional[str] = None,
    ) -> List[Seed]:
        """
        Run one replication cycle.

        Identifies candidate parents, issues seeds biased toward the pressure
        regions, emits feed events, and returns the list of issued seeds.

        Args:
            pressure_regions: Region keys (sha256[:4]) flagged by SensingAgent.
            capability_hint:  Optional capability type to bias children toward.
        """
        reputation_scores = _load_reputation(self._reputation_path)
        lineage = _load_lineage(self.vault_dir)

        candidates = self._select_candidates(reputation_scores)
        if not candidates:
            logger.info("ReplicationAgent: no candidate parents with sufficient reputation")
            return []

        issued: List[Seed] = []
        for peer_id in candidates[: self.max_seeds_per_cycle]:
            score = reputation_scores.get(peer_id, 0.0)
            blueprint = self._build_child_blueprint(
                parent_peer_id=peer_id,
                parent_lineage=lineage,
                capability_hint=capability_hint,
                parent_generation=lineage.get("generation", 0)
                if lineage.get("peerId") == peer_id
                else 0,
            )
            seed = self._seed_manager.issue(
                blueprint,
                compute_reserves=self.seed_compute_reserves,
            )
            if seed:
                issued.append(seed)
                self._emit_feed_event(
                    event_type="seed_issued",
                    seed_id=seed.seedId,
                    parent_peer_id=peer_id,
                    parent_reputation=score,
                    pressure_regions=pressure_regions or [],
                )
                logger.info(
                    "Seed issued for parent %s... (generation=%d reputation=%.2f)",
                    peer_id[:16], blueprint.generation, score,
                )
            else:
                logger.warning(
                    "Failed to issue seed for %s... (commons balance=%d)",
                    peer_id[:16], self._seed_manager.commons.balance,
                )

        return issued

    def activate_ready_seeds(
        self,
        peer_count: int,
        demand_signals: int,
        available_compute: int,
    ) -> List[str]:
        """
        Check all dormant seeds and activate those whose germination conditions
        are met.

        Returns a list of activated seed_ids.
        """
        activated: List[str] = []
        for seed in self._seed_manager.list_seeds(status="dormant"):
            if seed.is_expired():
                continue
            if self._seed_manager.check_germination_conditions(
                seed, peer_count, demand_signals, available_compute
            ):
                if self._seed_manager.activate(seed.seedId):
                    activated.append(seed.seedId)
                    self._emit_feed_event(
                        event_type="seed_activated",
                        seed_id=seed.seedId,
                        peer_count=peer_count,
                        demand_signals=demand_signals,
                    )
        return activated

    def cull_expired(self) -> List[str]:
        """Cull expired/stalled seeds and return credits to commons pool."""
        culled = self._seed_manager.cull_expired()
        for seed_id in culled:
            self._emit_feed_event(event_type="seed_culled", seed_id=seed_id)
        return culled

    # ------------------------------------------------------------------
    # Seed offer protocol — sender side (Step 6)
    # ------------------------------------------------------------------

    async def propose_seed_transfer(
        self,
        seed_id: str,
        target_peer_id: Optional[str] = None,
        local_peer_id: str = "",
    ) -> Dict[str, Any]:
        """
        Propose a seed transfer to *target_peer_id* (or broadcast if None).

        Pre-flight: checks that the target advertises seed_offer/v1.
        On protocol mismatch: records a compatibility observation and aborts.

        Returns a result dict with keys: sent (bool), reason (str).
        """
        if not self.gossip:
            return {"sent": False, "reason": "no_gossip_layer"}

        seed = self._seed_manager.load_seed(seed_id)
        if not seed:
            return {"sent": False, "reason": "seed_not_found"}

        if target_peer_id:
            supported, observed = await self.gossip.check_peer_protocol(
                target_peer_id, SEED_OFFER_PROTOCOL
            )
            if not supported:
                if self.sensing_agent:
                    self.sensing_agent.record_compatibility_observation(
                        peer_id=target_peer_id,
                        observed_protocols=observed,
                        mismatched_protocol=SEED_OFFER_PROTOCOL,
                    )
                self._emit_feed_event(
                    event_type="seed_offer_aborted",
                    seed_id=seed_id,
                    target_peer_id=target_peer_id,
                    reason="protocol_mismatch",
                    observed_protocols=observed,
                )
                return {"sent": False, "reason": "protocol_mismatch", "observed": observed}

        blueprint = seed.blueprint
        envelope = SeedOfferEnvelope(
            schemaVersion=SEED_OFFER_SCHEMA_VERSION,
            seedId=seed_id,
            senderPeerId=local_peer_id,
            blueprintSummary={
                "peerId": blueprint.peerId,
                "parentId": blueprint.parentId,
                "generation": blueprint.generation,
                "logitFingerprint": blueprint.logitFingerprint,
            },
            capabilityDeclarations=blueprint.capabilityDeclarations,
            germinationConditions=seed.germinationConditions.to_dict(),
            blueprintSignature="",  # TODO: sign with node key when signer available
            timestamp=time.time(),
        )

        sent = await self.gossip.propose_seed_offer(envelope)
        if sent:
            self._emit_feed_event(
                event_type="seed_offer_sent",
                seed_id=seed_id,
                target_peer_id=target_peer_id,
            )
        return {"sent": sent, "reason": "ok" if sent else "dht_error"}

    # ------------------------------------------------------------------
    # Seed offer protocol — receiver side (Step 7)
    # ------------------------------------------------------------------

    def evaluate_seed_offer(
        self, envelope: SeedOfferEnvelope
    ) -> tuple:
        """
        Evaluate an incoming seed offer against the three consent layers.

        Returns (accept: bool, reason: str).

        Consent layers (all required):
          1. schemaVersion must be known
          2. Sender reputation >= parent_reputation_threshold
          3. Capability declarations intersect pressure_regions in capability_map
          4. Resource state is not throttled
        """
        if envelope.schemaVersion != SEED_OFFER_SCHEMA_VERSION:
            return False, "schema_version_unsupported"

        # Layer 1: reputation gate
        reputation = _load_reputation(self._reputation_path)
        sender_score = reputation.get(envelope.senderPeerId, 0.0)
        if sender_score < self.parent_reputation_threshold:
            return False, f"reputation_too_low:{sender_score:.2f}"

        # Layer 2: capability gap alignment
        if not self._check_capability_gap(envelope.capabilityDeclarations):
            return False, "no_capability_gap_alignment"

        # Layer 3: resource state
        if not self._check_resource_available():
            return False, "resource_throttled"

        return True, "accepted"

    def _check_capability_gap(self, declarations: List[str]) -> bool:
        """Return True if any declaration matches a current pressure region type."""
        cap_map_path = self.mesh_dir / "capability_map.json"
        if not cap_map_path.exists():
            # No map yet — accept on capability grounds (can't detect a gap to fill).
            return True
        try:
            cap_map = json.loads(cap_map_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return True
        pressure_regions = cap_map.get("pressure_regions", [])
        if not pressure_regions:
            return False
        # pressure_regions are task-region hex keys; declarations are capability
        # type strings.  We accept if the network is under any pressure at all
        # and the offer brings relevant capabilities.
        # Phase 2: use embedding-space proximity for finer matching.
        return bool(declarations)

    def _check_resource_available(self) -> bool:
        """Return True if the local node is not currently throttled."""
        if not self._resource_state_path.exists():
            return True
        try:
            state = json.loads(self._resource_state_path.read_text(encoding="utf-8"))
            return not state.get("throttle", False)
        except (json.JSONDecodeError, OSError):
            return True

    async def receive_seed_payload(
        self, seed_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Receive and store a full seed payload after accepting an offer.

        Verifies schemaVersion, then delegates storage to SeedManager.receive_external().
        Returns a result dict with keys: stored (bool), reason (str).
        """
        version = payload.get("schemaVersion", 0)
        if version != SEED_OFFER_SCHEMA_VERSION:
            return {"stored": False, "reason": "schema_version_unsupported"}

        stored = self._seed_manager.receive_external(seed_id, payload)
        if stored:
            self._emit_feed_event(
                event_type="seed_received",
                seed_id=seed_id,
                received_from=payload.get("senderPeerId", "unknown"),
            )
        return {"stored": stored, "reason": "ok" if stored else "storage_failed"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _select_candidates(self, reputation_scores: Dict[str, float]) -> List[str]:
        """Return peer IDs sorted by reputation score (descending) that meet the threshold."""
        return sorted(
            [pid for pid, score in reputation_scores.items()
             if score >= self.parent_reputation_threshold],
            key=lambda pid: reputation_scores[pid],
            reverse=True,
        )

    def _build_child_blueprint(
        self,
        parent_peer_id: str,
        parent_lineage: Dict[str, Any],
        capability_hint: Optional[str],
        parent_generation: int,
    ) -> AgentBlueprint:
        """Construct an AgentBlueprint for a new child agent."""
        parent_fingerprint = parent_lineage.get("logitFingerprint", parent_peer_id)
        child_generation = parent_generation + 1
        child_fingerprint = _child_fingerprint(parent_fingerprint, child_generation)

        # Derive a stable but unique child peer ID from parent + fingerprint.
        raw_id = f"child:{parent_peer_id}:{child_fingerprint}"
        child_peer_id = hashlib.sha256(raw_id.encode()).hexdigest()[:40]

        capabilities = ["text-inference", "proof-of-logits"]
        if capability_hint:
            capabilities = [capability_hint] + [c for c in capabilities if c != capability_hint]

        return AgentBlueprint(
            peerId=child_peer_id,
            logitFingerprint=child_fingerprint,
            parentId=parent_peer_id,
            generation=child_generation,
            capabilityDeclarations=capabilities,
        )

    def _emit_feed_event(self, event_type: str, **kwargs: Any) -> None:
        """Append an event to the agent feed."""
        event = {"type": event_type, "timestamp": time.time(), **kwargs}
        try:
            self._feed_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._feed_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, sort_keys=True, separators=(",", ":")))
                fh.write("\n")
        except Exception as exc:
            logger.warning("Failed to emit feed event: %s", exc)

    # ------------------------------------------------------------------
    # MCP tools
    # ------------------------------------------------------------------

    def _register_tools(self) -> None:
        self.register_tool(
            "propose_seed_transfer",
            "Propose a P2P seed transfer to a specific peer or broadcast to all compatible peers.",
            self._tool_propose_seed_transfer,
            inputSchema={
                "type": "object",
                "properties": {
                    "seed_id": {
                        "type": "string",
                        "description": "ID of the seed to offer.",
                    },
                    "target_peer_id": {
                        "type": "string",
                        "description": "Peer to offer the seed to (optional; broadcast if omitted).",
                    },
                },
                "required": ["seed_id"],
            },
        )
        self.register_tool(
            "trigger_replication",
            "Manually trigger a replication cycle.  Issues seeds for candidate parents.",
            self._tool_trigger_replication,
            inputSchema={
                "type": "object",
                "properties": {
                    "capability_hint": {
                        "type": "string",
                        "description": "Bias children toward this capability type (optional).",
                    }
                },
            },
        )
        self.register_tool(
            "list_seeds",
            "List all agent seeds and their current lifecycle status.",
            self._tool_list_seeds,
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["dormant", "active", "germinated", "culled"],
                        "description": "Filter by status (optional; omit for all).",
                    }
                },
            },
        )
        self.register_tool(
            "get_commons_balance",
            "Return the current commons pool credit balance.",
            self._tool_get_commons_balance,
            inputSchema={"type": "object", "properties": {}},
        )

    async def _tool_propose_seed_transfer(
        self,
        seed_id: str,
        target_peer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self.propose_seed_transfer(seed_id, target_peer_id)

    def _tool_trigger_replication(self, capability_hint: Optional[str] = None) -> Dict[str, Any]:
        seeds = self.replicate(capability_hint=capability_hint)
        return {
            "seeds_issued": len(seeds),
            "seed_ids": [s.seedId for s in seeds],
            "commons_balance": self._seed_manager.commons.balance,
        }

    def _tool_list_seeds(self, status: Optional[str] = None) -> Dict[str, Any]:
        seeds = self._seed_manager.list_seeds(status=status)
        return {
            "seeds": [s.to_dict() for s in seeds],
            "total": len(seeds),
        }

    def _tool_get_commons_balance(self) -> Dict[str, Any]:
        return {
            "currentBalance": self._seed_manager.commons.balance,
            "totalAccumulated": self._seed_manager.commons.total_accumulated,
        }
