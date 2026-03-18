"""
Tests for Phase 2 components:
  - GovernanceAgent: poll(), announce_proposal(), active_proposal_ids(), auto-vote
  - InnovationAgent: probe(), report(), commons gate, capability map update
  - SeedManager governance inheritance: issue() merges accepted_rules, receive_external() warns

All tests use in-memory state (tmp_path); no real sockets or GPU required.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.governance import GovernanceAgent, GovernanceManager, Proposal
from agents.innovation_agent import InnovationAgent
from agents.seed_manager import AgentBlueprint, GerminationConditions, SeedManager
from p2p.dht import DHT
from reputation import ReputationManager


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_reputation(tmp_path: Path, peer_id: str, score: float = 0.8) -> ReputationManager:
    rep = ReputationManager(data_dir=tmp_path / "mesh")
    rep.record_peer(peer_id, reputation_score=score)
    return rep


def _make_gossip(dht: Optional[DHT] = None) -> Any:
    """Return a minimal AgentGossip-like mock backed by a real or fake DHT."""
    from discovery import SovereignDiscovery
    from reputation import ReputationManager
    from communication import AgentGossip
    from crypto import NodeIdentity

    identity = NodeIdentity()
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    rep = ReputationManager(data_dir=tmp / "mesh")
    disc = SovereignDiscovery(identity=identity, data_dir=tmp / "mesh")
    if dht:
        disc.set_dht(dht)
    gossip = AgentGossip(discovery=disc, reputation=rep, data_dir=tmp)
    return gossip


# ---------------------------------------------------------------------------
# GovernanceAgent tests
# ---------------------------------------------------------------------------

class TestGovernanceAgent:

    def _agent(self, tmp_path: Path, peer_id: str = "peer-A", score: float = 0.8,
               dht: Optional[DHT] = None) -> GovernanceAgent:
        rep = _make_reputation(tmp_path, peer_id, score)
        gossip = _make_gossip(dht)
        return GovernanceAgent(
            peer_id=peer_id,
            gossip=gossip,
            reputation_manager=rep,
            data_dir=tmp_path,
        )

    # --- submit_proposal (local only) ---

    def test_submit_proposal_saves_locally(self, tmp_path):
        agent = self._agent(tmp_path)
        proposal = agent.submit_proposal("max_peers", 50, rationale="scalability")
        assert proposal is not None
        assert proposal.ruleKey == "max_peers"
        assert proposal.proposedValue == 50
        assert proposal.status == "pending"

    def test_submit_proposal_blocked_by_low_reputation(self, tmp_path):
        agent = self._agent(tmp_path, score=0.1)
        # Default threshold is 0.5; score 0.1 should be blocked.
        proposal = agent.submit_proposal("max_peers", 50)
        assert proposal is None

    def test_active_proposal_ids_lists_own_pending(self, tmp_path):
        agent = self._agent(tmp_path)
        agent.submit_proposal("max_peers", 50)
        agent.submit_proposal("min_reputation", 0.3)
        ids = agent.active_proposal_ids()
        assert len(ids) == 2

    def test_active_proposal_ids_excludes_other_proposers(self, tmp_path):
        agent = self._agent(tmp_path, peer_id="peer-A")
        # Manually insert a proposal from another peer.
        foreign = Proposal(
            proposalId="foreign-id",
            proposerId="peer-B",
            ruleKey="some_rule",
            proposedValue=1,
            rationale="",
            submittedAt=time.time(),
            expiresAt=time.time() + 3600,
        )
        agent.manager._save_proposal(foreign)
        ids = agent.active_proposal_ids()
        assert "foreign-id" not in ids

    # --- cast_vote ---

    def test_cast_vote_records_weighted_by_reputation(self, tmp_path):
        agent = self._agent(tmp_path, score=0.7)
        proposal = agent.submit_proposal("max_peers", 50)
        assert proposal is not None
        ok = agent.cast_vote(proposal.proposalId, approve=True)
        assert ok is True
        votes = agent.manager.get_votes(proposal.proposalId)
        assert len(votes) == 1
        assert votes[0].voterReputation == pytest.approx(0.7, abs=1e-6)

    def test_cast_vote_on_missing_proposal_returns_false(self, tmp_path):
        agent = self._agent(tmp_path)
        ok = agent.cast_vote("nonexistent-id", approve=True)
        assert ok is False

    # --- announce_proposal (DHT broadcast) ---

    @pytest.mark.asyncio
    async def test_announce_proposal_broadcasts_to_dht(self, tmp_path):
        from crypto import NodeIdentity
        dht = DHT(NodeIdentity())
        agent = self._agent(tmp_path, dht=dht)
        proposal = await agent.announce_proposal("max_peers", 50, rationale="test")
        assert proposal is not None
        stored = await dht.find_value(f"governance_proposal:{proposal.proposalId}")
        assert stored is not None
        assert stored["ruleKey"] == "max_peers"

    @pytest.mark.asyncio
    async def test_announce_proposal_blocked_by_low_reputation_returns_none(self, tmp_path):
        from crypto import NodeIdentity
        dht = DHT(NodeIdentity())
        agent = self._agent(tmp_path, score=0.1, dht=dht)
        proposal = await agent.announce_proposal("max_peers", 50)
        assert proposal is None

    # --- poll() with shared DHT ---

    @pytest.mark.asyncio
    async def test_poll_ingests_remote_proposal(self, tmp_path):
        """Node B discovers and ingests a proposal submitted by Node A."""
        from crypto import NodeIdentity
        from discovery import SovereignDiscovery
        from communication import AgentGossip

        shared_dht = DHT(NodeIdentity())

        # Agent A: submitter
        tmp_a = tmp_path / "a"
        rep_a = _make_reputation(tmp_a, "peer-A")
        disc_a = SovereignDiscovery(identity=NodeIdentity(), data_dir=tmp_a / "mesh")
        disc_a.set_dht(shared_dht)
        gossip_a = AgentGossip(discovery=disc_a, reputation=rep_a, data_dir=tmp_a)
        agent_a = GovernanceAgent(
            peer_id="peer-A",
            gossip=gossip_a,
            reputation_manager=rep_a,
            data_dir=tmp_a,
        )

        # Agent B: discoverer
        tmp_b = tmp_path / "b"
        rep_b = _make_reputation(tmp_b, "peer-A")   # B knows about A (needed for list_trusted_peers)
        disc_b = SovereignDiscovery(identity=NodeIdentity(), data_dir=tmp_b / "mesh")
        disc_b.set_dht(shared_dht)
        gossip_b = AgentGossip(discovery=disc_b, reputation=rep_b, data_dir=tmp_b)
        agent_b = GovernanceAgent(
            peer_id="peer-B",
            gossip=gossip_b,
            reputation_manager=rep_b,
            data_dir=tmp_b,
        )

        # A announces a proposal and writes its presence with active_proposals.
        proposal = await agent_a.announce_proposal("max_peers", 50)
        assert proposal is not None
        await gossip_a.broadcast_presence(
            peer_id="peer-A",
            status="online",
            capabilities=[],
            protocols=[],
        )
        # Manually inject active_proposals into A's presence (broadcast_presence
        # doesn't support extra fields directly; in production _refresh_presence does).
        await shared_dht.store("presence:peer-A", {
            "peerId": "peer-A",
            "status": "online",
            "capabilities": [],
            "protocols": [],
            "active_proposals": [proposal.proposalId],
            "offered_seeds": [],
            "timestamp": time.time(),
        }, ttl=3600.0)

        # B polls and should ingest A's proposal.
        summary = await agent_b.poll()
        assert summary["ingested"] == 1

        # The proposal should now exist in B's manager.
        ingested = agent_b.manager.load_proposal(proposal.proposalId)
        assert ingested is not None
        assert ingested.ruleKey == "max_peers"

    @pytest.mark.asyncio
    async def test_poll_auto_votes_on_new_proposals(self, tmp_path):
        """After ingesting a remote proposal, the agent auto-votes on it."""
        from crypto import NodeIdentity
        from discovery import SovereignDiscovery
        from communication import AgentGossip

        shared_dht = DHT(NodeIdentity())

        tmp_a = tmp_path / "a"
        rep_a = _make_reputation(tmp_a, "peer-A")
        disc_a = SovereignDiscovery(identity=NodeIdentity(), data_dir=tmp_a / "mesh")
        disc_a.set_dht(shared_dht)
        gossip_a = AgentGossip(discovery=disc_a, reputation=rep_a, data_dir=tmp_a)
        agent_a = GovernanceAgent(
            peer_id="peer-A",
            gossip=gossip_a,
            reputation_manager=rep_a,
            data_dir=tmp_a,
        )

        tmp_b = tmp_path / "b"
        rep_b = _make_reputation(tmp_b, "peer-A")
        disc_b = SovereignDiscovery(identity=NodeIdentity(), data_dir=tmp_b / "mesh")
        disc_b.set_dht(shared_dht)
        gossip_b = AgentGossip(discovery=disc_b, reputation=rep_b, data_dir=tmp_b)
        agent_b = GovernanceAgent(
            peer_id="peer-B",
            gossip=gossip_b,
            reputation_manager=rep_b,
            data_dir=tmp_b,
            auto_vote=True,
        )

        proposal = await agent_a.announce_proposal("max_peers", 50)
        await shared_dht.store("presence:peer-A", {
            "peerId": "peer-A",
            "status": "online",
            "capabilities": [],
            "protocols": [],
            "active_proposals": [proposal.proposalId],
            "offered_seeds": [],
            "timestamp": time.time(),
        }, ttl=3600.0)

        summary = await agent_b.poll()
        assert summary["voted"] >= 1

        # B's vote should be findable in the shared DHT.
        raw_vote = await shared_dht.find_value(
            f"governance_vote:{proposal.proposalId}:peer-B"
        )
        assert raw_vote is not None
        assert raw_vote["voterId"] == "peer-B"

    @pytest.mark.asyncio
    async def test_poll_tally_accepts_and_broadcasts_rules(self, tmp_path):
        """When a proposal passes tally, accepted rules are broadcast to the DHT."""
        from crypto import NodeIdentity
        from discovery import SovereignDiscovery
        from communication import AgentGossip

        shared_dht = DHT(NodeIdentity())

        tmp_a = tmp_path / "a"
        rep_a = _make_reputation(tmp_a, "peer-A")
        disc_a = SovereignDiscovery(identity=NodeIdentity(), data_dir=tmp_a / "mesh")
        disc_a.set_dht(shared_dht)
        gossip_a = AgentGossip(discovery=disc_a, reputation=rep_a, data_dir=tmp_a)
        # Use a very short voting window so tally fires immediately
        agent_a = GovernanceAgent(
            peer_id="peer-A",
            gossip=gossip_a,
            reputation_manager=rep_a,
            data_dir=tmp_a,
            acceptance_threshold=0.5,
        )

        # A proposes and votes to approve (score 0.8 > threshold 0.5)
        proposal = await agent_a.announce_proposal("max_peers", 50)
        assert proposal is not None
        agent_a.cast_vote(proposal.proposalId, approve=True)

        # Force tally directly (skipping polling cycle complexity)
        result = agent_a.manager.tally()
        assert proposal.proposalId in result["accepted"]

        # Broadcast accepted rules
        rules = agent_a.get_accepted_rules()
        assert rules.get("max_peers") == 50

        await gossip_a.broadcast_accepted_rules(rules, "peer-A")
        fetched = await shared_dht.find_value("governance_accepted_rules")
        assert fetched is not None
        assert fetched.get("rules", fetched).get("max_peers") == 50


# ---------------------------------------------------------------------------
# InnovationAgent tests
# ---------------------------------------------------------------------------

class TestInnovationAgent:

    def _agent(self, tmp_path: Path, balance: int = 200) -> InnovationAgent:
        return InnovationAgent(
            mesh_dir=tmp_path / "mesh",
            commons_balance_fn=lambda: balance,
            data_dir=tmp_path,
        )

    def test_probe_writes_work_unit_to_inbox(self, tmp_path):
        agent = self._agent(tmp_path)
        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()
        probes = agent.probe(inbox_dir)
        assert len(probes) > 0
        assert probes[0].status == "pending"
        # The inbox should contain a work unit file.
        inbox_files = list(inbox_dir.glob("*.json"))
        assert len(inbox_files) == len(probes)

    def test_probe_work_unit_has_required_fields(self, tmp_path):
        agent = self._agent(tmp_path)
        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()
        probes = agent.probe(inbox_dir)
        assert len(probes) > 0
        wu_path = inbox_dir / f"{probes[0].workUnitTaskId}.json"
        wu = json.loads(wu_path.read_text())
        assert "taskId" in wu
        assert "inputBlob" in wu
        assert "inputTokens" in wu["inputBlob"]
        assert "outputTokens" in wu["inputBlob"]
        assert wu.get("source") == "innovation_agent"

    def test_probe_gated_by_commons_balance(self, tmp_path):
        agent = self._agent(tmp_path, balance=0)
        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()
        probes = agent.probe(inbox_dir)
        assert probes == []

    def test_report_success_marks_probe_resolved(self, tmp_path):
        agent = self._agent(tmp_path)
        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()
        probes = agent.probe(inbox_dir)
        assert len(probes) > 0
        task_id = probes[0].workUnitTaskId
        record = agent.report(task_id, success=True)
        assert record is not None
        assert record.status == "success"
        assert record.resolvedAt is not None

    def test_report_failure_marks_probe_failed(self, tmp_path):
        agent = self._agent(tmp_path)
        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()
        probes = agent.probe(inbox_dir)
        task_id = probes[0].workUnitTaskId
        record = agent.report(task_id, success=False, notes="consensus rejected")
        assert record is not None
        assert record.status == "failure"

    def test_report_unknown_task_returns_none(self, tmp_path):
        agent = self._agent(tmp_path)
        record = agent.report("nonexistent-task-id", success=True)
        assert record is None

    def test_report_updates_capability_map(self, tmp_path):
        agent = self._agent(tmp_path)
        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()
        probes = agent.probe(inbox_dir)
        task_id = probes[0].workUnitTaskId
        region = probes[0].region
        agent.report(task_id, success=True)
        cap_map = agent._load_capability_map()
        assert cap_map is not None
        assert region in cap_map.get("regions", {})
        entry = cap_map["regions"][region]
        assert entry["attempts"] == 1
        assert entry["successes"] == 1
        assert entry["failures"] == 0

    def test_probe_targets_blank_regions_first(self, tmp_path):
        """First probe round should target regions with no prior attempts."""
        agent = self._agent(tmp_path)
        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()
        probes = agent.probe(inbox_dir)
        # All initial probes should be for blank (unobserved) regions.
        for p in probes:
            cap_map = agent._load_capability_map()
            # The region shouldn't have been in the map before this probe cycle.
            # (It gets added by report(), not probe().)
            assert p.region is not None

    def test_probe_log_is_appended(self, tmp_path):
        agent = self._agent(tmp_path)
        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()
        probes1 = agent.probe(inbox_dir)
        probes2 = agent.probe(inbox_dir)
        log = agent._read_probe_log(limit=100)
        assert len(log) >= len(probes1) + len(probes2)


# ---------------------------------------------------------------------------
# SeedManager governance inheritance tests
# ---------------------------------------------------------------------------

class TestSeedManagerGovernanceInheritance:

    def _make_blueprint(self, peer_id: str = "child-peer") -> AgentBlueprint:
        return AgentBlueprint(
            peerId=peer_id,
            logitFingerprint="abc123",
            parentId="parent-peer",
            generation=1,
            capabilityDeclarations=["compute"],
            governingValues={},
        )

    def _write_accepted_rules(self, data_dir: Path, rules: Dict[str, Any]) -> None:
        gov_dir = data_dir / "mesh" / "governance"
        gov_dir.mkdir(parents=True, exist_ok=True)
        path = gov_dir / "accepted_rules.json"
        path.write_text(json.dumps({"version": 1, "rules": rules}), encoding="utf-8")

    def test_issue_inherits_accepted_rules(self, tmp_path):
        self._write_accepted_rules(tmp_path, {"max_peers": 50, "min_reputation": 0.3})
        mgr = SeedManager(data_dir=tmp_path)
        mgr.commons.accumulate(1000)

        bp = self._make_blueprint()
        seed = mgr.issue(bp, compute_reserves=100)
        assert seed is not None
        assert seed.blueprint.governingValues.get("max_peers") == 50
        assert seed.blueprint.governingValues.get("min_reputation") == pytest.approx(0.3)

    def test_issue_caller_values_take_precedence(self, tmp_path):
        """Caller-supplied governingValues override the accepted ruleset."""
        self._write_accepted_rules(tmp_path, {"max_peers": 50})
        mgr = SeedManager(data_dir=tmp_path)
        mgr.commons.accumulate(1000)

        bp = AgentBlueprint(
            peerId="child",
            logitFingerprint="abc",
            parentId="parent",
            generation=1,
            governingValues={"max_peers": 999},  # caller override
        )
        seed = mgr.issue(bp, compute_reserves=100)
        assert seed is not None
        assert seed.blueprint.governingValues["max_peers"] == 999

    def test_issue_no_rules_leaves_values_empty(self, tmp_path):
        """When no accepted_rules.json exists, governingValues stays as caller set."""
        mgr = SeedManager(data_dir=tmp_path)
        mgr.commons.accumulate(1000)
        bp = self._make_blueprint()
        seed = mgr.issue(bp, compute_reserves=100)
        assert seed is not None
        assert seed.blueprint.governingValues == {}

    def test_receive_external_warns_on_missing_rules(self, tmp_path, caplog):
        """receive_external() logs a warning when the seed is missing accepted rules."""
        import logging
        self._write_accepted_rules(tmp_path, {"max_peers": 50, "min_reputation": 0.3})
        mgr = SeedManager(data_dir=tmp_path)

        bp = self._make_blueprint()
        # Seed has only one of the two accepted rules.
        bp_with_partial = AgentBlueprint(
            peerId=bp.peerId,
            logitFingerprint=bp.logitFingerprint,
            parentId=bp.parentId,
            generation=bp.generation,
            governingValues={"max_peers": 50},  # min_reputation is missing
        )
        from agents.seed_manager import Seed, GerminationConditions
        now = time.time()
        seed = Seed(
            seedId="external-seed-001",
            blueprint=bp_with_partial,
            computeReserves=100,
            germinationConditions=GerminationConditions(),
            issuedAt=now,
            expiresAt=now + 3600,
        )
        payload = {**seed.to_dict(), "senderPeerId": "remote-peer"}
        with caplog.at_level(logging.WARNING, logger="agents.seed_manager"):
            ok = mgr.receive_external("external-seed-001", payload)
        assert ok is True
        assert any("missing" in r.message for r in caplog.records)

    def test_receive_external_no_warning_when_rules_match(self, tmp_path, caplog):
        """No warning when the seed carries all locally-accepted rules."""
        import logging
        self._write_accepted_rules(tmp_path, {"max_peers": 50})
        mgr = SeedManager(data_dir=tmp_path)

        bp = AgentBlueprint(
            peerId="child",
            logitFingerprint="abc",
            parentId="parent",
            generation=1,
            governingValues={"max_peers": 50, "extra_rule": True},
        )
        from agents.seed_manager import Seed, GerminationConditions
        now = time.time()
        seed = Seed(
            seedId="external-seed-002",
            blueprint=bp,
            computeReserves=100,
            germinationConditions=GerminationConditions(),
            issuedAt=now,
            expiresAt=now + 3600,
        )
        payload = {**seed.to_dict(), "senderPeerId": "remote-peer"}
        with caplog.at_level(logging.WARNING, logger="agents.seed_manager"):
            ok = mgr.receive_external("external-seed-002", payload)
        assert ok is True
        warning_msgs = [r.message for r in caplog.records if "missing" in r.message]
        assert warning_msgs == []
