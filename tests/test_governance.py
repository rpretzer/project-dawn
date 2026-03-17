"""
Tests for the Governance Protocol (Phase 2, item 5).

Covers:
- submit_proposal: reputation gate, deduplication
- cast_vote: valid vote, vote on non-pending proposal, one vote per voter
- tally: acceptance, rejection, expiry, no-decision when votes inconclusive
- get_accepted_rules: ruleset populated after acceptance
- _write_atomic: fsync + rename pattern
- Proposal / Vote round-trip
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from agents.governance import (
    DEFAULT_ACCEPTANCE_THRESHOLD,
    GovernanceManager,
    Proposal,
    Vote,
    _derive_proposal_id,
    _write_atomic,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _manager(tmp_path: Path, **kwargs) -> GovernanceManager:
    return GovernanceManager(data_dir=tmp_path, **kwargs)


# ---------------------------------------------------------------------------
# _write_atomic
# ---------------------------------------------------------------------------

def test_write_atomic_creates_file(tmp_path):
    path = tmp_path / "test.json"
    _write_atomic(path, {"a": 1})
    assert json.loads(path.read_text()) == {"a": 1}


def test_write_atomic_no_tmp_leftover(tmp_path):
    path = tmp_path / "data.json"
    _write_atomic(path, {"x": 2})
    assert not path.with_suffix(".json.tmp").exists()


# ---------------------------------------------------------------------------
# _derive_proposal_id
# ---------------------------------------------------------------------------

def test_derive_proposal_id_deterministic():
    pid1 = _derive_proposal_id("proposer", "key", "value")
    pid2 = _derive_proposal_id("proposer", "key", "value")
    assert pid1 == pid2


def test_derive_proposal_id_differs_by_value():
    p1 = _derive_proposal_id("proposer", "key", "v1")
    p2 = _derive_proposal_id("proposer", "key", "v2")
    assert p1 != p2


# ---------------------------------------------------------------------------
# Proposal schema
# ---------------------------------------------------------------------------

def test_proposal_round_trip():
    now = time.time()
    p = Proposal(
        proposalId="abc",
        proposerId="peer-x",
        ruleKey="max_peers",
        proposedValue=50,
        rationale="scale up",
        submittedAt=now,
        expiresAt=now + 3600,
    )
    assert Proposal.from_dict(p.to_dict()).proposalId == "abc"
    assert Proposal.from_dict(p.to_dict()).ruleKey == "max_peers"


def test_proposal_is_expired_true():
    now = time.time()
    p = Proposal("id", "pid", "k", "v", "", now - 2, now - 1)
    assert p.is_expired()


def test_proposal_is_expired_false():
    now = time.time()
    p = Proposal("id", "pid", "k", "v", "", now, now + 3600)
    assert not p.is_expired()


# ---------------------------------------------------------------------------
# Vote schema
# ---------------------------------------------------------------------------

def test_vote_round_trip():
    v = Vote(
        proposalId="prop-1", voterId="voter-1", voterReputation=0.8,
        approve=True, votedAt=time.time(),
    )
    assert Vote.from_dict(v.to_dict()).voterId == "voter-1"
    assert Vote.from_dict(v.to_dict()).approve is True


# ---------------------------------------------------------------------------
# submit_proposal
# ---------------------------------------------------------------------------

def test_submit_proposal_succeeds_above_threshold(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.5)
    p = mgr.submit_proposal("peer-a", 0.8, "max_peers", 100)
    assert p is not None
    assert p.status == "pending"


def test_submit_proposal_fails_below_threshold(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.7)
    p = mgr.submit_proposal("peer-a", 0.3, "max_peers", 100)
    assert p is None


def test_submit_proposal_deduplicates(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1)
    p1 = mgr.submit_proposal("peer-a", 0.9, "key", "value")
    p2 = mgr.submit_proposal("peer-a", 0.9, "key", "value")
    assert p1.proposalId == p2.proposalId
    # Only one proposal should exist.
    assert len(mgr.list_proposals()) == 1


def test_submit_proposal_persists(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1)
    p = mgr.submit_proposal("peer-a", 0.9, "rule", 42)
    mgr2 = GovernanceManager(data_dir=tmp_path)
    loaded = mgr2.load_proposal(p.proposalId)
    assert loaded is not None
    assert loaded.ruleKey == "rule"


# ---------------------------------------------------------------------------
# cast_vote
# ---------------------------------------------------------------------------

def test_cast_vote_records_vote(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1)
    p = mgr.submit_proposal("peer-a", 0.9, "key", "val")
    ok = mgr.cast_vote(p.proposalId, "voter-x", voter_reputation=0.8, approve=True)
    assert ok is True
    votes = mgr.get_votes(p.proposalId)
    assert len(votes) == 1
    assert votes[0].voterId == "voter-x"
    assert votes[0].approve is True


def test_cast_vote_on_unknown_proposal(tmp_path):
    mgr = _manager(tmp_path)
    ok = mgr.cast_vote("nonexistent", "voter", voter_reputation=0.5, approve=True)
    assert ok is False


def test_cast_vote_on_accepted_proposal_rejected(tmp_path):
    """Cannot vote on a decided proposal."""
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1, acceptance_threshold=0.1)
    p = mgr.submit_proposal("peer-a", 0.9, "key", "val")
    mgr.cast_vote(p.proposalId, "voter-1", 0.9, approve=True)
    mgr.tally()  # should accept

    reloaded = mgr.load_proposal(p.proposalId)
    assert reloaded.status == "accepted"

    ok = mgr.cast_vote(p.proposalId, "voter-2", 0.5, approve=True)
    assert ok is False


def test_cast_vote_one_per_voter_last_wins(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1)
    p = mgr.submit_proposal("peer-a", 0.9, "key", "val")
    mgr.cast_vote(p.proposalId, "voter-x", 0.8, approve=True)
    mgr.cast_vote(p.proposalId, "voter-x", 0.8, approve=False)  # change mind
    votes = mgr.get_votes(p.proposalId)
    assert len(votes) == 1
    assert votes[0].approve is False


def test_cast_vote_multiple_voters(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1)
    p = mgr.submit_proposal("peer-a", 0.9, "key", "val")
    mgr.cast_vote(p.proposalId, "voter-1", 0.8, approve=True)
    mgr.cast_vote(p.proposalId, "voter-2", 0.6, approve=False)
    votes = mgr.get_votes(p.proposalId)
    assert len(votes) == 2


# ---------------------------------------------------------------------------
# tally
# ---------------------------------------------------------------------------

def test_tally_accepts_when_above_threshold(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1, acceptance_threshold=0.6)
    p = mgr.submit_proposal("peer-a", 0.9, "key", "new_val")
    # Two high-rep approvals, one low-rep rejection.
    mgr.cast_vote(p.proposalId, "v1", voter_reputation=0.9, approve=True)
    mgr.cast_vote(p.proposalId, "v2", voter_reputation=0.8, approve=True)
    mgr.cast_vote(p.proposalId, "v3", voter_reputation=0.1, approve=False)

    result = mgr.tally()
    assert p.proposalId in result["accepted"]
    assert mgr.load_proposal(p.proposalId).status == "accepted"


def test_tally_rejects_when_rejection_exceeds_threshold(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1, acceptance_threshold=0.66)
    p = mgr.submit_proposal("peer-a", 0.9, "key", "val")
    # Overwhelming rejection.
    mgr.cast_vote(p.proposalId, "v1", voter_reputation=0.9, approve=False)
    mgr.cast_vote(p.proposalId, "v2", voter_reputation=0.8, approve=False)
    mgr.cast_vote(p.proposalId, "v3", voter_reputation=0.1, approve=True)

    result = mgr.tally()
    assert p.proposalId in result["rejected"]
    assert mgr.load_proposal(p.proposalId).status == "rejected"


def test_tally_leaves_inconclusive_as_pending(tmp_path):
    """Balanced vote: neither threshold met."""
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1, acceptance_threshold=0.66)
    p = mgr.submit_proposal("peer-a", 0.9, "key", "val")
    # 50/50 weighted split — neither accepted nor rejected.
    mgr.cast_vote(p.proposalId, "v1", voter_reputation=0.5, approve=True)
    mgr.cast_vote(p.proposalId, "v2", voter_reputation=0.5, approve=False)

    result = mgr.tally()
    assert p.proposalId not in result["accepted"]
    assert p.proposalId not in result["rejected"]
    assert p.proposalId not in result["expired"]
    assert mgr.load_proposal(p.proposalId).status == "pending"


def test_tally_expires_old_proposal(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1)
    p = mgr.submit_proposal("peer-a", 0.9, "key", "val")
    # Force expiry.
    proposals_path = tmp_path / "mesh" / "governance" / "proposals.json"
    raw = json.loads(proposals_path.read_text())
    for prop in raw["proposals"]:
        if prop["proposalId"] == p.proposalId:
            prop["expiresAt"] = time.time() - 1
    _write_atomic(proposals_path, raw)

    result = mgr.tally()
    assert p.proposalId in result["expired"]
    assert mgr.load_proposal(p.proposalId).status == "expired"


def test_tally_no_votes_leaves_pending(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1)
    p = mgr.submit_proposal("peer-a", 0.9, "key", "val")
    result = mgr.tally()
    assert p.proposalId not in result["accepted"]
    assert mgr.load_proposal(p.proposalId).status == "pending"


# ---------------------------------------------------------------------------
# get_accepted_rules
# ---------------------------------------------------------------------------

def test_get_accepted_rules_empty_before_any_acceptance(tmp_path):
    mgr = _manager(tmp_path)
    assert mgr.get_accepted_rules() == {}


def test_get_accepted_rules_populated_after_acceptance(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1, acceptance_threshold=0.1)
    p = mgr.submit_proposal("peer-a", 0.9, "max_peers", 100)
    mgr.cast_vote(p.proposalId, "v1", voter_reputation=0.9, approve=True)
    mgr.tally()

    rules = mgr.get_accepted_rules()
    assert rules.get("max_peers") == 100


def test_multiple_accepted_rules_accumulate(tmp_path):
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1, acceptance_threshold=0.1)

    for key, value in [("rule_a", 10), ("rule_b", "enabled"), ("rule_c", True)]:
        p = mgr.submit_proposal("peer-a", 0.9, key, value)
        mgr.cast_vote(p.proposalId, "v1", voter_reputation=0.9, approve=True)
        mgr.tally()

    rules = mgr.get_accepted_rules()
    assert rules["rule_a"] == 10
    assert rules["rule_b"] == "enabled"
    assert rules["rule_c"] is True


def test_accepted_rules_persist_across_instances(tmp_path):
    mgr1 = _manager(tmp_path, proposal_reputation_threshold=0.1, acceptance_threshold=0.1)
    p = mgr1.submit_proposal("peer-a", 0.9, "persisted_rule", 42)
    mgr1.cast_vote(p.proposalId, "v1", voter_reputation=0.9, approve=True)
    mgr1.tally()

    mgr2 = GovernanceManager(data_dir=tmp_path)
    rules = mgr2.get_accepted_rules()
    assert rules.get("persisted_rule") == 42


# ---------------------------------------------------------------------------
# Weighted tally correctness
# ---------------------------------------------------------------------------

def test_weighted_approval_reflects_voter_reputation(tmp_path):
    """
    Weighted approval = sum(rep of approvers) / sum(all reps).
    With a 0.9-rep approver and 0.1-rep rejector: approval = 0.9.
    """
    mgr = _manager(tmp_path, proposal_reputation_threshold=0.1, acceptance_threshold=0.8)
    p = mgr.submit_proposal("peer-a", 0.9, "key", "val")
    mgr.cast_vote(p.proposalId, "v1", voter_reputation=0.9, approve=True)
    mgr.cast_vote(p.proposalId, "v2", voter_reputation=0.1, approve=False)

    mgr.tally()
    loaded = mgr.load_proposal(p.proposalId)
    assert loaded.weightedApproval == pytest.approx(0.9, abs=0.01)
    assert loaded.status == "accepted"  # 0.9 >= threshold 0.8
