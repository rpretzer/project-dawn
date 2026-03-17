"""
Tests for the P2P seed offer protocol.

Covers:
- SeedOfferEnvelope: round-trip serialisation
- AgentGossip.check_peer_protocol: supported / missing / absent presence
- AgentGossip.broadcast_presence: protocols field included in DHT payload
- SensingAgent.record_compatibility_observation: written + merged atomically
- SensingAgent.scan: preserves compatibility section across scans
- ReplicationAgent.evaluate_seed_offer: all four consent layers
- ReplicationAgent.propose_seed_transfer: protocol mismatch → compatibility observation
- ReplicationAgent.receive_seed_payload: schema gate + storage
- SeedManager.receive_external: stored with provenance, load_seed alias
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.replication_agent import ReplicationAgent
from agents.seed_manager import (
    AgentBlueprint,
    GerminationConditions,
    SeedManager,
    _derive_seed_id,
)
from agents.sensing_agent import SensingAgent
from communication import (
    AgentGossip,
    SeedOfferEnvelope,
    SEED_OFFER_PROTOCOL,
    SEED_OFFER_SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_blueprint(peer_id: str = "peer-abc", generation: int = 1) -> AgentBlueprint:
    return AgentBlueprint(
        peerId=peer_id,
        logitFingerprint="fp-" + peer_id,
        parentId="parent-000",
        generation=generation,
        capabilityDeclarations=["text-inference", "proof-of-logits"],
    )


def _make_envelope(
    seed_id: str = "seed-001",
    sender_peer_id: str = "sender-peer",
    schema_version: int = SEED_OFFER_SCHEMA_VERSION,
    capabilities: list = None,
) -> SeedOfferEnvelope:
    return SeedOfferEnvelope(
        schemaVersion=schema_version,
        seedId=seed_id,
        senderPeerId=sender_peer_id,
        blueprintSummary={
            "peerId": "child-peer",
            "parentId": sender_peer_id,
            "generation": 1,
            "logitFingerprint": "fp-child",
        },
        capabilityDeclarations=capabilities or ["text-inference"],
        germinationConditions={"minPeerDensity": 3, "minDemandSignals": 5, "availableComputeUnits": 50},
        blueprintSignature="",
        timestamp=time.time(),
    )


def _make_replication_agent(
    tmp_path: Path,
    reputation: Dict[str, float] = None,
    throttled: bool = False,
    gossip=None,
    sensing_agent=None,
    threshold: float = 0.5,
) -> ReplicationAgent:
    mesh_dir = tmp_path / "mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    if reputation is not None:
        rep_path = mesh_dir / "reputation.json"
        rep_path.write_text(json.dumps({"scores": reputation}))

    if throttled:
        rs_path = mesh_dir / "resource_state.json"
        rs_path.write_text(json.dumps({"throttle": True}))

    return ReplicationAgent(
        mesh_dir=mesh_dir,
        vault_dir=tmp_path / "vault",
        data_dir=tmp_path / "agent-state",
        parent_reputation_threshold=threshold,
        gossip=gossip,
        sensing_agent=sensing_agent,
    )


# ---------------------------------------------------------------------------
# SeedOfferEnvelope
# ---------------------------------------------------------------------------

class TestSeedOfferEnvelope:
    def test_round_trip(self):
        env = _make_envelope()
        restored = SeedOfferEnvelope.from_dict(env.to_dict())
        assert restored.seedId == env.seedId
        assert restored.senderPeerId == env.senderPeerId
        assert restored.schemaVersion == env.schemaVersion
        assert restored.capabilityDeclarations == env.capabilityDeclarations
        assert restored.germinationConditions == env.germinationConditions

    def test_from_dict_tolerates_missing_optional_fields(self):
        minimal = {
            "schemaVersion": 1,
            "seedId": "s1",
            "senderPeerId": "p1",
        }
        env = SeedOfferEnvelope.from_dict(minimal)
        assert env.blueprintSignature == ""
        assert env.capabilityDeclarations == []


# ---------------------------------------------------------------------------
# AgentGossip.broadcast_presence — protocols field
# ---------------------------------------------------------------------------

class TestBroadcastPresenceProtocols:
    @pytest.mark.asyncio
    async def test_protocols_included_in_dht_payload(self):
        mock_dht = AsyncMock()
        mock_dht.store = AsyncMock(return_value=True)

        discovery = MagicMock()
        discovery.get_dht.return_value = mock_dht
        reputation = MagicMock()
        reputation._records = {}

        gossip = AgentGossip(discovery, reputation)
        gossip.feed_path.parent.mkdir(parents=True, exist_ok=True)
        gossip.feed_path.touch()

        await gossip.broadcast_presence(
            peer_id="peer-1",
            status="online",
            capabilities=["compute"],
            protocols=[SEED_OFFER_PROTOCOL],
        )

        stored_payload = mock_dht.store.call_args[0][1]
        assert SEED_OFFER_PROTOCOL in stored_payload["protocols"]

    @pytest.mark.asyncio
    async def test_protocols_defaults_to_empty(self):
        mock_dht = AsyncMock()
        mock_dht.store = AsyncMock(return_value=True)

        discovery = MagicMock()
        discovery.get_dht.return_value = mock_dht
        reputation = MagicMock()
        reputation._records = {}

        gossip = AgentGossip(discovery, reputation)
        gossip.feed_path.parent.mkdir(parents=True, exist_ok=True)
        gossip.feed_path.touch()

        await gossip.broadcast_presence(
            peer_id="peer-2",
            status="online",
            capabilities=["compute"],
        )

        stored_payload = mock_dht.store.call_args[0][1]
        assert stored_payload["protocols"] == []


# ---------------------------------------------------------------------------
# AgentGossip.check_peer_protocol
# ---------------------------------------------------------------------------

class TestCheckPeerProtocol:
    def _make_gossip(self, presence: Any):
        mock_dht = AsyncMock()
        mock_dht.find_value = AsyncMock(return_value=presence)
        discovery = MagicMock()
        discovery.get_dht.return_value = mock_dht
        reputation = MagicMock()
        reputation._records = {}
        gossip = AgentGossip(discovery, reputation)
        return gossip

    @pytest.mark.asyncio
    async def test_supported_returns_true(self):
        gossip = self._make_gossip({"protocols": [SEED_OFFER_PROTOCOL, "consensus/v1"]})
        supported, observed = await gossip.check_peer_protocol("peer-x", SEED_OFFER_PROTOCOL)
        assert supported is True
        assert SEED_OFFER_PROTOCOL in observed

    @pytest.mark.asyncio
    async def test_protocol_missing_returns_false(self):
        gossip = self._make_gossip({"protocols": ["consensus/v1"]})
        supported, observed = await gossip.check_peer_protocol("peer-x", SEED_OFFER_PROTOCOL)
        assert supported is False
        assert observed == ["consensus/v1"]

    @pytest.mark.asyncio
    async def test_absent_presence_returns_false_empty(self):
        gossip = self._make_gossip(None)
        supported, observed = await gossip.check_peer_protocol("peer-x", SEED_OFFER_PROTOCOL)
        assert supported is False
        assert observed == []

    @pytest.mark.asyncio
    async def test_no_protocols_field_returns_false(self):
        gossip = self._make_gossip({"status": "online"})
        supported, observed = await gossip.check_peer_protocol("peer-x", SEED_OFFER_PROTOCOL)
        assert supported is False
        assert observed == []


# ---------------------------------------------------------------------------
# SensingAgent — compatibility observations
# ---------------------------------------------------------------------------

class TestCompatibilityObservations:
    def test_record_writes_to_capability_map(self, tmp_path):
        mesh_dir = tmp_path / "mesh"
        mesh_dir.mkdir(parents=True, exist_ok=True)
        agent = SensingAgent(mesh_dir=mesh_dir)

        agent.record_compatibility_observation(
            peer_id="peer-abc123456789",
            observed_protocols=["consensus/v1"],
            mismatched_protocol=SEED_OFFER_PROTOCOL,
        )

        raw = json.loads((mesh_dir / "capability_map.json").read_text())
        compat = raw["compatibility"]
        assert "peer-abc12345678" in compat
        entry = compat["peer-abc12345678"]
        assert SEED_OFFER_PROTOCOL in entry["mismatches"]
        assert "consensus/v1" in entry["protocols"]

    def test_record_merges_on_second_call(self, tmp_path):
        mesh_dir = tmp_path / "mesh"
        mesh_dir.mkdir(parents=True, exist_ok=True)
        agent = SensingAgent(mesh_dir=mesh_dir)

        agent.record_compatibility_observation("peer-abc123456789", ["consensus/v1"], SEED_OFFER_PROTOCOL)
        agent.record_compatibility_observation("peer-abc123456789", ["handshake/v1"], "consensus/v2")

        raw = json.loads((mesh_dir / "capability_map.json").read_text())
        entry = raw["compatibility"]["peer-abc12345678"]
        assert "consensus/v1" in entry["protocols"]
        assert "handshake/v1" in entry["protocols"]
        assert SEED_OFFER_PROTOCOL in entry["mismatches"]
        assert "consensus/v2" in entry["mismatches"]

    def test_scan_preserves_compatibility_section(self, tmp_path):
        mesh_dir = tmp_path / "mesh"
        (mesh_dir / "consensus").mkdir(parents=True, exist_ok=True)
        (mesh_dir / "failed").mkdir(parents=True, exist_ok=True)
        agent = SensingAgent(mesh_dir=mesh_dir)

        agent.record_compatibility_observation("peer-abc123456789", [], SEED_OFFER_PROTOCOL)
        agent.scan()  # should not wipe the compatibility section

        raw = json.loads((mesh_dir / "capability_map.json").read_text())
        assert "peer-abc12345678" in raw.get("compatibility", {})


# ---------------------------------------------------------------------------
# ReplicationAgent.evaluate_seed_offer
# ---------------------------------------------------------------------------

class TestEvaluateSeedOffer:
    def test_unknown_schema_version_rejected(self, tmp_path):
        agent = _make_replication_agent(tmp_path)
        env = _make_envelope(schema_version=99)
        accept, reason = agent.evaluate_seed_offer(env)
        assert not accept
        assert "schema_version_unsupported" in reason

    def test_low_reputation_rejected(self, tmp_path):
        agent = _make_replication_agent(
            tmp_path,
            reputation={"sender-peer": 0.1},
            threshold=0.5,
        )
        env = _make_envelope(sender_peer_id="sender-peer")
        accept, reason = agent.evaluate_seed_offer(env)
        assert not accept
        assert "reputation_too_low" in reason

    def test_no_capability_gap_rejected(self, tmp_path):
        agent = _make_replication_agent(
            tmp_path,
            reputation={"sender-peer": 0.9},
            threshold=0.5,
        )
        # Write a capability map with no pressure
        cap_map = {"version": 1, "pressure_regions": [], "evolutionary_pressure": False}
        mesh_dir = agent.mesh_dir
        cap_path = mesh_dir / "capability_map.json"
        cap_path.write_text(json.dumps(cap_map))

        env = _make_envelope(sender_peer_id="sender-peer")
        accept, reason = agent.evaluate_seed_offer(env)
        assert not accept
        assert "no_capability_gap_alignment" in reason

    def test_resource_throttled_rejected(self, tmp_path):
        mesh_dir = tmp_path / "mesh"
        mesh_dir.mkdir(parents=True, exist_ok=True)
        # Write pressure into capability map
        cap_map = {"version": 1, "pressure_regions": ["ab12"], "evolutionary_pressure": True}
        (mesh_dir / "capability_map.json").write_text(json.dumps(cap_map))
        # Write throttle signal
        (mesh_dir / "resource_state.json").write_text(json.dumps({"throttle": True}))
        # Write reputation
        (mesh_dir / "reputation.json").write_text(json.dumps({"scores": {"sender-peer": 0.9}}))

        agent = ReplicationAgent(
            mesh_dir=mesh_dir,
            vault_dir=tmp_path / "vault",
            data_dir=tmp_path / "agent-state",
            parent_reputation_threshold=0.5,
        )
        env = _make_envelope(sender_peer_id="sender-peer")
        accept, reason = agent.evaluate_seed_offer(env)
        assert not accept
        assert "resource_throttled" in reason

    def test_all_layers_pass_accepts(self, tmp_path):
        mesh_dir = tmp_path / "mesh"
        mesh_dir.mkdir(parents=True, exist_ok=True)
        cap_map = {"version": 1, "pressure_regions": ["ab12"], "evolutionary_pressure": True}
        (mesh_dir / "capability_map.json").write_text(json.dumps(cap_map))
        (mesh_dir / "reputation.json").write_text(json.dumps({"scores": {"sender-peer": 0.9}}))

        agent = ReplicationAgent(
            mesh_dir=mesh_dir,
            vault_dir=tmp_path / "vault",
            data_dir=tmp_path / "agent-state",
            parent_reputation_threshold=0.5,
        )
        env = _make_envelope(sender_peer_id="sender-peer")
        accept, reason = agent.evaluate_seed_offer(env)
        assert accept
        assert reason == "accepted"


# ---------------------------------------------------------------------------
# ReplicationAgent.propose_seed_transfer — protocol mismatch path
# ---------------------------------------------------------------------------

class TestProposeSeedTransfer:
    @pytest.mark.asyncio
    async def test_protocol_mismatch_records_observation_and_aborts(self, tmp_path):
        mock_gossip = AsyncMock(spec=AgentGossip)
        mock_gossip.check_peer_protocol = AsyncMock(
            return_value=(False, ["consensus/v1"])
        )

        mock_sensing = MagicMock()

        agent = _make_replication_agent(
            tmp_path, gossip=mock_gossip, sensing_agent=mock_sensing
        )

        # Create a real seed so the agent can find it.
        blueprint = _make_blueprint()
        seed_id = _derive_seed_id(blueprint)
        seed_manager = SeedManager(data_dir=tmp_path)
        seed_manager.commons.accumulate(200)
        seed_manager.issue(blueprint, compute_reserves=100)

        # Patch the agent's internal seed manager to share the same tmp dir.
        agent._seed_manager = seed_manager

        result = await agent.propose_seed_transfer(seed_id, target_peer_id="peer-other")

        assert result["sent"] is False
        assert result["reason"] == "protocol_mismatch"
        mock_sensing.record_compatibility_observation.assert_called_once_with(
            peer_id="peer-other",
            observed_protocols=["consensus/v1"],
            mismatched_protocol=SEED_OFFER_PROTOCOL,
        )

    @pytest.mark.asyncio
    async def test_no_gossip_layer_returns_error(self, tmp_path):
        agent = _make_replication_agent(tmp_path, gossip=None)
        result = await agent.propose_seed_transfer("any-seed-id")
        assert result["sent"] is False
        assert result["reason"] == "no_gossip_layer"


# ---------------------------------------------------------------------------
# ReplicationAgent.receive_seed_payload
# ---------------------------------------------------------------------------

class TestReceiveSeedPayload:
    @pytest.mark.asyncio
    async def test_unknown_schema_rejected(self, tmp_path):
        agent = _make_replication_agent(tmp_path)
        result = await agent.receive_seed_payload("s1", {"schemaVersion": 99})
        assert result["stored"] is False
        assert "schema_version_unsupported" in result["reason"]

    @pytest.mark.asyncio
    async def test_valid_payload_stored(self, tmp_path):
        agent = _make_replication_agent(tmp_path)
        blueprint = _make_blueprint()
        seed_id = _derive_seed_id(blueprint)

        now = time.time()
        seed_dict = {
            "seedId": seed_id,
            "blueprint": blueprint.to_dict(),
            "computeReserves": 50,
            "germinationConditions": {"minPeerDensity": 3, "minDemandSignals": 5, "availableComputeUnits": 50},
            "issuedAt": now,
            "expiresAt": now + 86400,
            "status": "dormant",
            "schemaVersion": SEED_OFFER_SCHEMA_VERSION,
            "senderPeerId": "remote-peer",
        }
        result = await agent.receive_seed_payload(seed_id, seed_dict)
        assert result["stored"] is True

        seed_path = agent._seed_manager._seeds_dir / f"{seed_id}.json"
        assert seed_path.exists()
        stored = json.loads(seed_path.read_text())
        assert stored["provenance"]["receivedFrom"] == "remote-peer"
        assert stored["provenance"]["source"] == "p2p_offer"


# ---------------------------------------------------------------------------
# SeedManager.receive_external
# ---------------------------------------------------------------------------

class TestReceiveExternal:
    def test_stores_with_provenance(self, tmp_path):
        sm = SeedManager(data_dir=tmp_path)
        blueprint = _make_blueprint()
        seed_id = _derive_seed_id(blueprint)
        now = time.time()

        payload = {
            "seedId": seed_id,
            "blueprint": blueprint.to_dict(),
            "computeReserves": 50,
            "germinationConditions": {"minPeerDensity": 3, "minDemandSignals": 5, "availableComputeUnits": 50},
            "issuedAt": now,
            "expiresAt": now + 86400,
            "status": "dormant",
            "senderPeerId": "remote-sender",
        }

        assert sm.receive_external(seed_id, payload) is True
        seed_path = sm._seeds_dir / f"{seed_id}.json"
        raw = json.loads(seed_path.read_text())
        assert raw["provenance"]["receivedFrom"] == "remote-sender"
        assert raw["provenance"]["source"] == "p2p_offer"

    def test_malformed_payload_returns_false(self, tmp_path):
        sm = SeedManager(data_dir=tmp_path)
        assert sm.receive_external("bad-seed", {"not": "a seed"}) is False

    def test_load_seed_alias(self, tmp_path):
        sm = SeedManager(data_dir=tmp_path)
        blueprint = _make_blueprint()
        seed_id = _derive_seed_id(blueprint)
        sm.commons.accumulate(200)
        seed = sm.issue(blueprint, compute_reserves=50)
        assert seed is not None
        # Both load() and load_seed() should return the same object.
        assert sm.load_seed(seed_id) is not None
        assert sm.load(seed_id).seedId == sm.load_seed(seed_id).seedId
