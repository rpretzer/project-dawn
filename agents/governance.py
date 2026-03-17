"""
Governance Protocol — Phase 2, item 5.

Governance is the *conserved genome* of the network: the set of rules that
constrain all agents regardless of individual variation.  Individual agents
vary in capability and reputation; the governing constraints are inherited
unchanged and can only be modified by collective decision.

Mechanism:
  1. Any agent with reputation ≥ proposal_threshold can submit a proposal.
  2. Proposals are broadcast to the mesh as DHT entries.
  3. Peers vote; each vote is weighted by the voter's current reputation score.
  4. When weighted approval ≥ acceptance_threshold the rule is accepted.
  5. Accepted rules are written to data/mesh/governance/accepted_rules.json and
     propagated to all agents via the agent feed.
  6. Future seeds inherit all accepted rules.

On-disk layout (under a configurable root, default: data/):
  mesh/governance/
    proposals.json     — active proposals (pending + recently decided)
    accepted_rules.json — the current governing ruleset (seeds inherit this)
    votes/
      {proposal_id}.json — all votes cast for a proposal

All writes use the atomic pattern (tmp → fsync → rename).
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

GOVERNANCE_SCHEMA_VERSION = 1

# ---------- tunables --------------------------------------------------------
DEFAULT_PROPOSAL_REPUTATION_THRESHOLD = 0.5  # min rep to submit a proposal
DEFAULT_ACCEPTANCE_THRESHOLD = 0.66          # weighted-approval fraction
DEFAULT_VOTING_WINDOW_SECONDS = 7 * 24 * 3600  # 1 week
# ---------------------------------------------------------------------------


def _write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    """fsync-safe JSON write: tmp → fsync → rename."""
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _derive_proposal_id(proposer_id: str, rule_key: str, proposed_value: Any) -> str:
    raw = f"{proposer_id}:{rule_key}:{json.dumps(proposed_value, sort_keys=True)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

@dataclass
class Proposal:
    proposalId: str
    proposerId: str
    ruleKey: str
    proposedValue: Any
    rationale: str
    submittedAt: float
    expiresAt: float
    status: str = "pending"   # pending | accepted | rejected | expired
    weightedApproval: float = 0.0
    weightedRejection: float = 0.0
    decidedAt: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["version"] = GOVERNANCE_SCHEMA_VERSION
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Proposal":
        return cls(
            proposalId=d["proposalId"],
            proposerId=d["proposerId"],
            ruleKey=d["ruleKey"],
            proposedValue=d["proposedValue"],
            rationale=d.get("rationale", ""),
            submittedAt=d["submittedAt"],
            expiresAt=d["expiresAt"],
            status=d.get("status", "pending"),
            weightedApproval=d.get("weightedApproval", 0.0),
            weightedRejection=d.get("weightedRejection", 0.0),
            decidedAt=d.get("decidedAt"),
        )

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now or time.time()) >= self.expiresAt


@dataclass
class Vote:
    proposalId: str
    voterId: str
    voterReputation: float
    approve: bool   # True = approve, False = reject
    votedAt: float
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Vote":
        return cls(
            proposalId=d["proposalId"],
            voterId=d["voterId"],
            voterReputation=d["voterReputation"],
            approve=d["approve"],
            votedAt=d["votedAt"],
            rationale=d.get("rationale", ""),
        )


# ---------------------------------------------------------------------------
# GovernanceManager
# ---------------------------------------------------------------------------

class GovernanceManager:
    """
    Manages the full governance lifecycle:

      submit_proposal()   — create a new proposal (reputation-gated)
      cast_vote()         — record a vote weighted by the voter's reputation
      tally()             — evaluate all pending proposals; accept/reject/expire
      get_accepted_rules() — return the current governing ruleset
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        proposal_reputation_threshold: float = DEFAULT_PROPOSAL_REPUTATION_THRESHOLD,
        acceptance_threshold: float = DEFAULT_ACCEPTANCE_THRESHOLD,
        voting_window_seconds: float = DEFAULT_VOTING_WINDOW_SECONDS,
    ):
        root = data_dir or data_root()
        self._gov_dir = root / "mesh" / "governance"
        self._gov_dir.mkdir(parents=True, exist_ok=True)
        self._votes_dir = self._gov_dir / "votes"
        self._votes_dir.mkdir(parents=True, exist_ok=True)
        self._proposals_path = self._gov_dir / "proposals.json"
        self._accepted_rules_path = self._gov_dir / "accepted_rules.json"

        self.proposal_reputation_threshold = proposal_reputation_threshold
        self.acceptance_threshold = acceptance_threshold
        self.voting_window_seconds = voting_window_seconds

    # ------------------------------------------------------------------
    # Proposals
    # ------------------------------------------------------------------

    def submit_proposal(
        self,
        proposer_id: str,
        proposer_reputation: float,
        rule_key: str,
        proposed_value: Any,
        rationale: str = "",
    ) -> Optional[Proposal]:
        """
        Submit a governance proposal.

        Returns the Proposal if accepted for voting, or None if the proposer
        lacks sufficient reputation.
        """
        if proposer_reputation < self.proposal_reputation_threshold:
            logger.warning(
                "Proposal rejected: %s reputation %.2f < threshold %.2f",
                proposer_id[:16], proposer_reputation, self.proposal_reputation_threshold,
            )
            return None

        proposal_id = _derive_proposal_id(proposer_id, rule_key, proposed_value)

        # Don't create duplicates.
        existing = self.load_proposal(proposal_id)
        if existing and existing.status == "pending":
            logger.info("Duplicate proposal ignored: %s", proposal_id[:16])
            return existing

        now = time.time()
        proposal = Proposal(
            proposalId=proposal_id,
            proposerId=proposer_id,
            ruleKey=rule_key,
            proposedValue=proposed_value,
            rationale=rationale,
            submittedAt=now,
            expiresAt=now + self.voting_window_seconds,
        )
        self._save_proposal(proposal)
        logger.info(
            "Proposal submitted: id=%s key=%s proposer=%s...",
            proposal_id[:16], rule_key, proposer_id[:16],
        )
        return proposal

    def load_proposal(self, proposal_id: str) -> Optional[Proposal]:
        proposals = self._load_all_proposals()
        return proposals.get(proposal_id)

    def list_proposals(self, status: Optional[str] = None) -> List[Proposal]:
        proposals = self._load_all_proposals()
        result = list(proposals.values())
        if status:
            result = [p for p in result if p.status == status]
        return result

    # ------------------------------------------------------------------
    # Votes
    # ------------------------------------------------------------------

    def cast_vote(
        self,
        proposal_id: str,
        voter_id: str,
        voter_reputation: float,
        approve: bool,
        rationale: str = "",
    ) -> bool:
        """
        Cast a reputation-weighted vote on a proposal.

        Returns True if the vote was recorded, False if the proposal is
        not in a votable state (missing, expired, or already decided).
        """
        proposal = self.load_proposal(proposal_id)
        if not proposal:
            logger.warning("Vote rejected: unknown proposal %s", proposal_id[:16])
            return False
        if proposal.status != "pending":
            logger.warning(
                "Vote rejected: proposal %s is %s", proposal_id[:16], proposal.status
            )
            return False
        if proposal.is_expired():
            return False

        vote = Vote(
            proposalId=proposal_id,
            voterId=voter_id,
            voterReputation=voter_reputation,
            approve=approve,
            votedAt=time.time(),
            rationale=rationale,
        )
        self._save_vote(vote)
        logger.info(
            "Vote recorded: proposal=%s voter=%s... approve=%s weight=%.2f",
            proposal_id[:16], voter_id[:16], approve, voter_reputation,
        )
        return True

    def get_votes(self, proposal_id: str) -> List[Vote]:
        path = self._votes_dir / f"{proposal_id}.json"
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return [Vote.from_dict(v) for v in raw.get("votes", [])]
        except Exception as exc:
            logger.warning("Failed to load votes for %s: %s", proposal_id[:16], exc)
            return []

    # ------------------------------------------------------------------
    # Tally
    # ------------------------------------------------------------------

    def tally(self) -> Dict[str, List[str]]:
        """
        Evaluate all pending proposals.

        For each pending proposal:
          - If expired → mark "expired"
          - If weighted_approval / total_weight ≥ acceptance_threshold → accept
          - If weighted_rejection / total_weight > 1 − acceptance_threshold → reject
          - Otherwise leave pending for more votes

        Returns {"accepted": [...], "rejected": [...], "expired": [...]}
        sorted by proposalId.
        """
        accepted: List[str] = []
        rejected: List[str] = []
        expired: List[str] = []

        for proposal in self.list_proposals(status="pending"):
            now = time.time()

            if proposal.is_expired(now):
                proposal.status = "expired"
                proposal.decidedAt = now
                self._save_proposal(proposal)
                expired.append(proposal.proposalId)
                continue

            votes = self.get_votes(proposal.proposalId)
            if not votes:
                continue

            total_weight = sum(v.voterReputation for v in votes)
            if total_weight == 0:
                continue

            approve_weight = sum(v.voterReputation for v in votes if v.approve)
            reject_weight = total_weight - approve_weight
            approval_fraction = approve_weight / total_weight

            proposal.weightedApproval = approval_fraction
            proposal.weightedRejection = reject_weight / total_weight

            if approval_fraction >= self.acceptance_threshold:
                proposal.status = "accepted"
                proposal.decidedAt = now
                self._save_proposal(proposal)
                self._apply_rule(proposal)
                accepted.append(proposal.proposalId)
                logger.info(
                    "Proposal ACCEPTED: %s key=%s approval=%.2f",
                    proposal.proposalId[:16], proposal.ruleKey, approval_fraction,
                )
            elif proposal.weightedRejection >= self.acceptance_threshold:
                # Explicit rejection majority required — mirrors the acceptance bar.
                # A balanced or low-participation vote stays pending for more votes.
                proposal.status = "rejected"
                proposal.decidedAt = now
                self._save_proposal(proposal)
                rejected.append(proposal.proposalId)
                logger.info(
                    "Proposal REJECTED: %s key=%s rejection=%.2f",
                    proposal.proposalId[:16], proposal.ruleKey, proposal.weightedRejection,
                )

        return {"accepted": accepted, "rejected": rejected, "expired": expired}

    # ------------------------------------------------------------------
    # Accepted ruleset
    # ------------------------------------------------------------------

    def get_accepted_rules(self) -> Dict[str, Any]:
        """Return the current governing ruleset as a key→value dict."""
        if not self._accepted_rules_path.exists():
            return {}
        try:
            raw = json.loads(self._accepted_rules_path.read_text(encoding="utf-8"))
            return raw.get("rules", raw)
        except Exception:
            return {}

    def _apply_rule(self, proposal: Proposal) -> None:
        """Merge the accepted proposal's value into the ruleset and persist."""
        rules = self.get_accepted_rules()
        rules[proposal.ruleKey] = proposal.proposedValue
        payload = {
            "version": GOVERNANCE_SCHEMA_VERSION,
            "updatedAt": time.time(),
            "rules": rules,
        }
        _write_atomic(self._accepted_rules_path, payload)
        logger.info(
            "Rule applied: %s = %r", proposal.ruleKey, proposal.proposedValue
        )

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_all_proposals(self) -> Dict[str, Proposal]:
        if not self._proposals_path.exists():
            return {}
        try:
            raw = json.loads(self._proposals_path.read_text(encoding="utf-8"))
            return {
                p["proposalId"]: Proposal.from_dict(p)
                for p in raw.get("proposals", [])
            }
        except Exception as exc:
            logger.warning("Failed to load proposals: %s", exc)
            return {}

    def _save_proposal(self, proposal: Proposal) -> None:
        proposals = self._load_all_proposals()
        proposals[proposal.proposalId] = proposal
        payload = {
            "version": GOVERNANCE_SCHEMA_VERSION,
            "updatedAt": time.time(),
            "proposals": [p.to_dict() for p in proposals.values()],
        }
        _write_atomic(self._proposals_path, payload)

    def _save_vote(self, vote: Vote) -> None:
        votes = self.get_votes(vote.proposalId)
        # One vote per voter — last vote wins.
        votes = [v for v in votes if v.voterId != vote.voterId]
        votes.append(vote)
        path = self._votes_dir / f"{vote.proposalId}.json"
        _write_atomic(path, {"votes": [v.to_dict() for v in votes]})


