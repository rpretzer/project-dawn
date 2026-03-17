"""
Tests for the Phase 2 seed protocol: SeedManager, CommonsPool, and the
Seed lifecycle (dormant → active → germinated / culled).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from agents.seed_manager import (
    AgentBlueprint,
    CommonsPool,
    GerminationConditions,
    Seed,
    SeedManager,
    _derive_seed_id,
    _write_atomic,
    SEED_SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _blueprint(
    peer_id: str = "peer-aaa",
    fingerprint: str = "fp-aaa",
    parent_id: str = "parent-aaa",
    generation: int = 1,
) -> AgentBlueprint:
    return AgentBlueprint(
        peerId=peer_id,
        logitFingerprint=fingerprint,
        parentId=parent_id,
        generation=generation,
        capabilityDeclarations=["text-inference"],
    )


def _manager(tmp_path: Path) -> SeedManager:
    return SeedManager(data_dir=tmp_path)


# ---------------------------------------------------------------------------
# _write_atomic
# ---------------------------------------------------------------------------

def test_write_atomic_creates_file(tmp_path):
    path = tmp_path / "test.json"
    _write_atomic(path, {"key": "value"})
    assert path.exists()
    assert json.loads(path.read_text()) == {"key": "value"}


def test_write_atomic_no_tmp_leftover(tmp_path):
    path = tmp_path / "test.json"
    _write_atomic(path, {"x": 1})
    tmp = path.with_suffix(".json.tmp")
    assert not tmp.exists(), "tmp file must be cleaned up after atomic write"


# ---------------------------------------------------------------------------
# CommonsPool
# ---------------------------------------------------------------------------

def test_commons_initial_balance_is_zero(tmp_path):
    pool = CommonsPool(tmp_path)
    assert pool.balance == 0
    assert pool.total_accumulated == 0


def test_commons_accumulate(tmp_path):
    pool = CommonsPool(tmp_path)
    pool.accumulate(100)
    assert pool.balance == 100
    assert pool.total_accumulated == 100


def test_commons_accumulate_multiple(tmp_path):
    pool = CommonsPool(tmp_path)
    pool.accumulate(50)
    pool.accumulate(75)
    assert pool.balance == 125
    assert pool.total_accumulated == 125


def test_commons_allocate_reduces_balance(tmp_path):
    pool = CommonsPool(tmp_path)
    pool.accumulate(200)
    ok = pool.allocate("seed-1", 80)
    assert ok is True
    assert pool.balance == 120


def test_commons_allocate_fails_when_insufficient(tmp_path):
    pool = CommonsPool(tmp_path)
    pool.accumulate(50)
    ok = pool.allocate("seed-1", 100)
    assert ok is False
    assert pool.balance == 50  # unchanged


def test_commons_return_credits(tmp_path):
    pool = CommonsPool(tmp_path)
    pool.accumulate(200)
    pool.allocate("seed-1", 80)
    returned = pool.return_credits("seed-1")
    assert returned == 80
    assert pool.balance == 200  # fully restored


def test_commons_return_credits_unknown_seed(tmp_path):
    pool = CommonsPool(tmp_path)
    pool.accumulate(100)
    returned = pool.return_credits("does-not-exist")
    assert returned == 0
    assert pool.balance == 100  # unchanged


def test_commons_persists_across_instances(tmp_path):
    pool1 = CommonsPool(tmp_path)
    pool1.accumulate(300)
    pool1.allocate("seed-x", 50)

    pool2 = CommonsPool(tmp_path)
    assert pool2.balance == 250
    assert pool2.total_accumulated == 300


# ---------------------------------------------------------------------------
# AgentBlueprint + GerminationConditions
# ---------------------------------------------------------------------------

def test_blueprint_round_trip():
    bp = _blueprint()
    assert AgentBlueprint.from_dict(bp.to_dict()) == bp


def test_germination_conditions_defaults():
    gc = GerminationConditions()
    assert gc.minPeerDensity == 3
    assert gc.minDemandSignals == 5
    assert gc.availableComputeUnits == 50


def test_germination_conditions_round_trip():
    gc = GerminationConditions(minPeerDensity=5, minDemandSignals=10, availableComputeUnits=100)
    assert GerminationConditions.from_dict(gc.to_dict()) == gc


# ---------------------------------------------------------------------------
# Seed schema
# ---------------------------------------------------------------------------

def test_seed_round_trip(tmp_path):
    bp = _blueprint()
    now = time.time()
    seed = Seed(
        seedId="abc123",
        blueprint=bp,
        computeReserves=100,
        germinationConditions=GerminationConditions(),
        issuedAt=now,
        expiresAt=now + 86400,
    )
    restored = Seed.from_dict(seed.to_dict())
    assert restored.seedId == seed.seedId
    assert restored.blueprint == seed.blueprint
    assert restored.computeReserves == seed.computeReserves
    assert restored.status == "dormant"


def test_seed_to_dict_includes_version():
    bp = _blueprint()
    now = time.time()
    seed = Seed(
        seedId="abc123",
        blueprint=bp,
        computeReserves=100,
        germinationConditions=GerminationConditions(),
        issuedAt=now,
        expiresAt=now + 86400,
    )
    assert seed.to_dict()["version"] == SEED_SCHEMA_VERSION


def test_seed_is_expired():
    bp = _blueprint()
    now = time.time()
    seed = Seed(
        seedId="exp",
        blueprint=bp,
        computeReserves=10,
        germinationConditions=GerminationConditions(),
        issuedAt=now - 2,
        expiresAt=now - 1,  # already expired
    )
    assert seed.is_expired()


def test_seed_not_expired_when_future():
    bp = _blueprint()
    now = time.time()
    seed = Seed(
        seedId="live",
        blueprint=bp,
        computeReserves=10,
        germinationConditions=GerminationConditions(),
        issuedAt=now,
        expiresAt=now + 3600,
    )
    assert not seed.is_expired()


# ---------------------------------------------------------------------------
# _derive_seed_id
# ---------------------------------------------------------------------------

def test_derive_seed_id_deterministic():
    bp = _blueprint()
    assert _derive_seed_id(bp) == _derive_seed_id(bp)


def test_derive_seed_id_differs_by_generation():
    bp1 = _blueprint(generation=1)
    bp2 = _blueprint(generation=2)
    assert _derive_seed_id(bp1) != _derive_seed_id(bp2)


# ---------------------------------------------------------------------------
# SeedManager.issue()
# ---------------------------------------------------------------------------

def test_issue_creates_seed_file(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    bp = _blueprint()
    seed = mgr.issue(bp, compute_reserves=100)
    assert seed is not None
    path = tmp_path / "seeds" / f"{seed.seedId}.json"
    assert path.exists()


def test_issue_deducts_from_commons(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    bp = _blueprint()
    mgr.issue(bp, compute_reserves=150)
    assert mgr.commons.balance == 350


def test_issue_returns_none_when_insufficient_credits(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(50)
    bp = _blueprint()
    seed = mgr.issue(bp, compute_reserves=100)
    assert seed is None
    assert mgr.commons.balance == 50  # not deducted


def test_issue_seed_status_is_dormant(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    seed = mgr.issue(_blueprint(), compute_reserves=100)
    assert seed.status == "dormant"


def test_issue_seed_id_is_deterministic(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(1000)
    bp = _blueprint()
    seed1 = mgr.issue(bp, compute_reserves=100)
    # Second issue with same blueprint reuses same seed_id (idempotent allocation key).
    assert seed1.seedId == _derive_seed_id(bp)


# ---------------------------------------------------------------------------
# SeedManager lifecycle: activate / germinate / cull
# ---------------------------------------------------------------------------

def test_activate_transitions_dormant_to_active(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    seed = mgr.issue(_blueprint(), compute_reserves=100)
    ok = mgr.activate(seed.seedId)
    assert ok is True
    loaded = mgr.load(seed.seedId)
    assert loaded.status == "active"
    assert loaded.activatedAt is not None


def test_activate_unknown_seed_returns_false(tmp_path):
    mgr = _manager(tmp_path)
    assert mgr.activate("does-not-exist") is False


def test_activate_already_active_returns_false(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    seed = mgr.issue(_blueprint(), compute_reserves=100)
    mgr.activate(seed.seedId)
    assert mgr.activate(seed.seedId) is False


def test_germinate_transitions_active_to_germinated(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    seed = mgr.issue(_blueprint(), compute_reserves=100)
    mgr.activate(seed.seedId)
    ok = mgr.germinate(seed.seedId)
    assert ok is True
    loaded = mgr.load(seed.seedId)
    assert loaded.status == "germinated"
    assert loaded.germinatedAt is not None


def test_germinate_dormant_seed_returns_false(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    seed = mgr.issue(_blueprint(), compute_reserves=100)
    assert mgr.germinate(seed.seedId) is False


def test_cull_returns_credits_to_commons(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    seed = mgr.issue(_blueprint(), compute_reserves=100)
    assert mgr.commons.balance == 400

    returned = mgr.cull(seed.seedId, reason="test")
    assert returned == 100
    assert mgr.commons.balance == 500

    loaded = mgr.load(seed.seedId)
    assert loaded.status == "culled"
    assert loaded.culledReason == "test"


def test_cull_already_culled_returns_zero(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    seed = mgr.issue(_blueprint(), compute_reserves=100)
    mgr.cull(seed.seedId)
    returned = mgr.cull(seed.seedId)
    assert returned == 0


# ---------------------------------------------------------------------------
# cull_expired
# ---------------------------------------------------------------------------

def test_cull_expired_removes_expired_seeds(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)

    # Issue a seed that has already expired.
    bp = _blueprint()
    seed_id = _derive_seed_id(bp)
    mgr.commons.allocate(seed_id, 100)
    now = time.time()
    expired_seed = Seed(
        seedId=seed_id,
        blueprint=bp,
        computeReserves=100,
        germinationConditions=GerminationConditions(),
        issuedAt=now - 200,
        expiresAt=now - 100,  # expired
    )
    mgr._save_seed(expired_seed)

    culled = mgr.cull_expired()
    assert seed_id in culled
    assert mgr.load(seed_id).status == "culled"


def test_cull_expired_skips_germinated_seeds(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    seed = mgr.issue(_blueprint(), compute_reserves=100)
    mgr.activate(seed.seedId)
    mgr.germinate(seed.seedId)

    culled = mgr.cull_expired()
    assert seed.seedId not in culled
    assert mgr.load(seed.seedId).status == "germinated"


# ---------------------------------------------------------------------------
# check_germination_conditions
# ---------------------------------------------------------------------------

def test_germination_conditions_met(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    seed = mgr.issue(
        _blueprint(),
        compute_reserves=100,
        germination_conditions=GerminationConditions(
            minPeerDensity=3, minDemandSignals=5, availableComputeUnits=50
        ),
    )
    assert mgr.check_germination_conditions(
        seed, peer_count=5, demand_signals=6, available_compute=100
    )


def test_germination_conditions_not_met_peer_density(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    seed = mgr.issue(
        _blueprint(),
        compute_reserves=100,
        germination_conditions=GerminationConditions(minPeerDensity=5),
    )
    assert not mgr.check_germination_conditions(
        seed, peer_count=2, demand_signals=10, available_compute=100
    )


def test_germination_conditions_not_met_demand(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    seed = mgr.issue(
        _blueprint(),
        compute_reserves=100,
        germination_conditions=GerminationConditions(minDemandSignals=10),
    )
    assert not mgr.check_germination_conditions(
        seed, peer_count=5, demand_signals=3, available_compute=100
    )


# ---------------------------------------------------------------------------
# list_seeds
# ---------------------------------------------------------------------------

def test_list_seeds_all(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    mgr.issue(_blueprint("peer-1", "fp-1", "parent-1", 1), compute_reserves=50)
    mgr.issue(_blueprint("peer-2", "fp-2", "parent-2", 1), compute_reserves=50)
    seeds = mgr.list_seeds()
    assert len(seeds) == 2


def test_list_seeds_filtered_by_status(tmp_path):
    mgr = _manager(tmp_path)
    mgr.commons.accumulate(500)
    s1 = mgr.issue(_blueprint("p1", "f1", "parent-1", 1), compute_reserves=50)
    s2 = mgr.issue(_blueprint("p2", "f2", "parent-2", 1), compute_reserves=50)
    mgr.activate(s1.seedId)

    dormant = mgr.list_seeds(status="dormant")
    active = mgr.list_seeds(status="active")
    assert len(dormant) == 1
    assert len(active) == 1
    assert dormant[0].seedId == s2.seedId
    assert active[0].seedId == s1.seedId
