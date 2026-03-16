"""
Tests for compute.build_compute_handler() and the compute config section.

All tests run without PyTorch / real models by using the synthetic provider.
"""

from __future__ import annotations

import json
import os
import pytest

from compute import build_compute_handler, synthetic_logits_provider, generate_proof_of_logits
from config.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_work_unit(seed: int = 0, sample_rate: float = 1.0, top_k: int = 5) -> dict:
    return {
        "taskId": "test-task",
        "inputBlob": {
            "inputTokens": [1, 2, 3],
            "outputTokens": [4, 5, 6],
            "seed": seed,
            "sampleRate": sample_rate,
            "topK": top_k,
        },
    }


# ---------------------------------------------------------------------------
# build_compute_handler — synthetic provider
# ---------------------------------------------------------------------------


def test_synthetic_handler_returns_proofs():
    handler = build_compute_handler(logits_provider_name="synthetic")
    proofs = handler(_minimal_work_unit())
    assert isinstance(proofs, list)
    assert proofs, "synthetic handler must return at least one proof"


def test_synthetic_handler_proof_fields():
    handler = build_compute_handler(logits_provider_name="synthetic")
    proofs = handler(_minimal_work_unit())
    for entry in proofs:
        assert "index" in entry
        assert "logitHash" in entry
        assert "timestamp" in entry
        assert "nodeSignature" in entry


def test_synthetic_handler_unsigned_when_no_signer():
    """build_compute_handler(synthetic) produces empty signatures — no signer is passed."""
    handler = build_compute_handler(logits_provider_name="synthetic")
    proofs = handler(_minimal_work_unit())
    for entry in proofs:
        assert entry["nodeSignature"] == "", "no signer → nodeSignature must be empty string"


def test_synthetic_handler_deterministic():
    handler = build_compute_handler(logits_provider_name="synthetic", seed=7)
    unit = _minimal_work_unit(seed=7)
    proofs_a = handler(unit)
    proofs_b = handler(unit)
    # logit hashes must be identical across calls (determinism)
    hashes_a = [e["logitHash"] for e in proofs_a]
    hashes_b = [e["logitHash"] for e in proofs_b]
    assert hashes_a == hashes_b


def test_synthetic_handler_seed_changes_hashes():
    handler = build_compute_handler(logits_provider_name="synthetic")
    proofs_seed_0 = handler(_minimal_work_unit(seed=0))
    proofs_seed_1 = handler(_minimal_work_unit(seed=1))
    hashes_0 = {e["logitHash"] for e in proofs_seed_0}
    hashes_1 = {e["logitHash"] for e in proofs_seed_1}
    assert hashes_0 != hashes_1, "different seeds must produce different logit hashes"


def test_synthetic_handler_work_unit_params_override_defaults():
    """sampleRate and topK in the work unit should override factory defaults."""
    # Default: sample_rate=0.1 on 3 output tokens → 1 sample
    handler_default = build_compute_handler(logits_provider_name="synthetic", sample_rate=0.1)
    proofs_sparse = handler_default(_minimal_work_unit(sample_rate=0.1))

    # Override to 100% coverage
    proofs_full = handler_default(_minimal_work_unit(sample_rate=1.0))

    # Full coverage must produce more (or equal) proof entries
    assert len(proofs_full) >= len(proofs_sparse)


def test_synthetic_handler_missing_input_blob_raises():
    handler = build_compute_handler(logits_provider_name="synthetic")
    with pytest.raises(ValueError):
        handler({"taskId": "bad", "inputBlob": {}})


# ---------------------------------------------------------------------------
# build_compute_handler — error cases
# ---------------------------------------------------------------------------


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown logits_provider"):
        build_compute_handler(logits_provider_name="magic")


def test_torch_without_model_path_raises():
    with pytest.raises(FileNotFoundError, match="model_path"):
        build_compute_handler(logits_provider_name="torch", model_path="")


