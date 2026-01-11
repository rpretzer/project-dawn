import json

from discovery import SovereignDiscovery


def test_record_peer_filters_protocols(tmp_path):
    data_dir = tmp_path / "data" / "mesh"
    discovery = SovereignDiscovery(data_dir=data_dir)

    rejected = discovery.record_peer(
        peer_id="peer-1",
        address="ws://localhost:8000",
        protocols=["/not-dawn/1.0.0"],
    )
    assert rejected is False

    accepted = discovery.record_peer(
        peer_id="peer-2",
        address="ws://localhost:8000",
        protocols=["/project-dawn/1.0.0"],
    )
    assert accepted is True

    cache_path = data_dir / "peers.json"
    assert cache_path.exists()
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert any(peer["peerId"] == "peer-2" for peer in payload["peers"])
