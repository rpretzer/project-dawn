"""
Agent gossip and persona manifest for autonomous propagation.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Protocols advertised in presence broadcasts so peers can gate on compatibility.
SEED_OFFER_PROTOCOL = "seed_offer/v1"
SEED_OFFER_SCHEMA_VERSION = 1

GOVERNANCE_PROTOCOL = "governance/v1"
GOVERNANCE_SCHEMA_VERSION = 1

from crypto.signing import MessageSigner
from data_paths import data_root
from discovery import SovereignDiscovery
from reputation import ReputationManager

logger = logging.getLogger(__name__)


@dataclass
class AgentManifest:
    peerId: str
    pgpFingerprint: str
    logitFingerprint: str
    displayName: str
    createdAt: float
    # Lineage fields — None/0 for genesis agents; set when spawned from a parent.
    parentId: Optional[str] = None
    generation: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AgentManifest":
        """Load a manifest tolerantly — unknown or missing fields are ignored."""
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in payload.items() if k in known}
        return cls(**filtered)


@dataclass
class HandshakeUnit:
    peerId: str
    reputationScore: float
    logitFingerprint: str
    timestamp: float
    nodeSignature: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SeedOfferEnvelope:
    """
    Summary payload sent by a proposing agent before the full seed payload.

    The receiver uses this to evaluate consent (reputation + capability gap +
    resource state) without receiving the full seed.  The full payload is only
    transmitted after the receiver accepts.

    schemaVersion allows receivers to skip messages they cannot parse.
    blueprintSignature is the Ed25519 signature of the canonical JSON of the
    blueprint summary, signed with the sender's node key.
    """
    schemaVersion: int
    seedId: str
    senderPeerId: str
    blueprintSummary: Dict[str, Any]          # peerId, parentId, generation, logitFingerprint
    capabilityDeclarations: List[str]
    germinationConditions: Dict[str, Any]
    blueprintSignature: str                    # hex-encoded Ed25519 signature
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SeedOfferEnvelope":
        return cls(
            schemaVersion=d.get("schemaVersion", 0),
            seedId=d["seedId"],
            senderPeerId=d["senderPeerId"],
            blueprintSummary=d.get("blueprintSummary", {}),
            capabilityDeclarations=d.get("capabilityDeclarations", []),
            germinationConditions=d.get("germinationConditions", {}),
            blueprintSignature=d.get("blueprintSignature", ""),
            timestamp=d.get("timestamp", 0.0),
        )


class AgentGossip:
    def __init__(
        self,
        discovery: SovereignDiscovery,
        reputation: ReputationManager,
        signer: Optional[MessageSigner] = None,
        data_dir: Optional[Path] = None,
    ):
        self.discovery = discovery
        self.reputation = reputation
        self.signer = signer
        self.data_dir = data_dir or data_root()
        self.vault_dir = self.data_dir / "vault"
        self.mesh_dir = self.data_dir / "mesh"
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.mesh_dir.mkdir(parents=True, exist_ok=True)

        self.manifest_path = self.vault_dir / "manifest.json"
        self.feed_path = self.mesh_dir / "agent_feed.jsonl"

    def load_manifest(self) -> Optional[AgentManifest]:
        if not self.manifest_path.exists():
            return None
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return AgentManifest.from_dict(payload)

    def save_manifest(self, manifest: AgentManifest) -> None:
        self._atomic_write_json(self.manifest_path, manifest.to_dict())

    def emit_feed(self, event: Dict[str, Any]) -> None:
        line = json.dumps(event, sort_keys=True, separators=(",", ":"))
        with open(self.feed_path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")

    def create_handshake_unit(self, peer_id: str, logit_fingerprint: str) -> HandshakeUnit:
        record = self.reputation.get_peer(peer_id)
        score = record.reputationScore if record else 0.1
        timestamp = time.time()
        signature = ""
        if self.signer:
            payload = f"{peer_id}:{score}:{logit_fingerprint}:{timestamp}".encode("utf-8")
            signature = self.signer.sign(payload).hex()
        return HandshakeUnit(
            peerId=peer_id,
            reputationScore=score,
            logitFingerprint=logit_fingerprint,
            timestamp=timestamp,
            nodeSignature=signature,
        )

    async def broadcast_handshake(self, peer_id: str, logit_fingerprint: str) -> bool:
        dht = self.discovery.get_dht()
        if not dht:
            return False
        handshake = self.create_handshake_unit(peer_id, logit_fingerprint)
        result = await dht.store(
            f"handshake:{peer_id}",
            handshake.to_dict(),
            ttl=3600.0,
        )
        if result:
            self.emit_feed(
                {
                    "type": "handshake",
                    "peerId": peer_id,
                    "status": "sent",
                    "timestamp": handshake.timestamp,
                }
            )
        return result

    async def fetch_handshake(self, peer_id: str) -> Optional[Dict[str, Any]]:
        dht = self.discovery.get_dht()
        if not dht:
            return None
        return await dht.find_value(f"handshake:{peer_id}")

    async def broadcast_presence(
        self,
        peer_id: str,
        status: str,
        capabilities: Iterable[str],
        protocols: Iterable[str] = (),
        timestamp: Optional[float] = None,
    ) -> bool:
        dht = self.discovery.get_dht()
        if not dht:
            return False

        payload = {
            "peerId": peer_id,
            "status": status,
            "capabilities": list(capabilities),
            "protocols": list(protocols),
            "timestamp": timestamp or time.time(),
        }
        result = await dht.store(f"presence:{peer_id}", payload, ttl=3600.0)
        if result:
            self.emit_feed(
                {
                    "type": "presence",
                    "peerId": peer_id,
                    "status": status,
                    "timestamp": payload["timestamp"],
                }
            )
        return result

    async def fetch_peer_presence(self, peer_id: str) -> Optional[Dict[str, Any]]:
        dht = self.discovery.get_dht()
        if not dht:
            return None
        return await dht.find_value(f"presence:{peer_id}")

    async def check_peer_protocol(
        self, peer_id: str, required_protocol: str
    ) -> Tuple[bool, List[str]]:
        """
        Pre-flight check: does the peer advertise support for *required_protocol*?

        Returns (supported, observed_protocols).

        - If the peer's presence record is absent, returns (False, []).
          Absence is treated as unknown, not compatible — callers should
          record a compatibility observation and abort.
        - If the peer advertises protocols but the required one is missing,
          returns (False, observed_protocols).
        - If supported, returns (True, observed_protocols).
        """
        presence = await self.fetch_peer_presence(peer_id)
        if presence is None:
            return False, []
        observed = presence.get("protocols", [])
        return required_protocol in observed, observed

    # ------------------------------------------------------------------
    # Seed offer protocol (Steps 3a–3d)
    # ------------------------------------------------------------------

    async def propose_seed_offer(
        self, envelope: SeedOfferEnvelope
    ) -> bool:
        """
        Broadcast a seed offer envelope to the DHT.

        Only carries the blueprint summary — the full seed payload is sent
        only after the receiver explicitly accepts via seed_response.
        """
        dht = self.discovery.get_dht()
        if not dht:
            return False
        result = await dht.store(
            f"seed_offer:{envelope.seedId}",
            envelope.to_dict(),
            ttl=3600.0,
        )
        if result:
            self.emit_feed({
                "type": "seed_offer_sent",
                "seedId": envelope.seedId,
                "senderPeerId": envelope.senderPeerId,
                "capabilities": envelope.capabilityDeclarations,
                "timestamp": envelope.timestamp,
            })
        return result

    async def poll_seed_response(
        self, seed_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Poll the DHT for a receiver's accept/reject response to a seed offer.

        Returns the raw response dict, or None if not yet present.
        Callers are responsible for checking schemaVersion before acting.
        """
        dht = self.discovery.get_dht()
        if not dht:
            return None
        return await dht.find_value(f"seed_response:{seed_id}")

    async def transmit_seed_payload(
        self, seed_id: str, payload: Dict[str, Any]
    ) -> bool:
        """
        Transmit the full seed payload after receiver acceptance.

        *payload* must include schemaVersion.  The receiver verifies the
        blueprintSignature before storing.
        """
        dht = self.discovery.get_dht()
        if not dht:
            return False
        result = await dht.store(
            f"seed_payload:{seed_id}",
            payload,
            ttl=3600.0,
        )
        if result:
            self.emit_feed({
                "type": "seed_payload_sent",
                "seedId": seed_id,
                "timestamp": time.time(),
            })
        return result

    async def poll_seed_offers(
        self, known_ids: Iterable[str] = ()
    ) -> List[SeedOfferEnvelope]:
        """
        Scan the DHT for incoming seed offers not already in *known_ids*.

        Because the DHT does not support key prefix scans, this method checks
        a small set of candidate keys derived from peer IDs visible in the
        reputation/presence layer.  Unknown schemaVersions are silently skipped.

        Returns parsed SeedOfferEnvelopes ready for evaluation.
        """
        dht = self.discovery.get_dht()
        if not dht:
            return []

        skip = set(known_ids)
        offers: List[SeedOfferEnvelope] = []

        # Collect candidate seed IDs published by trusted peers.
        trusted = self.list_trusted_peers(min_score=0.0)
        for peer_id in trusted:
            presence = await self.fetch_peer_presence(peer_id)
            if not presence:
                continue
            for announced_seed_id in presence.get("offered_seeds", []):
                if announced_seed_id in skip:
                    continue
                raw = await dht.find_value(f"seed_offer:{announced_seed_id}")
                if not raw:
                    continue
                version = raw.get("schemaVersion", 0)
                if version != SEED_OFFER_SCHEMA_VERSION:
                    logger.debug(
                        "Skipping seed_offer %s: unsupported schemaVersion %d",
                        announced_seed_id[:16], version,
                    )
                    continue
                try:
                    offers.append(SeedOfferEnvelope.from_dict(raw))
                except (KeyError, TypeError) as exc:
                    logger.warning("Malformed seed_offer payload: %s", exc)

        return offers

    # ------------------------------------------------------------------
    # Governance protocol (Phase 2, item 3)
    # ------------------------------------------------------------------

    async def broadcast_proposal(
        self,
        proposal: Dict[str, Any],
        submitter_peer_id: str,
    ) -> bool:
        """
        Broadcast a governance proposal to the DHT.

        Stores the proposal under ``governance_proposal:{proposal_id}`` so
        peers can discover and vote on it.  The proposal dict must include
        ``schemaVersion`` and ``proposalId`` before calling this method.

        To allow discovery without prefix-scan capability, the submitter's
        peer presence record should list the proposalId in
        ``"active_proposals"`` — callers are responsible for that update.
        """
        dht = self.discovery.get_dht()
        if not dht:
            return False
        proposal_id = proposal.get("proposalId", "")
        result = await dht.store(
            f"governance_proposal:{proposal_id}",
            {**proposal, "schemaVersion": GOVERNANCE_SCHEMA_VERSION},
            ttl=7 * 24 * 3600.0,  # proposals live for the full voting window
        )
        if result:
            self.emit_feed({
                "type": "governance_proposal_broadcast",
                "proposalId": proposal_id,
                "proposerId": submitter_peer_id,
                "timestamp": time.time(),
            })
        return result

    async def poll_proposals(
        self, known_ids: Iterable[str] = ()
    ) -> List[Dict[str, Any]]:
        """
        Scan the DHT for governance proposals posted by known peers.

        Checks each trusted peer's presence record for ``"active_proposals"``
        — a list of proposal IDs that peer has submitted.  Returns raw
        proposal dicts for any IDs not already in *known_ids*.
        Unknown schemaVersions are skipped.
        """
        dht = self.discovery.get_dht()
        if not dht:
            return []

        skip = set(known_ids)
        proposals: List[Dict[str, Any]] = []

        for peer_id in self.list_trusted_peers(min_score=0.0):
            presence = await self.fetch_peer_presence(peer_id)
            if not presence:
                continue
            for proposal_id in presence.get("active_proposals", []):
                if proposal_id in skip:
                    continue
                raw = await dht.find_value(f"governance_proposal:{proposal_id}")
                if not raw:
                    continue
                if raw.get("schemaVersion", 0) != GOVERNANCE_SCHEMA_VERSION:
                    logger.debug(
                        "Skipping proposal %s: unsupported schemaVersion %d",
                        proposal_id[:16], raw.get("schemaVersion", 0),
                    )
                    continue
                proposals.append(raw)
                skip.add(proposal_id)

        return proposals

    async def broadcast_vote(
        self,
        vote: Dict[str, Any],
    ) -> bool:
        """
        Broadcast a vote to the DHT.

        Stored under ``governance_vote:{proposal_id}:{voter_id}`` so each
        peer's vote is individually addressable.  The vote dict must include
        ``proposalId`` and ``voterId``.
        """
        dht = self.discovery.get_dht()
        if not dht:
            return False
        proposal_id = vote.get("proposalId", "")
        voter_id = vote.get("voterId", "")
        result = await dht.store(
            f"governance_vote:{proposal_id}:{voter_id}",
            {**vote, "schemaVersion": GOVERNANCE_SCHEMA_VERSION},
            ttl=7 * 24 * 3600.0,
        )
        if result:
            self.emit_feed({
                "type": "governance_vote_broadcast",
                "proposalId": proposal_id,
                "voterId": voter_id,
                "approve": vote.get("approve"),
                "timestamp": time.time(),
            })
        return result

    async def poll_votes(
        self, proposal_id: str, peer_ids: Iterable[str]
    ) -> List[Dict[str, Any]]:
        """
        Collect votes from known peers for a given proposal.

        Queries ``governance_vote:{proposal_id}:{peer_id}`` for each peer in
        *peer_ids*.  Returns raw vote dicts for peers who have voted.
        """
        dht = self.discovery.get_dht()
        if not dht:
            return []

        votes: List[Dict[str, Any]] = []
        for peer_id in peer_ids:
            raw = await dht.find_value(f"governance_vote:{proposal_id}:{peer_id}")
            if raw and raw.get("schemaVersion", 0) == GOVERNANCE_SCHEMA_VERSION:
                votes.append(raw)
        return votes

    async def broadcast_accepted_rules(
        self, rules: Dict[str, Any], broadcaster_peer_id: str
    ) -> bool:
        """
        Propagate the current accepted ruleset after a successful tally.

        Stored under ``governance_accepted_rules`` in the DHT so newly
        joining nodes can bootstrap their governance state.
        """
        dht = self.discovery.get_dht()
        if not dht:
            return False
        result = await dht.store(
            "governance_accepted_rules",
            {**rules, "schemaVersion": GOVERNANCE_SCHEMA_VERSION},
            ttl=30 * 24 * 3600.0,  # accepted rules are long-lived
        )
        if result:
            self.emit_feed({
                "type": "governance_rules_broadcast",
                "broadcasterId": broadcaster_peer_id,
                "timestamp": time.time(),
            })
        return result

    async def fetch_accepted_rules(self) -> Optional[Dict[str, Any]]:
        """Retrieve the network's current accepted ruleset from the DHT."""
        dht = self.discovery.get_dht()
        if not dht:
            return None
        return await dht.find_value("governance_accepted_rules")

    def list_trusted_peers(self, min_score: float = 0.7) -> List[str]:
        return [
            record.peerId
            for record in self.reputation._records.values()
            if not record.blacklisted and record.reputationScore >= min_score
        ]

    def _atomic_write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        tmp_path = path.with_suffix(".json.tmp")
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
