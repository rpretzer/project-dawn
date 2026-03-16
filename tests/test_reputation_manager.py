import time

from reputation import ReputationManager, DECAY_WINDOW_SECONDS, GOSSIP_WEIGHT


def test_reputation_persistence(tmp_path):
    data_dir = tmp_path / "data" / "mesh"
    manager = ReputationManager(data_dir=data_dir)
    manager.sync_reputation(
        [
            {
                "peerId": "peer-1",
                "reputationScore": 0.4,
                "uptime": 10.0,
                "lastVerified": time.time(),
            }
        ]
    )

    reloaded = ReputationManager(data_dir=data_dir)
    nodes = reloaded.list_peer_nodes()
    assert any(node["peerId"] == "peer-1" for node in nodes)


def test_decay_after_window(tmp_path):
    data_dir = tmp_path / "data" / "mesh"
    manager = ReputationManager(data_dir=data_dir)
    now = time.time()
    record = manager.record_peer(
        peer_id="peer-2",
        reputation_score=1.0,
        last_verified=now - (DECAY_WINDOW_SECONDS * 2),
        last_seen=now - (DECAY_WINDOW_SECONDS * 2),
    )
    record.lastDecay = record.lastVerified
    manager.apply_decay(now=now)
    decayed = manager.get_peer("peer-2")
    assert decayed is not None
    assert decayed.reputationScore < 1.0


def test_blacklist_after_three_failures(tmp_path):
    data_dir = tmp_path / "data" / "mesh"
    manager = ReputationManager(data_dir=data_dir)
    for _ in range(3):
        manager.update_reputation("peer-3", is_successful=False)

    record = manager.get_peer("peer-3")
    assert record is not None
    assert record.blacklisted is True
    assert record.reputationScore <= 0.1


# --- sync_reputation (gossip) tests ---

def test_gossip_cannot_instantly_inflate_score(tmp_path):
    """Gossip claiming maximum score must not push to maximum in one step."""
    data_dir = tmp_path / "data" / "mesh"
    manager = ReputationManager(data_dir=data_dir)
    manager.record_peer("peer-1", reputation_score=0.1)

    manager.sync_reputation([{
        "peerId": "peer-1",
        "reputationScore": 1.0,
        "uptime": 0.0,
        "lastVerified": time.time(),
    }])

    record = manager.get_peer("peer-1")
    assert record is not None
    expected = (1.0 - GOSSIP_WEIGHT) * 0.1 + GOSSIP_WEIGHT * 1.0
    assert abs(record.reputationScore - expected) < 0.01
    assert record.reputationScore < 1.0


def test_gossip_can_decrease_score(tmp_path):
    """Unlike the old max() implementation, gossip must be able to decrease scores."""
    data_dir = tmp_path / "data" / "mesh"
    manager = ReputationManager(data_dir=data_dir)
    manager.record_peer("peer-1", reputation_score=0.9)

    manager.sync_reputation([{
        "peerId": "peer-1",
        "reputationScore": 0.1,
        "uptime": 0.0,
        "lastVerified": time.time(),
    }])

    record = manager.get_peer("peer-1")
    assert record is not None
    assert record.reputationScore < 0.9


def test_gossip_colluding_peers_bounded_inflation(tmp_path):
    """Even with sustained max gossip over many cycles, inflation is bounded."""
    data_dir = tmp_path / "data" / "mesh"
    manager = ReputationManager(data_dir=data_dir)
    manager.record_peer("peer-1", reputation_score=0.1)

    gossip = [{"peerId": "peer-1", "reputationScore": 1.0, "uptime": 0.0, "lastVerified": time.time()}]
    for _ in range(5):
        manager.sync_reputation(gossip)

    record = manager.get_peer("peer-1")
    # After 5 cycles of max gossip: converges toward ~0.85 (geometric series), well below 1.0
    assert record.reputationScore < 0.95
    assert record.reputationScore > 0.1  # should have moved


def test_gossip_new_peer_starts_at_blended_score(tmp_path):
    """A peer seen only via gossip gets a score blended from the default, not the gossip value."""
    data_dir = tmp_path / "data" / "mesh"
    manager = ReputationManager(data_dir=data_dir)

    manager.sync_reputation([{
        "peerId": "new-peer",
        "reputationScore": 0.9,
        "uptime": 0.0,
        "lastVerified": time.time(),
    }])

    record = manager.get_peer("new-peer")
    assert record is not None
    # Default PeerReputation.reputationScore is 0.1; blended with 0.9
    expected = (1.0 - GOSSIP_WEIGHT) * 0.1 + GOSSIP_WEIGHT * 0.9
    assert abs(record.reputationScore - expected) < 0.01


def test_gossip_clamps_out_of_range_scores(tmp_path):
    """Incoming scores outside [0, 1] must be clamped before blending."""
    data_dir = tmp_path / "data" / "mesh"
    manager = ReputationManager(data_dir=data_dir)
    manager.record_peer("peer-x", reputation_score=0.5)

    manager.sync_reputation([{
        "peerId": "peer-x",
        "reputationScore": 999.0,  # malformed / malicious
        "uptime": 0.0,
        "lastVerified": time.time(),
    }])

    record = manager.get_peer("peer-x")
    # 999 should be clamped to 1.0 before blending
    expected = (1.0 - GOSSIP_WEIGHT) * 0.5 + GOSSIP_WEIGHT * 1.0
    assert abs(record.reputationScore - expected) < 0.01
