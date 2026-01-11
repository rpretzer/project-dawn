"""
Agent gossip and persona manifest for autonomous propagation.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from crypto.signing import MessageSigner
from data_paths import data_root
from discovery import SovereignDiscovery
from reputation import ReputationManager

logger = logging.getLogger(__name__)


@dataclass
class AgentManifest:
    peerId: str
    pgpFingerprint: str
    logitFingerprint: str
    displayName: str
    createdAt: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HandshakeUnit:
    peerId: str
    reputationScore: float
    logitFingerprint: str
    timestamp: float
    nodeSignature: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentGossip:
    def __init__(
        self,
        discovery: SovereignDiscovery,
        reputation: ReputationManager,
        signer: Optional[MessageSigner] = None,
        data_dir: Optional[Path] = None,
    ):
        self.discovery = discovery
        self.reputation = reputation
        self.signer = signer
        self.data_dir = data_dir or data_root()
        self.vault_dir = self.data_dir / "vault"
        self.mesh_dir = self.data_dir / "mesh"
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.mesh_dir.mkdir(parents=True, exist_ok=True)

        self.manifest_path = self.vault_dir / "manifest.json"
        self.feed_path = self.mesh_dir / "agent_feed.jsonl"

    def load_manifest(self) -> Optional[AgentManifest]:
        if not self.manifest_path.exists():
            return None
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return AgentManifest(**payload)

    def save_manifest(self, manifest: AgentManifest) -> None:
        self._atomic_write_json(self.manifest_path, manifest.to_dict())

    def emit_feed(self, event: Dict[str, Any]) -> None:
        line = json.dumps(event, sort_keys=True, separators=(",", ":"))
        with open(self.feed_path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")

    def create_handshake_unit(self, peer_id: str, logit_fingerprint: str) -> HandshakeUnit:
        record = self.reputation.get_peer(peer_id)
        score = record.reputationScore if record else 0.1
        timestamp = time.time()
        signature = ""
        if self.signer:
            payload = f"{peer_id}:{score}:{logit_fingerprint}:{timestamp}".encode("utf-8")
            signature = self.signer.sign(payload).hex()
        return HandshakeUnit(
            peerId=peer_id,
            reputationScore=score,
            logitFingerprint=logit_fingerprint,
            timestamp=timestamp,
            nodeSignature=signature,
        )

    async def broadcast_handshake(self, peer_id: str, logit_fingerprint: str) -> bool:
        dht = self.discovery.get_dht()
        if not dht:
            return False
        handshake = self.create_handshake_unit(peer_id, logit_fingerprint)
        result = await dht.store(
            f"handshake:{peer_id}",
            handshake.to_dict(),
            ttl=3600.0,
        )
        if result:
            self.emit_feed(
                {
                    "type": "handshake",
                    "peerId": peer_id,
                    "status": "sent",
                    "timestamp": handshake.timestamp,
                }
            )
        return result

    async def fetch_handshake(self, peer_id: str) -> Optional[Dict[str, Any]]:
        dht = self.discovery.get_dht()
        if not dht:
            return None
        return await dht.find_value(f"handshake:{peer_id}")

    async def broadcast_presence(
        self,
        peer_id: str,
        status: str,
        capabilities: Iterable[str],
        timestamp: Optional[float] = None,
    ) -> bool:
        dht = self.discovery.get_dht()
        if not dht:
            return False

        payload = {
            "peerId": peer_id,
            "status": status,
            "capabilities": list(capabilities),
            "timestamp": timestamp or time.time(),
        }
        result = await dht.store(f"presence:{peer_id}", payload, ttl=3600.0)
        if result:
            self.emit_feed(
                {
                    "type": "presence",
                    "peerId": peer_id,
                    "status": status,
                    "timestamp": payload["timestamp"],
                }
            )
        return result

    async def fetch_peer_presence(self, peer_id: str) -> Optional[Dict[str, Any]]:
        dht = self.discovery.get_dht()
        if not dht:
            return None
        return await dht.find_value(f"presence:{peer_id}")

    def list_trusted_peers(self, min_score: float = 0.7) -> List[str]:
        return [
            record.peerId
            for record in self.reputation._records.values()
            if not record.blacklisted and record.reputationScore >= min_score
        ]

    def _atomic_write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        tmp_path = path.with_suffix(".json.tmp")
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
