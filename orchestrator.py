"""
Orchestrator entry point for the Python logic core.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from crypto import NodeIdentity
from crypto.signing import (
    derive_peer_id_from_pgp_public_key_file,
    pgp_fingerprint_from_public_key_file,
    MessageSigner,
)
from data_paths import data_root
from compute import generate_proof_of_logits, persist_work_result, synthetic_logits_provider
from discovery import SovereignDiscovery
from reputation import ReputationManager
from communication import AgentGossip, AgentManifest

logger = logging.getLogger(__name__)

RESULT_TTL_SECONDS = 60 * 60
CONSENSUS_TTL_SECONDS = 60 * 60
PROCESSED_RETENTION_SECONDS = 24 * 60 * 60
HANDSHAKE_INTERVAL_SECONDS = 60.0
DHT_BACKOFF_MIN_SECONDS = 2.0
DHT_BACKOFF_MAX_SECONDS = 60.0
MAX_TASK_ATTEMPTS = 3
FETCH_CONCURRENCY = 5
REQUIRE_SIGNED_RESULTS = True

WorkUnit = Dict[str, Any]
ProofList = List[Dict[str, Any]]
ComputeHandler = Callable[[WorkUnit], ProofList]


class Orchestrator:
    def __init__(
        self,
        data_dir: Optional[Path] = None,
        pgp_public_key_path: Optional[Path] = None,
        compute_handler: Optional[ComputeHandler] = None,
        display_name: str = "Local Agent",
        mdns_port: Optional[int] = None,
        mdns_service_name: Optional[str] = None,
        enable_mdns: bool = True,
    ):
        self.data_dir = data_dir or data_root()
        self.vault_dir = self.data_dir / "vault"
        self.mesh_dir = self.data_dir / "mesh"
        self.outbox_dir = self.data_dir / "outbox"
        self.inbox_dir = self.mesh_dir / "inbox"
        self.resource_state_path = self.mesh_dir / "resource_state.json"
        self.peer_results_dir = self.mesh_dir / "peer_results"
        self.consensus_dir = self.mesh_dir / "consensus"
        self.failed_dir = self.mesh_dir / "failed"
        self.handshakes_path = self.mesh_dir / "handshakes.json"
        self.identity_key_path = self.vault_dir / "node_identity.key"
        self.processed_results_path = self.mesh_dir / "processed_results.json"
        self.task_attempts_path = self.mesh_dir / "task_attempts.json"

        for directory in (
            self.vault_dir,
            self.mesh_dir,
            self.outbox_dir,
            self.inbox_dir,
            self.peer_results_dir,
            self.consensus_dir,
            self.failed_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self.pgp_public_key_path = pgp_public_key_path or (self.vault_dir / "public_key.asc")
        self.peer_id = self._load_peer_id()
        self.pgp_fingerprint = pgp_fingerprint_from_public_key_file(self.pgp_public_key_path)
        self.identity = self._load_identity()
        self.discovery = SovereignDiscovery(identity=self.identity, data_dir=self.mesh_dir)
        self.reputation = ReputationManager(data_dir=self.mesh_dir)
        self.gossip = AgentGossip(self.discovery, self.reputation, data_dir=self.data_dir)
        self.display_name = display_name
        self.mdns_port = mdns_port
        self.mdns_service_name = mdns_service_name
        self.enable_mdns = enable_mdns

        self.compute_handler = compute_handler or self.default_compute_handler
        self._running = False
        self._last_throttled: Optional[bool] = None
        self._poll_jitter = 0.25
        self._dht_backoff = DHT_BACKOFF_MIN_SECONDS
        self._processed_results: Dict[str, set] = {}
        self._task_attempts: Dict[str, int] = {}
        self._handshakes: Dict[str, Dict[str, Any]] = {}
        self._last_handshake = 0.0

        self._ensure_manifest()
        self._load_persistent_state()

    def _load_peer_id(self) -> str:
        if not self.pgp_public_key_path.exists():
            raise FileNotFoundError(
                f"PGP public key not found at {self.pgp_public_key_path}"
            )
        return derive_peer_id_from_pgp_public_key_file(self.pgp_public_key_path)

    def _load_identity(self) -> NodeIdentity:
        if self.identity_key_path.exists():
            key_bytes = self.identity_key_path.read_bytes()
            if len(key_bytes) == 32:
                return NodeIdentity.from_private_key_bytes(key_bytes)

        identity = NodeIdentity()
        tmp_path = self.identity_key_path.with_suffix(".key.tmp")
        tmp_path.write_bytes(identity.serialize_private_key())
        tmp_path.replace(self.identity_key_path)
        return identity

    def _ensure_manifest(self) -> None:
        manifest = self.gossip.load_manifest()
        if manifest:
            return

        logit_fingerprint_path = self.vault_dir / "logit_fingerprint.txt"
        if logit_fingerprint_path.exists():
            logit_fingerprint = logit_fingerprint_path.read_text(encoding="utf-8").strip()
        else:
            logit_fingerprint = self._hash_string(self.peer_id)
            logit_fingerprint_path.write_text(f"{logit_fingerprint}\n", encoding="utf-8")

        manifest = AgentManifest(
            peerId=self.peer_id,
            pgpFingerprint=self.pgp_fingerprint,
            logitFingerprint=logit_fingerprint,
            displayName=self.display_name,
            createdAt=time.time(),
        )
        self.gossip.save_manifest(manifest)

    def start_discovery(self) -> None:
        if not self.enable_mdns:
            return
        self.discovery.start_mdns(service_name=self.mdns_service_name, port=self.mdns_port or 8000)

    def stop_discovery(self) -> None:
        self.discovery.stop_mdns()

    def fetch_work_unit(self) -> Optional[WorkUnit]:
        """
        Poll /data/mesh/inbox for the next work unit.
        """
        inbox_files = sorted(self.inbox_dir.glob("*.json"))
        if not inbox_files:
            return None

        work_path = inbox_files[0]
        payload = json.loads(work_path.read_text(encoding="utf-8"))
        work_path.unlink(missing_ok=True)
        return payload

    def is_work_unit_expired(self, work_unit: WorkUnit, now: Optional[float] = None) -> bool:
        expires_at = work_unit.get("expiresAt")
        if expires_at is None:
            return False
        try:
            expiry = float(expires_at)
        except (TypeError, ValueError):
            return False
        current = now or time.time()
        return current >= expiry

    def _load_persistent_state(self) -> None:
        self._processed_results = self._load_json_map(self.processed_results_path)
        self._task_attempts = self._load_json_map(self.task_attempts_path, value_type=int)
        self._handshakes = self._load_json_map(self.handshakes_path, value_type=dict)

    def _save_processed_results(self) -> None:
        serializable = {task_id: list(peers) for task_id, peers in self._processed_results.items()}
        self._write_json_atomic(self.processed_results_path, serializable)

    def _save_task_attempts(self) -> None:
        self._write_json_atomic(self.task_attempts_path, self._task_attempts)

    def _save_handshakes(self) -> None:
        self._write_json_atomic(self.handshakes_path, self._handshakes)

    @staticmethod
    def _load_json_map(path: Path, value_type: type = list) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        result: Dict[str, Any] = {}
        for key, value in payload.items():
            if value_type == int:
                try:
                    result[key] = int(value)
                except (TypeError, ValueError):
                    continue
            elif value_type == dict:
                if isinstance(value, dict):
                    result[key] = value
            else:
                result[key] = set(value) if isinstance(value, list) else value
        return result

    @staticmethod
    def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        tmp_path.replace(path)

    def validate_local_proof(self, proofs: ProofList) -> bool:
        return bool(proofs)

    def validate_peer_result(self, peer_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        2-out-of-3 consensus validation for peer results.
        """
        if len(peer_results) < 2:
            return {"accepted": False, "winners": [], "fingerprint": None}

        verified_results = []
        invalid_peers: List[str] = []
        for result in peer_results:
            peer_id = result.get("peerId")
            if not peer_id:
                continue
            verified = self._verify_peer_result(result)
            if verified or not REQUIRE_SIGNED_RESULTS:
                verified_results.append(result)
            else:
                invalid_peers.append(peer_id)

        for peer_id in invalid_peers:
            self.reputation.update_reputation(peer_id, is_successful=False, severe_failure=True)

        if len(verified_results) < 2:
            return {"accepted": False, "winners": [], "fingerprint": None}

        grouped: Dict[str, List[str]] = {}
        for result in verified_results:
            peer_id = result.get("peerId")
            proofs = result.get("proofOfLogits", [])
            if not peer_id or not proofs:
                continue
            fingerprint = self._proof_fingerprint(proofs)
            grouped.setdefault(fingerprint, []).append(peer_id)

        if not grouped:
            return {"accepted": False, "winners": [], "fingerprint": None}

        winning_hash, winners = max(grouped.items(), key=lambda item: len(item[1]))
        accepted = len(winners) >= 2

        for result in verified_results:
            peer_id = result.get("peerId")
            if not peer_id:
                continue
            is_winner = peer_id in winners
            self.reputation.update_reputation(
                peer_id,
                is_successful=accepted and is_winner,
                severe_failure=accepted and not is_winner,
            )

        self.gossip.emit_feed(
            {
                "type": "consensus",
                "peerId": self.peer_id,
                "status": "accepted" if accepted else "rejected",
                "timestamp": time.time(),
            }
        )
        return {"accepted": accepted, "winners": winners, "fingerprint": winning_hash}

    def process_work_unit(self, work_unit: WorkUnit, proofs: ProofList) -> Path:
        valid = self.validate_local_proof(proofs)
        requester_peer_id = work_unit.get("requesterPeerId")
        if requester_peer_id:
            self.reputation.update_reputation(
                requester_peer_id,
                is_successful=valid,
            )

        return persist_work_result(
            task_id=work_unit["taskId"],
            peer_id=self.peer_id,
            proofs=proofs,
            outbox_dir=self.outbox_dir,
            public_key=self.identity.serialize_public_key().hex(),
        )

    def submit_peer_result(self, task_id: str, peer_result: Dict[str, Any]) -> Path:
        target = self.peer_results_dir / f"{task_id}.jsonl"
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(peer_result, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
        return target

    async def broadcast_peer_result(self, task_id: str, peer_result: Dict[str, Any]) -> bool:
        self.submit_peer_result(task_id, peer_result)
        dht = self.discovery.get_dht()
        if not dht:
            return False
        peer_id = peer_result.get("peerId")
        if not peer_id:
            return False
        return await dht.store(f"result:{task_id}:{peer_id}", peer_result, ttl=RESULT_TTL_SECONDS)

    async def fetch_peer_results(self, task_id: str, peer_ids: List[str]) -> List[Dict[str, Any]]:
        dht = self.discovery.get_dht()
        if not dht:
            return []
        semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)
        results: List[Dict[str, Any]] = []

        async def fetch(peer_id: str) -> None:
            async with semaphore:
                payload = await dht.find_value(f"result:{task_id}:{peer_id}")
                if payload:
                    results.append(payload)

        await asyncio.gather(*(fetch(peer_id) for peer_id in peer_ids))
        return results

    async def broadcast_consensus_receipt(self, task_id: str, receipt: Dict[str, Any]) -> bool:
        dht = self.discovery.get_dht()
        if not dht:
            return False
        return await dht.store(f"consensus:{task_id}", receipt, ttl=CONSENSUS_TTL_SECONDS)

    def process_peer_results(self) -> List[Path]:
        processed: List[Path] = []
        for path in self.peer_results_dir.glob("*.jsonl"):
            lines = path.read_text(encoding="utf-8").splitlines()
            results = []
            for line in lines:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if len(results) < 3:
                continue
            consensus = self.validate_peer_result(results)
            receipt = {
                "taskId": path.stem,
                "accepted": consensus["accepted"],
                "winners": consensus["winners"],
                "fingerprint": consensus["fingerprint"],
                "timestamp": time.time(),
            }
            receipt_path = self.consensus_dir / f"{path.stem}.json"
            receipt_path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            processed.append(receipt_path)
            path.rename(path.with_suffix(".jsonl.processed"))
        return processed

    async def sync_peer_results_from_dht(self) -> None:
        dht = self.discovery.get_dht()
        if not dht:
            return
        peer_ids = self._known_peer_ids()
        if not peer_ids:
            return

        task_ids = set()
        task_ids.update(path.stem for path in self.peer_results_dir.glob("*.jsonl"))
        task_ids.update(path.stem for path in self.outbox_dir.glob("*.json"))

        try:
            for task_id in task_ids:
                results = await self.fetch_peer_results(task_id, peer_ids)
                for result in results:
                    peer_id = result.get("peerId")
                    if not peer_id or peer_id == self.peer_id:
                        continue
                    if self._is_duplicate_result(task_id, peer_id):
                        continue
                    self.submit_peer_result(task_id, result)
            self._dht_backoff = DHT_BACKOFF_MIN_SECONDS
        except Exception as exc:
            logger.warning(f"Failed to fetch peer results: {exc}")
            await asyncio.sleep(self._dht_backoff)
            self._dht_backoff = min(self._dht_backoff * 2, DHT_BACKOFF_MAX_SECONDS)

    async def _maybe_broadcast_handshake(self) -> None:
        if time.time() - self._last_handshake < HANDSHAKE_INTERVAL_SECONDS:
            return
        manifest = self.gossip.load_manifest()
        if not manifest:
            return
        sent = await self.gossip.broadcast_handshake(self.peer_id, manifest.logitFingerprint)
        if sent:
            self._last_handshake = time.time()

    async def sync_handshakes(self) -> None:
        peer_ids = [peer_id for peer_id in self._known_peer_ids() if peer_id and peer_id != self.peer_id]
        if not peer_ids:
            return
        for peer_id in peer_ids:
            handshake = await self.gossip.fetch_handshake(peer_id)
            if not handshake:
                continue
            if self._handshakes.get(peer_id) == handshake:
                continue
            self._handshakes[peer_id] = handshake
            self._save_handshakes()
            self.gossip.emit_feed(
                {
                    "type": "handshake",
                    "peerId": peer_id,
                    "status": "received",
                    "timestamp": time.time(),
                }
            )

    def _known_peer_ids(self) -> List[str]:
        records = self.discovery.list_peer_records()
        return [record.get("peerId") for record in records if record.get("peerId")]

    def _is_duplicate_result(self, task_id: str, peer_id: str) -> bool:
        seen = self._processed_results.setdefault(task_id, set())
        if peer_id in seen:
            return True
        seen.add(peer_id)
        self._save_processed_results()
        return False

    def _verify_peer_result(self, peer_result: Dict[str, Any]) -> bool:
        public_key_hex = peer_result.get("publicKey")
        proofs = peer_result.get("proofOfLogits", [])
        if not proofs:
            return False
        if not public_key_hex:
            return False
        try:
            public_key_bytes = bytes.fromhex(public_key_hex)
        except ValueError:
            return False

        for entry in proofs:
            if not self._verify_proof_signature(entry, public_key_bytes):
                return False
        return True

    @staticmethod
    def _verify_proof_signature(entry: Dict[str, Any], public_key_bytes: bytes) -> bool:
        signature_hex = entry.get("nodeSignature")
        if not signature_hex:
            return False
        try:
            signature = bytes.fromhex(signature_hex)
        except ValueError:
            return False
        payload = f"{entry.get('index')}:{entry.get('logitHash')}:{entry.get('timestamp')}".encode("utf-8")
        from crypto.signing import MessageSigner

        return MessageSigner.verify_with_public_key_bytes(payload, signature, public_key_bytes)

    def cleanup_stale_files(self) -> None:
        now = time.time()
        for path in self.peer_results_dir.glob("*.processed"):
            if now - path.stat().st_mtime > PROCESSED_RETENTION_SECONDS:
                path.unlink(missing_ok=True)
        for path in self.consensus_dir.glob("*.json"):
            if now - path.stat().st_mtime > CONSENSUS_TTL_SECONDS:
                path.unlink(missing_ok=True)
        active_tasks = set(path.stem for path in self.peer_results_dir.glob("*.jsonl"))
        active_tasks.update(path.stem for path in self.outbox_dir.glob("*.json"))
        if active_tasks:
            self._processed_results = {task_id: peers for task_id, peers in self._processed_results.items() if task_id in active_tasks}
            self._save_processed_results()

    def default_compute_handler(self, work_unit: WorkUnit) -> ProofList:
        input_blob = work_unit.get("inputBlob", {})
        input_tokens = input_blob.get("inputTokens")
        output_tokens = input_blob.get("outputTokens")
        if not isinstance(input_tokens, list) or not isinstance(output_tokens, list):
            raise ValueError("inputBlob.inputTokens and inputBlob.outputTokens are required")

        seed = int(input_blob.get("seed", 0))
        sample_rate = float(input_blob.get("sampleRate", 0.1))
        top_k = int(input_blob.get("topK", 5))

        signer = MessageSigner(self.identity)
        return generate_proof_of_logits(
            model=None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            sample_rate=sample_rate,
            top_k=top_k,
            seed=seed,
            logits_provider=synthetic_logits_provider(seed),
            signer=signer,
        )

    def generate_proof(
        self,
        model: Any,
        input_tokens: List[int],
        output_tokens: List[int],
        **kwargs: Any,
    ) -> ProofList:
        return generate_proof_of_logits(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            **kwargs,
        )

    async def run_once(self) -> Optional[Path]:
        if self._should_throttle():
            return None
        work_unit = self.fetch_work_unit()
        if not work_unit:
            return None
        if self.is_work_unit_expired(work_unit):
            self.gossip.emit_feed(
                {
                    "type": "task",
                    "peerId": self.peer_id,
                    "status": "expired",
                    "timestamp": time.time(),
                }
            )
            return None

        task_id = work_unit.get("taskId")
        if task_id:
            attempts = self._task_attempts.get(task_id, 0)
            if attempts >= MAX_TASK_ATTEMPTS:
                self._record_task_failure(task_id, work_unit, "max_attempts")
                return None

        try:
            proofs = self.compute_handler(work_unit)
        except Exception as exc:
            if task_id:
                self._task_attempts[task_id] = self._task_attempts.get(task_id, 0) + 1
                self._save_task_attempts()
                self._record_task_failure(task_id, work_unit, str(exc))
            return None
        result_path = self.process_work_unit(work_unit, proofs)

        peer_result = {
            "peerId": self.peer_id,
            "publicKey": self.identity.serialize_public_key().hex(),
            "proofOfLogits": proofs,
        }
        await self.broadcast_peer_result(work_unit["taskId"], peer_result)
        return result_path

    async def run(self, poll_interval: float = 5.0) -> None:
        self._running = True
        self.start_discovery()
        await self.gossip.broadcast_presence(
            peer_id=self.peer_id,
            status="online",
            capabilities=["compute", "proof-of-logits"],
        )
        try:
            while self._running:
                await self._maybe_broadcast_handshake()
                await self.run_once()
                await self.sync_peer_results_from_dht()
                await self.sync_handshakes()
                receipts = self.process_peer_results()
                for receipt_path in receipts:
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                    await self.broadcast_consensus_receipt(receipt["taskId"], receipt)
                self.cleanup_stale_files()
                jitter = 1 + random.uniform(0, self._poll_jitter)
                await asyncio.sleep(poll_interval * jitter)
        finally:
            self.stop_discovery()

    def stop(self) -> None:
        self._running = False

    def _record_task_failure(self, task_id: str, work_unit: WorkUnit, reason: str) -> None:
        payload = {
            "taskId": task_id,
            "reason": reason,
            "timestamp": time.time(),
            "workUnit": work_unit,
        }
        target = self.failed_dir / f"{task_id}.json"
        self._write_json_atomic(target, payload)

    def _should_throttle(self) -> bool:
        if not self.resource_state_path.exists():
            return False
        try:
            payload = json.loads(self.resource_state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False

        throttled = bool(payload.get("throttled", False))
        if throttled != self._last_throttled:
            self._last_throttled = throttled
            self.gossip.emit_feed(
                {
                    "type": "resource",
                    "peerId": self.peer_id,
                    "status": "throttled" if throttled else "stable",
                    "timestamp": time.time(),
                }
            )
        return throttled

    @staticmethod
    def _hash_string(value: str) -> str:
        import hashlib

        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _proof_fingerprint(proofs: ProofList) -> str:
        import hashlib

        normalized = sorted(
            ((entry.get("index"), entry.get("logitHash")) for entry in proofs),
            key=lambda pair: pair[0],
        )
        payload = "|".join(f"{index}:{logit}" for index, logit in normalized)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