def test_torch_with_nonexistent_model_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_compute_handler(
            logits_provider_name="torch",
            model_path=str(tmp_path / "does_not_exist"),
        )


def test_torch_without_pytorch_raises(tmp_path, monkeypatch):
    """If torch is not installed, build_compute_handler(torch) must raise ImportError."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name in ("torch", "transformers"):
            raise ImportError(f"Mocked: {name} not available")
        return real_import(name, *args, **kwargs)

    # Create a fake model directory so the path-exists check passes.
    model_dir = tmp_path / "fake_model"
    model_dir.mkdir()

    monkeypatch.setattr(builtins, "__import__", mock_import)
    with pytest.raises(ImportError, match="PyTorch and transformers"):
        build_compute_handler(logits_provider_name="torch", model_path=str(model_dir))


# ---------------------------------------------------------------------------
# Config.compute section
# ---------------------------------------------------------------------------


def test_config_compute_defaults():
    cfg = Config()
    assert cfg.compute["logits_provider"] == "synthetic"
    assert cfg.compute["model_path"] == ""
    assert cfg.compute["seed"] == 0
    assert 0 < cfg.compute["sample_rate"] <= 1.0
    assert cfg.compute["top_k"] >= 1


def test_config_compute_override_via_dict():
    cfg = Config(config_data={"compute": {"logits_provider": "synthetic", "seed": 42, "top_k": 10}})
    assert cfg.compute["seed"] == 42
    assert cfg.compute["top_k"] == 10


def test_config_validate_rejects_bad_provider():
    cfg = Config(config_data={"compute": {"logits_provider": "magic"}})
    cfg.validate()
    assert cfg.compute["logits_provider"] == "synthetic"


def test_config_validate_rejects_bad_sample_rate():
    cfg = Config(config_data={"compute": {"sample_rate": -0.5}})
    cfg.validate()
    assert cfg.compute["sample_rate"] == 0.1


def test_config_validate_rejects_zero_top_k():
    cfg = Config(config_data={"compute": {"top_k": 0}})
    cfg.validate()
    assert cfg.compute["top_k"] == 5


def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("PROJECT_DAWN_LOGITS_PROVIDER", "synthetic")
    monkeypatch.setenv("PROJECT_DAWN_COMPUTE_SEED", "99")
    monkeypatch.setenv("PROJECT_DAWN_SAMPLE_RATE", "0.5")
    monkeypatch.setenv("PROJECT_DAWN_TOP_K", "3")
    cfg = Config()
    assert cfg.compute["logits_provider"] == "synthetic"
    assert cfg.compute["seed"] == 99
    assert cfg.compute["sample_rate"] == 0.5
    assert cfg.compute["top_k"] == 3


def test_config_to_dict_includes_compute():
    cfg = Config()
    d = cfg.to_dict()
    assert "compute" in d
    assert "logits_provider" in d["compute"]


# ---------------------------------------------------------------------------
# Integration: Config → build_compute_handler → proofs
# ---------------------------------------------------------------------------


def test_config_wired_to_handler_produces_valid_proofs():
    """
    The pattern used in server_p2p.py: read config, call build_compute_handler,
    run the handler on a work unit, get proofs back.
    """
    cfg = Config(config_data={
        "compute": {
            "logits_provider": "synthetic",
            "seed": 5,
            "sample_rate": 1.0,
            "top_k": 3,
        }
    })
    cfg.validate()

    handler = build_compute_handler(
        logits_provider_name=cfg.compute["logits_provider"],
        model_path=cfg.compute["model_path"],
        seed=cfg.compute["seed"],
        sample_rate=cfg.compute["sample_rate"],
        top_k=cfg.compute["top_k"],
    )
    work_unit = {
        "taskId": "cfg-integration",
        "inputBlob": {
            "inputTokens": [10, 20],
            "outputTokens": [30, 40, 50],
        },
    }
    proofs = handler(work_unit)
    assert proofs
    for entry in proofs:
        assert entry["logitHash"]
        assert isinstance(entry["index"], int)
