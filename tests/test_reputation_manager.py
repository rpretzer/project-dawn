import time

from reputation import ReputationManager, DECAY_WINDOW_SECONDS


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