# ---------------------------------------------------------------------------
# GovernanceAgent — MCP wrapper + DHT integration
# ---------------------------------------------------------------------------

class GovernanceAgent:
    """
    Wraps GovernanceManager and connects it to the DHT gossip layer.

    Responsibilities:
    - Expose MCP tools: submit_proposal, cast_vote, list_proposals,
      get_accepted_rules
    - poll(): called from the orchestrator run loop; fetches proposals and
      votes from the DHT, runs tally, broadcasts accepted rules when a
      proposal passes
    - Auto-vote: if *auto_vote* is True, the agent casts its own vote on
      every pending proposal it encounters, weighted by *local_reputation*.
      The vote is always "approve" by default (conservative bootstrap
      behaviour — the agent trusts the submitter's reputation gate to screen
      out bad proposals).  Override by subclassing and overriding
      _should_approve().

    The agent intentionally does NOT implement its own periodic loop.  The
    orchestrator calls poll() at a configurable interval (see
    GOVERNANCE_POLL_SECONDS in orchestrator.py) so that timing is
    controlled from one place.
    """

    def __init__(
        self,
        peer_id: str,
        gossip: Any,                          # AgentGossip — imported lazily to avoid circular import
        reputation_manager: Any,              # ReputationManager
        data_dir: Optional[Path] = None,
        auto_vote: bool = True,
        proposal_reputation_threshold: float = DEFAULT_PROPOSAL_REPUTATION_THRESHOLD,
        acceptance_threshold: float = DEFAULT_ACCEPTANCE_THRESHOLD,
    ):
        self.peer_id = peer_id
        self.gossip = gossip
        self.reputation_manager = reputation_manager
        self.auto_vote = auto_vote

        self.manager = GovernanceManager(
            data_dir=data_dir,
            proposal_reputation_threshold=proposal_reputation_threshold,
            acceptance_threshold=acceptance_threshold,
        )

        # Proposal IDs already processed this session (avoid reprocessing).
        self._seen_proposal_ids: set = set()

    # ------------------------------------------------------------------
    # Public tools (called by MCP or orchestrator directly)
    # ------------------------------------------------------------------

    def submit_proposal(
        self,
        rule_key: str,
        proposed_value: Any,
        rationale: str = "",
    ) -> Optional[Proposal]:
        """
        Submit a governance proposal as this node.

        Reputation-gated: uses the node's own current reputation score.
        Returns the Proposal object, or None if the reputation gate blocks it.
        """
        rep = self.reputation_manager.get_peer(self.peer_id)
        score = rep.reputationScore if rep else 0.0
        return self.manager.submit_proposal(
            proposer_id=self.peer_id,
            proposer_reputation=score,
            rule_key=rule_key,
            proposed_value=proposed_value,
            rationale=rationale,
        )

    def cast_vote(
        self,
        proposal_id: str,
        approve: bool,
        rationale: str = "",
    ) -> bool:
        """Cast a vote on an existing proposal, weighted by this node's reputation."""
        rep = self.reputation_manager.get_peer(self.peer_id)
        score = rep.reputationScore if rep else 0.0
        return self.manager.cast_vote(
            proposal_id=proposal_id,
            voter_id=self.peer_id,
            voter_reputation=score,
            approve=approve,
            rationale=rationale,
        )

    def get_accepted_rules(self) -> Dict[str, Any]:
        return self.manager.get_accepted_rules()

    def list_proposals(self, status: Optional[str] = None) -> List[Proposal]:
        return self.manager.list_proposals(status=status)

    # ------------------------------------------------------------------
    # DHT integration — called from orchestrator run loop
    # ------------------------------------------------------------------

    async def poll(self) -> Dict[str, Any]:
        """
        One poll cycle:
        1. Fetch new proposals from DHT via gossip.poll_proposals().
        2. For each new proposal: ingest it into GovernanceManager.
        3. Collect votes from peers for all pending proposals.
        4. Run tally().
        5. Broadcast accepted rules if any proposals were accepted.
        6. Broadcast this node's votes for any new proposals (auto_vote).

        Returns a summary dict: {"ingested": N, "voted": N, "accepted": [...]}
        """
        ingested = 0
        voted = 0

        # --- Step 1: Fetch new proposals ---
        new_raw = await self.gossip.poll_proposals(known_ids=self._seen_proposal_ids)
        for raw_proposal in new_raw:
            pid = raw_proposal.get("proposalId", "")
            self._seen_proposal_ids.add(pid)
            # Ingest into manager if it doesn't already exist.
            if not self.manager.load_proposal(pid):
                try:
                    p = Proposal.from_dict(raw_proposal)
                    # Trust the remote proposal's metadata; bypass the local
                    # reputation gate since the submitter's gate was enforced
                    # at submission time on their node.
                    self.manager._save_proposal(p)
                    ingested += 1
                    logger.info(
                        "Ingested remote proposal: %s key=%s", pid[:16], p.ruleKey
                    )
                except (KeyError, TypeError) as exc:
                    logger.warning("Malformed remote proposal: %s", exc)

        # --- Step 2: Collect peer votes ---
        peer_ids = self.gossip.list_trusted_peers(min_score=0.0)
        for proposal in self.manager.list_proposals(status="pending"):
            peer_votes = await self.gossip.poll_votes(proposal.proposalId, peer_ids)
            for raw_vote in peer_votes:
                try:
                    v = Vote.from_dict(raw_vote)
                    if v.voterId != self.peer_id:  # don't overwrite our own vote
                        self.manager._save_vote(v)
                except (KeyError, TypeError) as exc:
                    logger.warning("Malformed remote vote: %s", exc)

        # --- Step 3: Auto-vote on new proposals ---
        if self.auto_vote:
            for proposal in self.manager.list_proposals(status="pending"):
                if not self._has_voted(proposal.proposalId):
                    approve = self._should_approve(proposal)
                    if self.cast_vote(proposal.proposalId, approve=approve):
                        # Broadcast our vote to the DHT.
                        rep = self.reputation_manager.get_peer(self.peer_id)
                        score = rep.reputationScore if rep else 0.0
                        await self.gossip.broadcast_vote({
                            "proposalId": proposal.proposalId,
                            "voterId": self.peer_id,
                            "voterReputation": score,
                            "approve": approve,
                            "votedAt": time.time(),
                        })
                        voted += 1

        # --- Step 4: Tally ---
        result = self.manager.tally()
        accepted_ids: List[str] = result.get("accepted", [])

        # --- Step 5: Broadcast accepted rules ---
        if accepted_ids:
            rules = self.manager.get_accepted_rules()
            await self.gossip.broadcast_accepted_rules(rules, self.peer_id)
            logger.info(
                "Governance tally: accepted=%s rejected=%s expired=%s",
                accepted_ids, result.get("rejected", []), result.get("expired", []),
            )

        return {
            "ingested": ingested,
            "voted": voted,
            "accepted": accepted_ids,
            "rejected": result.get("rejected", []),
            "expired": result.get("expired", []),
        }

    def _has_voted(self, proposal_id: str) -> bool:
        votes = self.manager.get_votes(proposal_id)
        return any(v.voterId == self.peer_id for v in votes)

    def _should_approve(self, proposal: "Proposal") -> bool:  # noqa: F821
        """
        Default approval policy: approve everything (conservative bootstrap).

        Override this method to implement domain-specific voting logic,
        e.g. reject proposals that would lower the acceptance_threshold
        below a safety floor, or that come from low-reputation peers.
        """
        return True
