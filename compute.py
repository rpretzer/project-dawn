"""
Compute module for inference and Proof-of-Logits generation.
"""

from __future__ import annotations

import hashlib
import importlib
import random
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import json
import os

from crypto.signing import MessageSigner
from data_paths import data_root


LogitsProvider = Callable[[Sequence[int], int], Iterable[float]]


@dataclass(frozen=True)
class ProofOfLogitsEntry:
    index: int
    logitHash: str
    timestamp: int
    nodeSignature: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "logitHash": self.logitHash,
            "timestamp": self.timestamp,
            "nodeSignature": self.nodeSignature,
        }


def _select_challenge_indices(
    output_tokens: Sequence[int],
    sample_rate: float,
    seed: int,
) -> List[int]:
    if not output_tokens:
        return []
    if not (0 < sample_rate <= 1):
        raise ValueError("sample_rate must be between 0 and 1")

    total = len(output_tokens)
    sample_count = max(1, int(total * sample_rate))
    rng = random.Random(seed)
    indices = rng.sample(range(total), k=min(sample_count, total))
    indices.sort()
    return indices


def _logits_to_hash(logits: Iterable[float], top_k: int) -> str:
    values = list(logits)
    if not values:
        raise ValueError("logits must contain at least one value")
    if top_k <= 0:
        raise ValueError("top_k must be >= 1")

    values.sort(reverse=True)
    top_values = values[: min(top_k, len(values))]
    packed = struct.pack(f"!{len(top_values)}d", *top_values)
    return hashlib.sha256(packed).hexdigest()


def _default_logits_provider(model: Any) -> LogitsProvider:
    def provider(context_tokens: Sequence[int], _step_index: int) -> Iterable[float]:
        torch = importlib.import_module("torch")

        with torch.no_grad():
            token_tensor = torch.tensor([list(context_tokens)])
            logits = model(token_tensor).logits[0, -1]
            return logits.cpu().numpy().tolist()

    return provider


def synthetic_logits_provider(seed: int = 0, width: int = 64) -> LogitsProvider:
    """
    Deterministic logits provider derived from token context only.
    """
    def provider(context_tokens: Sequence[int], step_index: int) -> Iterable[float]:
        hasher = hashlib.sha256()
        hasher.update(str(seed).encode("utf-8"))
        hasher.update(str(step_index).encode("utf-8"))
        for token in context_tokens:
            hasher.update(str(token).encode("utf-8"))
        digest = hasher.digest()
        values = []
        for i in range(width):
            idx = i % len(digest)
            values.append((digest[idx] / 255.0) * 10.0)
        return values

    return provider


def generate_proof_of_logits(
    model: Any,
    input_tokens: Sequence[int],
    output_tokens: Sequence[int],
    sample_rate: float = 0.1,
    top_k: int = 5,
    seed: int = 0,
    signer: Optional[MessageSigner] = None,
    timestamp: Optional[int] = None,
    logits_provider: Optional[LogitsProvider] = None,
) -> List[Dict[str, Any]]:
    """
    Generate Proof-of-Logits entries for selected output token indices.

    Returns a list of dicts that match the ProofOfLogits schema:
    index, logitHash, timestamp, nodeSignature.
    """
    timestamp_ms = int(time.time() * 1000) if timestamp is None else int(timestamp)
    indices = _select_challenge_indices(output_tokens, sample_rate, seed)
    if logits_provider is None:
        logits_provider = _default_logits_provider(model)

    proofs: List[ProofOfLogitsEntry] = []
    input_list = list(input_tokens)
    output_list = list(output_tokens)

    for idx in indices:
        context = input_list + output_list[:idx]
        logits = logits_provider(context, idx)
        logit_hash = _logits_to_hash(logits, top_k)
        signature_payload = f"{idx}:{logit_hash}:{timestamp_ms}".encode("utf-8")
        node_signature = signer.sign(signature_payload).hex() if signer else ""
        proofs.append(
            ProofOfLogitsEntry(
                index=idx,
                logitHash=logit_hash,
                timestamp=timestamp_ms,
                nodeSignature=node_signature,
            )
        )

    return [entry.to_dict() for entry in proofs]


def wrap_work_result(
    task_id: str,
    peer_id: str,
    proofs: List[Dict[str, Any]],
    public_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Wrap Proof-of-Logits entries with task and peer metadata before broadcast.
    """
    if not task_id:
        raise ValueError("task_id is required")
    if not peer_id:
        raise ValueError("peer_id is required")
    payload = {
        "taskId": task_id,
        "peerId": peer_id,
        "proofOfLogits": proofs,
    }
    if public_key:
        payload["publicKey"] = public_key
    return payload


def persist_work_result(
    task_id: str,
    peer_id: str,
    proofs: List[Dict[str, Any]],
    outbox_dir: Optional[Path] = None,
    public_key: Optional[str] = None,
) -> Path:
    """
    Persist Proof-of-Logits output to /data/outbox/[taskId].json.
    """
    target_dir = outbox_dir or data_root() / "outbox"
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = wrap_work_result(task_id, peer_id, proofs, public_key=public_key)

    file_path = target_dir / f"{task_id}.json"
    tmp_path = file_path.with_suffix(".json.tmp")
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(data)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(tmp_path, file_path)
    return file_path
