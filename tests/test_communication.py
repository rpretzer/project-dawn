import time

from communication import AgentGossip, AgentManifest
from reputation import ReputationManager


class _StubDiscovery:
    def __init__(self, dht=None):
        self._dht = dht

    def get_dht(self):
        return self._dht


class _StubDHT:
    def __init__(self):
        self.store_calls = []
        self.values = {}

    async def store(self, key, value, ttl=0):
        self.store_calls.append((key, value, ttl))
        self.values[key] = value
        return True

    async def find_value(self, key):
        return self.values.get(key)


def test_manifest_persistence(tmp_path):
    data_dir = tmp_path / "data"
    gossip = AgentGossip(_StubDiscovery(), ReputationManager(data_dir=data_dir / "mesh"), data_dir=data_dir)
    manifest = AgentManifest(
        peerId="peer-1",
        pgpFingerprint="fp",
        logitFingerprint="logits",
        displayName="Agent One",
        createdAt=time.time(),
    )
    gossip.save_manifest(manifest)
    loaded = gossip.load_manifest()
    assert loaded is not None
    assert loaded.peerId == "peer-1"


import asyncio


def test_presence_broadcast(tmp_path):
    data_dir = tmp_path / "data"
    dht = _StubDHT()
    gossip = AgentGossip(_StubDiscovery(dht), ReputationManager(data_dir=data_dir / "mesh"), data_dir=data_dir)
    asyncio.run(gossip.broadcast_presence("peer-2", "online", ["text"], timestamp=12345))
    assert dht.store_calls
    key, value, _ = dht.store_calls[0]
    assert key == "presence:peer-2"
    assert value["peerId"] == "peer-2"
    feed = (data_dir / "mesh" / "agent_feed.jsonl").read_text(encoding="utf-8")
    assert '"peerId":"peer-2"' in feed
