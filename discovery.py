"""
Discovery module for sovereign peer discovery and cache persistence.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import os
import socket
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from crypto import NodeIdentity
from data_paths import data_root
from p2p.dht import DHT

logger = logging.getLogger(__name__)

PROTOCOL_PREFIX = "/project-dawn/"
SERVICE_TYPE = "_projectdawn._tcp.local."

ServiceInfo = Any
Zeroconf = Any
ServiceBrowser = Any
ServiceListener = Any
ZEROCONF_AVAILABLE = importlib.util.find_spec("zeroconf") is not None
if ZEROCONF_AVAILABLE:
    zeroconf = importlib.import_module("zeroconf")
    ServiceInfo = zeroconf.ServiceInfo
    Zeroconf = zeroconf.Zeroconf
    ServiceBrowser = zeroconf.ServiceBrowser
    ServiceListener = zeroconf.ServiceListener


@dataclass
class PeerNode:
    peerId: str
    reputationScore: float
    uptime: float
    lastVerified: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PeerRecord:
    peerId: str
    address: str
    protocols: List[str]
    reputationScore: float
    uptime: float
    lastVerified: float
    lastSeen: float

    def to_node(self) -> PeerNode:
        return PeerNode(
            peerId=self.peerId,
            reputationScore=self.reputationScore,
            uptime=self.uptime,
            lastVerified=self.lastVerified,
        )


class SovereignDiscovery:
    def __init__(
        self,
        identity: Optional[NodeIdentity] = None,
        data_dir: Optional[Path] = None,
        protocol_prefix: str = PROTOCOL_PREFIX,
    ):
        self.identity = identity
        self.protocol_prefix = protocol_prefix
        self.data_dir = data_dir or data_root() / "mesh"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.peers_path = self.data_dir / "peers.json"
        self._peers: Dict[str, PeerRecord] = {}

        self._zeroconf: Optional[Zeroconf] = None
        self._browser: Optional[ServiceBrowser] = None

        self._dht: Optional[DHT] = DHT(identity) if identity else None
        self._load_cache()

    def _load_cache(self) -> None:
        if not self.peers_path.exists():
            return
        try:
            raw = json.loads(self.peers_path.read_text(encoding="utf-8"))
            for item in raw.get("peers", []):
                record = PeerRecord(**item)
                self._peers[record.peerId] = record
        except Exception as exc:
            logger.warning(f"Failed to load mesh cache: {exc}")

    def _save_cache(self) -> None:
        payload = {
            "version": 1,
            "peers": [asdict(peer) for peer in self._peers.values()],
        }
        tmp_path = self.peers_path.with_suffix(".json.tmp")
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, self.peers_path)

    def _protocols_allowed(self, protocols: Iterable[str]) -> bool:
        return any(protocol.startswith(self.protocol_prefix) for protocol in protocols)

    def record_peer(
        self,
        peer_id: str,
        address: str,
        protocols: Iterable[str],
        reputation_score: float = 0.1,
        uptime: float = 0.0,
        last_verified: Optional[float] = None,
        last_seen: Optional[float] = None,
    ) -> bool:
        protocols_list = list(protocols)
        if not protocols_list or not self._protocols_allowed(protocols_list):
            logger.debug(f"Rejected peer {peer_id[:16]}... due to protocol filter")
            return False

        now = time.time()
        record = PeerRecord(
            peerId=peer_id,
            address=address,
            protocols=protocols_list,
            reputationScore=reputation_score,
            uptime=uptime,
            lastVerified=last_verified or now,
            lastSeen=last_seen or now,
        )
        self._peers[peer_id] = record
        self._save_cache()
        return True

    def list_peer_nodes(self) -> List[Dict[str, Any]]:
        return [record.to_node().to_dict() for record in self._peers.values()]

    def list_peer_records(self) -> List[Dict[str, Any]]:
        return [asdict(record) for record in self._peers.values()]

    def start_mdns(self, service_name: Optional[str] = None, port: int = 8000) -> None:
        if not ZEROCONF_AVAILABLE:
            logger.warning("zeroconf not available; mDNS discovery disabled")
            return

        class _Listener(ServiceListener):
            def __init__(self, parent: "SovereignDiscovery"):
                self.parent = parent

            def add_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
                info = zeroconf.get_service_info(service_type, name)
                if not info:
                    return
                props = info.properties
                peer_id = props.get(b"peer_id", b"").decode("utf-8")
                address = props.get(b"address", b"").decode("utf-8")
                protocols_raw = props.get(b"protocols", b"").decode("utf-8")
                protocols = [p for p in protocols_raw.split(",") if p]
                if peer_id and address:
                    self.parent.record_peer(peer_id, address, protocols)

            def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
                return None

            def update_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
                return None

        self._zeroconf = Zeroconf()
        self._browser = ServiceBrowser(self._zeroconf, SERVICE_TYPE, _Listener(self))

        if self.identity:
            host = "127.0.0.1"
            info = ServiceInfo(
                SERVICE_TYPE,
                f"{service_name or 'project-dawn-node'}.{SERVICE_TYPE}",
                addresses=[socket.inet_aton(host)],
                port=port,
                properties={
                    b"peer_id": self.identity.get_node_id().encode("utf-8"),
                    b"address": f"ws://{host}:{port}".encode("utf-8"),
                    b"protocols": self.protocol_prefix.encode("utf-8"),
                },
            )
            self._zeroconf.register_service(info)

    def stop_mdns(self) -> None:
        if self._browser:
            self._browser.cancel()
        if self._zeroconf:
            self._zeroconf.close()

    def get_dht(self) -> Optional[DHT]:
        return self._dht

    async def discover_peers_dht(self, target_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._dht:
            return []
        target = target_id or (self.identity.get_node_id() if self.identity else None)
        if not target:
            return []
        discovered = []
        nodes = await self._dht.find_node(target)
        for node in nodes:
            if self.record_peer(node.node_id, node.address, [self.protocol_prefix]):
                discovered.append(node.node_id)
        return discovered
