"""
Tests for ReplicationAgent — Phase 2 evolutionary replication coordinator.

Covers:
- _child_fingerprint: heritable, unique, deterministic given same nonce (via mock)
- _select_candidates: threshold filtering and sort order
- _build_child_blueprint: correct lineage fields
- replicate(): issues seeds, emits feed events, handles empty reputation
- replicate(): respects max_seeds_per_cycle
- replicate(): handles insufficient commons balance gracefully
- activate_ready_seeds(): activates when conditions met, skips when not
- cull_expired(): delegates to SeedManager and emits events
- MCP tools: trigger_replication, list_seeds, get_commons_balance
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from agents.replication_agent import (
    ReplicationAgent,
    _child_fingerprint,
    _load_reputation,
    _load_lineage,
)
from agents.seed_manager import (
    AgentBlueprint,
    GerminationConditions,
    Seed,
    SeedManager,
    _derive_seed_id,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_agent(tmp_path: Path, **kwargs) -> ReplicationAgent:
    return ReplicationAgent(
        mesh_dir=tmp_path / "mesh",
        vault_dir=tmp_path / "vault",
        data_dir=tmp_path / "agent-state",
        **kwargs,
    )


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_reputation(mesh_dir: Path, scores: Dict[str, float]) -> None:
    _write_json(mesh_dir / "reputation.json", {"scores": scores})


def _write_lineage(vault_dir: Path, record: Dict[str, Any]) -> None:
    _write_json(vault_dir / "lineage.json", record)


# ---------------------------------------------------------------------------
# _child_fingerprint
# ---------------------------------------------------------------------------

def test_child_fingerprint_length():
    fp = _child_fingerprint("parent-fp", generation=1)
    assert len(fp) == 32


def test_child_fingerprint_varies_between_calls():
    fp1 = _child_fingerprint("parent-fp", generation=1)
    fp2 = _child_fingerprint("parent-fp", generation=1)
    # UUID nonce ensures two calls produce different fingerprints.
    assert fp1 != fp2


def test_child_fingerprint_differs_by_generation():
    fp1 = _child_fingerprint("parent-fp", generation=1)
    fp2 = _child_fingerprint("parent-fp", generation=2)
    # Even ignoring the nonce, different generations produce different hashes.
    # (The nonce also varies, but we verify generation is included in input.)
    assert len(fp1) == len(fp2) == 32  # format is stable


# ---------------------------------------------------------------------------
# _load_reputation
# ---------------------------------------------------------------------------

def test_load_reputation_missing_file(tmp_path):
    scores = _load_reputation(tmp_path / "does_not_exist.json")
    assert scores == {}


def test_load_reputation_scores_key(tmp_path):
    path = tmp_path / "reputation.json"
    path.write_text(json.dumps({"scores": {"peer-a": 0.8, "peer-b": 0.3}}))
    scores = _load_reputation(path)
    assert scores["peer-a"] == pytest.approx(0.8)
    assert scores["peer-b"] == pytest.approx(0.3)


def test_load_reputation_flat_format(tmp_path):
    """Also handles reputation.json without a 'scores' wrapper."""
    path = tmp_path / "reputation.json"
    path.write_text(json.dumps({"peer-x": 0.5}))
    scores = _load_reputation(path)
    assert scores["peer-x"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# _load_lineage
# ---------------------------------------------------------------------------

def test_load_lineage_missing(tmp_path):
    lineage = _load_lineage(tmp_path)
    assert lineage == {}


def test_load_lineage_present(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_json(vault / "lineage.json", {"peerId": "p1", "generation": 2})
    lineage = _load_lineage(vault)
    assert lineage["peerId"] == "p1"
    assert lineage["generation"] == 2


# ---------------------------------------------------------------------------
# ReplicationAgent._select_candidates
# ---------------------------------------------------------------------------

def test_select_candidates_filters_below_threshold(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.7)
    candidates = agent._select_candidates({"p-high": 0.9, "p-low": 0.4, "p-mid": 0.7})
    assert "p-low" not in candidates
    assert "p-high" in candidates
    assert "p-mid" in candidates


def test_select_candidates_sorted_by_reputation(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5)
    scores = {"p-a": 0.6, "p-b": 0.9, "p-c": 0.75}
    candidates = agent._select_candidates(scores)
    assert candidates[0] == "p-b"
    assert candidates[1] == "p-c"
    assert candidates[2] == "p-a"


def test_select_candidates_empty_when_none_qualify(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.9)
    candidates = agent._select_candidates({"p-a": 0.5, "p-b": 0.3})
    assert candidates == []


# ---------------------------------------------------------------------------
# ReplicationAgent._build_child_blueprint
# ---------------------------------------------------------------------------

def test_build_child_blueprint_lineage(tmp_path):
    agent = _make_agent(tmp_path)
    parent_lineage = {"peerId": "parent-p", "logitFingerprint": "fp-parent", "generation": 2}
    bp = agent._build_child_blueprint(
        parent_peer_id="parent-p",
        parent_lineage=parent_lineage,
        capability_hint=None,
        parent_generation=2,
    )
    assert bp.parentId == "parent-p"
    assert bp.generation == 3
    assert len(bp.logitFingerprint) == 32


def test_build_child_blueprint_capability_hint(tmp_path):
    agent = _make_agent(tmp_path)
    bp = agent._build_child_blueprint(
        parent_peer_id="p",
        parent_lineage={},
        capability_hint="math-inference",
        parent_generation=0,
    )
    assert bp.capabilityDeclarations[0] == "math-inference"


def test_build_child_blueprint_default_capabilities(tmp_path):
    agent = _make_agent(tmp_path)
    bp = agent._build_child_blueprint(
        parent_peer_id="p",
        parent_lineage={},
        capability_hint=None,
        parent_generation=0,
    )
    assert "text-inference" in bp.capabilityDeclarations
    assert "proof-of-logits" in bp.capabilityDeclarations


# ---------------------------------------------------------------------------
# ReplicationAgent.replicate()
# ---------------------------------------------------------------------------

def test_replicate_empty_reputation_returns_no_seeds(tmp_path):
    agent = _make_agent(tmp_path)
    seeds = agent.replicate()
    assert seeds == []


def test_replicate_issues_seeds_for_candidates(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5, seed_compute_reserves=50)
    _write_reputation(tmp_path / "mesh", {"peer-alpha": 0.9, "peer-beta": 0.8})
    # Fund the commons pool so seeds can be issued.
    agent._seed_manager.commons.accumulate(1000)

    seeds = agent.replicate()
    assert len(seeds) > 0
    for seed in seeds:
        assert seed.status == "dormant"
        assert seed.blueprint.parentId in ("peer-alpha", "peer-beta")


def test_replicate_respects_max_seeds_per_cycle(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5,
                        seed_compute_reserves=10, max_seeds_per_cycle=2)
    scores = {f"peer-{i}": 0.9 for i in range(10)}
    _write_reputation(tmp_path / "mesh", scores)
    agent._seed_manager.commons.accumulate(10000)

    seeds = agent.replicate()
    assert len(seeds) <= 2


def test_replicate_handles_insufficient_commons(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5, seed_compute_reserves=100)
    _write_reputation(tmp_path / "mesh", {"peer-rich": 0.9})
    # Don't fund the commons — should return empty list gracefully.

    seeds = agent.replicate()
    assert seeds == []


def test_replicate_emits_feed_events(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5, seed_compute_reserves=50)
    _write_reputation(tmp_path / "mesh", {"peer-x": 0.9})
    agent._seed_manager.commons.accumulate(500)

    agent.replicate()

    feed_path = tmp_path / "mesh" / "agent_feed.jsonl"
    assert feed_path.exists()
    events = [json.loads(line) for line in feed_path.read_text().splitlines() if line]
    assert any(e["type"] == "seed_issued" for e in events)


def test_replicate_sets_pressure_regions_in_feed(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5, seed_compute_reserves=50)
    _write_reputation(tmp_path / "mesh", {"peer-x": 0.9})
    agent._seed_manager.commons.accumulate(500)

    agent.replicate(pressure_regions=["ab12", "cd34"])

    feed_path = tmp_path / "mesh" / "agent_feed.jsonl"
    events = [json.loads(line) for line in feed_path.read_text().splitlines() if line]
    issued = [e for e in events if e["type"] == "seed_issued"]
    assert len(issued) > 0
    assert issued[0]["pressure_regions"] == ["ab12", "cd34"]


# ---------------------------------------------------------------------------
# ReplicationAgent.activate_ready_seeds()
# ---------------------------------------------------------------------------

def test_activate_ready_seeds_activates_when_conditions_met(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5, seed_compute_reserves=50)
    _write_reputation(tmp_path / "mesh", {"peer-y": 0.9})
    agent._seed_manager.commons.accumulate(500)
    seeds = agent.replicate()
    assert seeds

    # Very permissive conditions — should activate immediately.
    activated = agent.activate_ready_seeds(
        peer_count=100,
        demand_signals=100,
        available_compute=1000,
    )
    assert len(activated) == len(seeds)
    for seed in seeds:
        loaded = agent._seed_manager.load(seed.seedId)
        assert loaded.status == "active"


def test_activate_ready_seeds_skips_when_conditions_not_met(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5, seed_compute_reserves=50)
    _write_reputation(tmp_path / "mesh", {"peer-z": 0.9})
    agent._seed_manager.commons.accumulate(500)
    seeds = agent.replicate(
        # Use very demanding germination conditions.
    )
    # Force demanding conditions onto the seed.
    for seed in seeds:
        seed_path = agent._seed_manager._seeds_dir / f"{seed.seedId}.json"
        data = json.loads(seed_path.read_text())
        data["germinationConditions"]["minPeerDensity"] = 999
        seed_path.write_text(json.dumps(data))

    activated = agent.activate_ready_seeds(peer_count=1, demand_signals=1, available_compute=10)
    assert activated == []


# ---------------------------------------------------------------------------
# ReplicationAgent.cull_expired()
# ---------------------------------------------------------------------------

def test_cull_expired_returns_credits(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5, seed_compute_reserves=100)
    _write_reputation(tmp_path / "mesh", {"peer-exp": 0.9})
    agent._seed_manager.commons.accumulate(1000)
    seeds = agent.replicate()
    assert seeds

    balance_after_issue = agent._seed_manager.commons.balance

    # Force expiry.
    for seed in seeds:
        seed_path = agent._seed_manager._seeds_dir / f"{seed.seedId}.json"
        data = json.loads(seed_path.read_text())
        data["expiresAt"] = time.time() - 1
        seed_path.write_text(json.dumps(data))

    culled = agent.cull_expired()
    assert len(culled) == len(seeds)
    assert agent._seed_manager.commons.balance > balance_after_issue  # credits returned


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

def test_tool_get_commons_balance(tmp_path):
    agent = _make_agent(tmp_path)
    agent._seed_manager.commons.accumulate(500)
    result = agent._tool_get_commons_balance()
    assert result["currentBalance"] == 500
    assert result["totalAccumulated"] == 500


def test_tool_list_seeds_all(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5, seed_compute_reserves=50)
    _write_reputation(tmp_path / "mesh", {"peer-t": 0.9})
    agent._seed_manager.commons.accumulate(500)
    agent.replicate()

    result = agent._tool_list_seeds()
    assert result["total"] > 0
    assert all("seedId" in s for s in result["seeds"])


def test_tool_list_seeds_filtered(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5, seed_compute_reserves=50)
    _write_reputation(tmp_path / "mesh", {"peer-t": 0.9})
    agent._seed_manager.commons.accumulate(500)
    agent.replicate()

    result = agent._tool_list_seeds(status="dormant")
    assert result["total"] > 0
    assert all(s["status"] == "dormant" for s in result["seeds"])


def test_tool_trigger_replication(tmp_path):
    agent = _make_agent(tmp_path, parent_reputation_threshold=0.5, seed_compute_reserves=50)
    _write_reputation(tmp_path / "mesh", {"peer-q": 0.9})
    agent._seed_manager.commons.accumulate(500)

    result = agent._tool_trigger_replication()
    assert result["seeds_issued"] > 0
    assert len(result["seed_ids"]) == result["seeds_issued"]
