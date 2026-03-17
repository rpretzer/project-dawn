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


def build_compute_handler(
    logits_provider_name: str = "synthetic",
    model_path: str = "",
    seed: int = 0,
    sample_rate: float = 0.1,
    top_k: int = 5,
) -> "Callable[[Dict[str, Any]], List[Dict[str, Any]]]":
    """
    Return a compute handler function suitable for Orchestrator(compute_handler=…).

    Args:
        logits_provider_name: ``"synthetic"`` or ``"torch"``.
        model_path: Path to a HuggingFace-compatible model directory.
                    Required (and used) only when *logits_provider_name* is ``"torch"``.
        seed:        RNG seed for challenge-index selection (and synthetic logits).
        sample_rate: Fraction of output tokens to sample for proof (0 < x ≤ 1).
        top_k:       Number of top logit values to hash per sampled position.

    Returns:
        A callable ``(work_unit) -> proofs`` that the Orchestrator can use directly.

    Raises:
        ValueError: if *logits_provider_name* is not a recognised provider.
        ImportError: if ``"torch"`` is requested but PyTorch is not installed.
        FileNotFoundError: if ``"torch"`` is requested and *model_path* is missing or empty.
    """
    provider_name = logits_provider_name.lower()

    if provider_name == "synthetic":
        _logits_provider: Optional[LogitsProvider] = None  # resolved per work-unit below
        _model: Any = None

        def _synthetic_handler(work_unit: Dict[str, Any]) -> List[Dict[str, Any]]:
            input_blob = work_unit.get("inputBlob", {})
            input_tokens = input_blob.get("inputTokens")
            output_tokens = input_blob.get("outputTokens")
            if not isinstance(input_tokens, list) or not isinstance(output_tokens, list):
                raise ValueError("inputBlob.inputTokens and inputBlob.outputTokens are required")
            unit_seed = int(input_blob.get("seed", seed))
            unit_rate = float(input_blob.get("sampleRate", sample_rate))
            unit_top_k = int(input_blob.get("topK", top_k))
            return generate_proof_of_logits(
                model=None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                sample_rate=unit_rate,
                top_k=unit_top_k,
                seed=unit_seed,
                logits_provider=synthetic_logits_provider(unit_seed),
            )

        return _synthetic_handler  # type: ignore[return-value]

    if provider_name == "torch":
        if not model_path:
            raise FileNotFoundError(
                "logits_provider=torch requires a non-empty model_path"
            )
        model_dir = Path(model_path)
        if not model_dir.exists():
            raise FileNotFoundError(f"model_path does not exist: {model_path}")

        try:
            import importlib as _importlib
            _torch = _importlib.import_module("torch")
            _transformers = _importlib.import_module("transformers")
        except ImportError as exc:
            raise ImportError(
                "logits_provider=torch requires PyTorch and transformers to be installed"
            ) from exc

        _model = _transformers.AutoModelForCausalLM.from_pretrained(
            str(model_dir), torch_dtype=_torch.float32
        )
        _model.eval()
        _torch_logits_provider = _default_logits_provider(_model)

        def _torch_handler(work_unit: Dict[str, Any]) -> List[Dict[str, Any]]:
            input_blob = work_unit.get("inputBlob", {})
            input_tokens = input_blob.get("inputTokens")
            output_tokens = input_blob.get("outputTokens")
            if not isinstance(input_tokens, list) or not isinstance(output_tokens, list):
                raise ValueError("inputBlob.inputTokens and inputBlob.outputTokens are required")
            unit_seed = int(input_blob.get("seed", seed))
            unit_rate = float(input_blob.get("sampleRate", sample_rate))
            unit_top_k = int(input_blob.get("topK", top_k))
            return generate_proof_of_logits(
                model=_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                sample_rate=unit_rate,
                top_k=unit_top_k,
                seed=unit_seed,
                logits_provider=_torch_logits_provider,
            )

        return _torch_handler  # type: ignore[return-value]

    raise ValueError(
        f"Unknown logits_provider '{logits_provider_name}'. Choose 'synthetic' or 'torch'."
    )


def generate_action_proof(
    task_id: str,
    tool_name: str,
    result: Any,
    signer: "MessageSigner",
) -> Dict[str, Any]:
    """
    Generate a signed proof for an agentic tool-call result.

    Unlike Proof-of-Logits (which attests to logit values at sampled token
    positions), an action proof attests to the *outcome* of a tool call:

        payload = "<taskId>:<toolName>:<json-sorted-result>"
        resultHash = sha256(payload)
        nodeSignature = Ed25519.sign(payload)

    Two peers independently running the same deterministic tool on the same
    task should produce identical resultHashes.  The 2-of-3 consensus check
    compares resultHashes the same way it compares logitHashes.
    """
    result_json = json.dumps(result, sort_keys=True, separators=(",", ":"))
    payload = f"{task_id}:{tool_name}:{result_json}"
    payload_bytes = payload.encode("utf-8")
    result_hash = hashlib.sha256(payload_bytes).hexdigest()
    signature = signer.sign(payload_bytes)
    return {
        "taskId": task_id,
        "proofType": "action",
        "tool": tool_name,
        "resultHash": result_hash,
        "nodeSignature": signature.hex(),
        "timestamp": int(time.time()),
    }


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
