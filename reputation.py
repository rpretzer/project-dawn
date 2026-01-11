"""
Reputation manager for sovereign peer trust scoring.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_paths import data_root

logger = logging.getLogger(__name__)

DECAY_WINDOW_SECONDS = 30 * 24 * 60 * 60


@dataclass
class PeerReputation:
    peerId: str
    reputationScore: float = 0.1
    uptime: float = 0.0
    lastVerified: float = 0.0
    successes: int = 0
    failures: int = 0
    consecutiveFailures: int = 0
    totalComputeMs: int = 0
    lastSeen: float = 0.0
    lastDecay: float = 0.0
    blacklisted: bool = False

    def to_peer_node(self) -> Dict[str, Any]:
        return {
            "peerId": self.peerId,
            "reputationScore": self.reputationScore,
            "uptime": self.uptime,
            "lastVerified": self.lastVerified,
        }


class ReputationManager:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or data_root() / "mesh"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reputation_path = self.data_dir / "reputation.json"
        self._records: Dict[str, PeerReputation] = {}
        self._load()

    def _load(self) -> None:
        if not self.reputation_path.exists():
            return
        try:
            payload = json.loads(self.reputation_path.read_text(encoding="utf-8"))
            for item in payload.get("peers", []):
                record = PeerReputation(**item)
                self._records[record.peerId] = record
        except Exception as exc:
            logger.warning(f"Failed to load reputation cache: {exc}")

    def _save(self) -> None:
        payload = {
            "version": 1,
            "peers": [asdict(record) for record in self._records.values()],
        }
        tmp_path = self.reputation_path.with_suffix(".json.tmp")
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, self.reputation_path)

    def get_peer(self, peer_id: str) -> Optional[PeerReputation]:
        return self._records.get(peer_id)

    def record_peer(
        self,
        peer_id: str,
        reputation_score: float = 0.1,
        uptime: float = 0.0,
        last_verified: Optional[float] = None,
        last_seen: Optional[float] = None,
    ) -> PeerReputation:
        now = time.time()
        record = self._records.get(peer_id)
        if record is None:
            record = PeerReputation(peerId=peer_id)
            self._records[peer_id] = record

        record.reputationScore = reputation_score
        record.uptime = uptime
        record.lastVerified = last_verified or now
        record.lastSeen = last_seen or now
        record.lastDecay = record.lastDecay or record.lastVerified
        self._save()
        return record

    def apply_decay(self, now: Optional[float] = None, decay_factor: float = 0.95) -> None:
        current = now or time.time()
        for record in self._records.values():
            if record.blacklisted:
                continue
            last_decay = record.lastDecay or record.lastVerified or current
            if current - last_decay < DECAY_WINDOW_SECONDS:
                continue
            periods = int((current - last_decay) // DECAY_WINDOW_SECONDS)
            record.reputationScore *= decay_factor ** periods
            record.lastDecay = last_decay + periods * DECAY_WINDOW_SECONDS
        self._save()

    def update_reputation(
        self,
        peer_id: str,
        is_successful: bool,
        compute_ms: int = 0,
        verified_at: Optional[float] = None,
        severe_failure: bool = False,
    ) -> PeerReputation:
        now = verified_at or time.time()
        record = self._records.get(peer_id) or PeerReputation(peerId=peer_id)

        if is_successful:
            record.successes += 1
            record.consecutiveFailures = 0
            record.totalComputeMs += max(0, int(compute_ms))
        else:
            record.failures += 1
            record.consecutiveFailures += 1

        total = record.successes + record.failures
        base_score = record.successes / total if total else 0.1
        volume_bonus = min(record.successes / 100.0, 0.2)
        record.reputationScore = min(base_score + volume_bonus, 1.0)

        if not is_successful:
            record.reputationScore *= 0.5
        if severe_failure:
            record.reputationScore = min(record.reputationScore, 0.1)
        if record.consecutiveFailures >= 3:
            record.blacklisted = True
            record.reputationScore = min(record.reputationScore, 0.1)

        record.lastVerified = now
        record.lastSeen = now
        record.lastDecay = record.lastDecay or now
        self._records[peer_id] = record
        self._save()
        return record

    def sync_reputation(self, peer_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Update local trust scores based on peer data from the mesh.
        """
        now = time.time()
        for node in peer_nodes:
            peer_id = node.get("peerId")
            if not peer_id:
                continue
            record = self._records.get(peer_id) or PeerReputation(peerId=peer_id)
            incoming_score = float(node.get("reputationScore", record.reputationScore))
            record.reputationScore = max(record.reputationScore, incoming_score)
            record.uptime = max(record.uptime, float(node.get("uptime", record.uptime)))
            record.lastVerified = max(record.lastVerified, float(node.get("lastVerified", record.lastVerified)))
            record.lastSeen = now
            record.lastDecay = record.lastDecay or record.lastVerified or now
            self._records[peer_id] = record

        self.apply_decay(now=now)
        return self.list_peer_nodes()

    def list_peer_nodes(self) -> List[Dict[str, Any]]:
        return [record.to_peer_node() for record in self._records.values()]
