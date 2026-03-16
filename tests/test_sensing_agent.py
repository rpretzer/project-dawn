"""
Tests for SensingAgent and AgentManifest lineage fields.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from agents.sensing_agent import SensingAgent, RegionStats, MIN_ATTEMPTS_FOR_PRESSURE
from communication import AgentManifest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(tmp_path: Path) -> SensingAgent:
    mesh = tmp_path / "mesh"
    (mesh / "failed").mkdir(parents=True)
    (mesh / "consensus").mkdir(parents=True)
    return SensingAgent(mesh_dir=mesh, data_dir=tmp_path / "agent-state")


def _write_consensus(consensus_dir: Path, task_id: str, accepted: bool, ts: float = 0.0) -> None:
    receipt = {
        "taskId": task_id,
        "accepted": accepted,
        "winners": ["peer-a", "peer-b"] if accepted else [],
        "fingerprint": "abc",
        "timestamp": ts or time.time(),
    }
    (consensus_dir / f"{task_id}.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )


def _write_failed(failed_dir: Path, task_id: str, ts: float = 0.0) -> None:
    record = {
        "taskId": task_id,
        "reason": "max_attempts",
        "timestamp": ts or time.time(),
        "workUnit": {"taskId": task_id, "inputBlob": {"seed": 0}},
    }
    (failed_dir / f"{task_id}.json").write_text(
        json.dumps(record), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# AgentManifest — lineage fields
# ---------------------------------------------------------------------------


def test_manifest_default_lineage_fields():
    m = AgentManifest(
        peerId="p1",
        pgpFingerprint="fp",
        logitFingerprint="lf",
        displayName="test",
        createdAt=1.0,
    )
    assert m.parentId is None
    assert m.generation == 0


def test_manifest_with_lineage():
    m = AgentManifest(
        peerId="child",
        pgpFingerprint="fp",
        logitFingerprint="lf",
        displayName="child-agent",
        createdAt=2.0,
        parentId="parent-peer-id",
        generation=1,
    )
    assert m.parentId == "parent-peer-id"
    assert m.generation == 1


def test_manifest_round_trip_with_lineage():
    m = AgentManifest(
        peerId="p2",
        pgpFingerprint="fp",
        logitFingerprint="lf",
        displayName="test",
        createdAt=1.0,
        parentId="p1",
        generation=3,
    )
    d = m.to_dict()
    m2 = AgentManifest.from_dict(d)
    assert m2.parentId == "p1"
    assert m2.generation == 3


def test_manifest_from_dict_backwards_compatible():
    """Old manifests without lineage fields must still load cleanly."""
    old_payload = {
        "peerId": "p-old",
        "pgpFingerprint": "fp",
        "logitFingerprint": "lf",
        "displayName": "old",
        "createdAt": 99.0,
    }
    m = AgentManifest.from_dict(old_payload)
    assert m.parentId is None
    assert m.generation == 0
    assert m.peerId == "p-old"


def test_manifest_from_dict_ignores_unknown_fields():
    """Extra keys in serialised payload must not cause a crash."""
    payload = {
        "peerId": "p-extra",
        "pgpFingerprint": "fp",
        "logitFingerprint": "lf",
        "displayName": "extra",
        "createdAt": 1.0,
        "unknownFutureField": "ignored",
    }
    m = AgentManifest.from_dict(payload)
    assert m.peerId == "p-extra"


# ---------------------------------------------------------------------------
# lineage.json written by Orchestrator
# ---------------------------------------------------------------------------


def test_orchestrator_writes_lineage_json(tmp_path):
    """_ensure_manifest() must create vault/lineage.json on first run."""
    import base64
    import hashlib
    from orchestrator import Orchestrator

    vault = tmp_path / "data" / "vault"
    vault.mkdir(parents=True)
    key_bytes = hashlib.sha256(b"lineage-test").digest()
    pgp = "\n".join([
        "-----BEGIN PGP PUBLIC KEY BLOCK-----",
        base64.b64encode(key_bytes).decode(),
        "=xxxx",
        "-----END PGP PUBLIC KEY BLOCK-----",
    ])
    (vault / "public_key.asc").write_text(pgp, encoding="utf-8")

    orc = Orchestrator(data_dir=tmp_path / "data")
    lineage_path = vault / "lineage.json"
    assert lineage_path.exists(), "lineage.json must be written at genesis"

    record = json.loads(lineage_path.read_text(encoding="utf-8"))
    assert record["generation"] == 0
    assert record["parentId"] is None
    assert record["peerId"] == orc.peer_id
    assert "logitFingerprint" in record


def test_orchestrator_does_not_overwrite_existing_lineage(tmp_path):
    """lineage.json must not be overwritten on subsequent Orchestrator inits."""
    import base64
    import hashlib
    from orchestrator import Orchestrator

    vault = tmp_path / "data" / "vault"
    vault.mkdir(parents=True)
    key_bytes = hashlib.sha256(b"lineage-stable").digest()
    pgp = "\n".join([
        "-----BEGIN PGP PUBLIC KEY BLOCK-----",
        base64.b64encode(key_bytes).decode(),
        "=xxxx",
        "-----END PGP PUBLIC KEY BLOCK-----",
    ])
    (vault / "public_key.asc").write_text(pgp, encoding="utf-8")

    Orchestrator(data_dir=tmp_path / "data")
    lineage_path = vault / "lineage.json"
    mtime_first = lineage_path.stat().st_mtime

    # Second init — must not touch lineage.json
    Orchestrator(data_dir=tmp_path / "data")
    assert lineage_path.stat().st_mtime == mtime_first


# ---------------------------------------------------------------------------
# SensingAgent — scan()
# ---------------------------------------------------------------------------


def test_scan_empty_dirs_produces_empty_map(tmp_path):
    agent = _make_agent(tmp_path)
    cap_map = agent.scan()

    assert cap_map["version"] == 1
    assert cap_map["regions"] == {}
    assert cap_map["evolutionary_pressure"] is False
    assert cap_map["pressure_regions"] == []
    assert cap_map["summary"]["total_attempts"] == 0


def test_scan_accepted_consensus(tmp_path):
    agent = _make_agent(tmp_path)
    _write_consensus(agent.consensus_dir, "task-1", accepted=True)
    _write_consensus(agent.consensus_dir, "task-2", accepted=True)

    cap_map = agent.scan()
    assert cap_map["summary"]["total_attempts"] == 2
    assert cap_map["summary"]["total_successes"] == 2
    assert cap_map["summary"]["total_failures"] == 0
    assert cap_map["evolutionary_pressure"] is False


def test_scan_rejected_consensus(tmp_path):
    agent = _make_agent(tmp_path)
    _write_consensus(agent.consensus_dir, "task-fail", accepted=False)

    cap_map = agent.scan()
    assert cap_map["summary"]["total_failures"] == 1


def test_scan_failed_tasks_without_consensus(tmp_path):
    agent = _make_agent(tmp_path)
    _write_failed(agent.failed_dir, "task-never-ran")

    cap_map = agent.scan()
    assert cap_map["summary"]["total_attempts"] == 1
    assert cap_map["summary"]["total_failures"] == 1


def test_scan_failed_task_with_consensus_not_double_counted(tmp_path):
    """
    A task that appears in both failed/ and consensus/ must only be counted
    once (from the consensus receipt, not the failed record).
    """
    agent = _make_agent(tmp_path)
    _write_consensus(agent.consensus_dir, "task-both", accepted=True)
    _write_failed(agent.failed_dir, "task-both")

    cap_map = agent.scan()
    assert cap_map["summary"]["total_attempts"] == 1
    assert cap_map["summary"]["total_successes"] == 1
    assert cap_map["summary"]["total_failures"] == 0


def test_scan_writes_capability_map_json(tmp_path):
    agent = _make_agent(tmp_path)
    _write_consensus(agent.consensus_dir, "t1", accepted=True)
    agent.scan()

    assert agent.capability_map_path.exists()
    loaded = json.loads(agent.capability_map_path.read_text(encoding="utf-8"))
    assert loaded["version"] == 1


def test_scan_atomic_no_tmp_leftover(tmp_path):
    agent = _make_agent(tmp_path)
    agent.scan()
    assert not list(agent.mesh_dir.glob("*.tmp"))


# ---------------------------------------------------------------------------
# SensingAgent — pressure detection
# ---------------------------------------------------------------------------


def test_pressure_not_triggered_below_threshold(tmp_path):
    """A single failed task must not trigger pressure (MIN_ATTEMPTS_FOR_PRESSURE)."""
    agent = _make_agent(tmp_path)
    for i in range(MIN_ATTEMPTS_FOR_PRESSURE - 1):
        _write_failed(agent.failed_dir, f"task-{i}")
    cap_map = agent.scan()
    assert cap_map["evolutionary_pressure"] is False


def test_pressure_triggered_above_threshold(tmp_path):
    """
    A region with ≥ MIN_ATTEMPTS_FOR_PRESSURE attempts and failure_rate ≥
    pressure_threshold must be flagged.

    These three task IDs were pre-computed to all hash to region '400d'
    (sha256(task_id)[:4] == '400d'), so all failures land in the same bucket.
    """
    agent = _make_agent(tmp_path)
    agent2 = SensingAgent(mesh_dir=agent.mesh_dir, pressure_threshold=0.5)

    # Pre-computed IDs that all map to region '400d'.
    colliding_ids = ["task-01108", "task-01732", "task-02453"]
    for task_id in colliding_ids:
        _write_failed(agent.failed_dir, task_id)

    cap_map = agent2.scan()
    assert cap_map["evolutionary_pressure"] is True
    assert "400d" in cap_map["pressure_regions"]


def test_pressure_cleared_when_failures_resolve(tmp_path):
    """After failures turn to successes, pressure_regions must become empty."""
    agent = _make_agent(tmp_path)
    # Write many successes, zero failures
    for i in range(10):
        _write_consensus(agent.consensus_dir, f"success-{i}", accepted=True)
    cap_map = agent.scan()
    assert cap_map["evolutionary_pressure"] is False


# ---------------------------------------------------------------------------
# SensingAgent — load_capability_map / is_under_pressure
# ---------------------------------------------------------------------------


def test_load_capability_map_none_before_scan(tmp_path):
    agent = _make_agent(tmp_path)
    assert agent.load_capability_map() is None


def test_load_capability_map_after_scan(tmp_path):
    agent = _make_agent(tmp_path)
    agent.scan()
    loaded = agent.load_capability_map()
    assert loaded is not None
    assert "regions" in loaded


def test_is_under_pressure_false_before_scan(tmp_path):
    agent = _make_agent(tmp_path)
    assert agent.is_under_pressure() is False


def test_is_under_pressure_reflects_scan(tmp_path):
    agent = SensingAgent(
        mesh_dir=tmp_path / "mesh",
        data_dir=tmp_path / "agent-state",
        pressure_threshold=0.5,
    )
    (agent.failed_dir).mkdir(parents=True)
    (agent.consensus_dir).mkdir(parents=True)

    # Pre-computed IDs that all map to region 'b151'.
    colliding_ids = ["lots-of-fail-0010", "lots-of-fail-2935", "lots-of-fail-3077"]
    for task_id in colliding_ids:
        _write_failed(agent.failed_dir, task_id)

    agent.scan()
    assert agent.is_under_pressure() is True


# ---------------------------------------------------------------------------
# RegionStats unit tests
# ---------------------------------------------------------------------------


def test_region_stats_failure_rate_zero_when_no_attempts():
    stats = RegionStats()
    stats.attempts = 0
    assert stats.failure_rate == 0.0


def test_region_stats_failure_rate_correct():
    stats = RegionStats(attempts=10, successes=3, failures=7)
    assert abs(stats.failure_rate - 0.7) < 1e-9


def test_region_stats_to_dict_includes_failure_rate():
    stats = RegionStats(attempts=4, successes=1, failures=3)
    d = stats.to_dict()
    assert "failure_rate" in d
    assert abs(d["failure_rate"] - 0.75) < 1e-3
