import random

from compute import generate_proof_of_logits


def _fake_logits_provider(context_tokens, step_index):
    base = sum(context_tokens) + step_index
    return [float(base + i) for i in range(10)]


def _expected_indices(total, sample_rate, seed):
    rng = random.Random(seed)
    count = max(1, int(total * sample_rate))
    indices = rng.sample(range(total), k=min(count, total))
    indices.sort()
    return indices


def test_generate_proof_of_logits_is_deterministic():
    input_tokens = [1, 2, 3]
    output_tokens = list(range(10))
    sample_rate = 0.2
    seed = 42
    timestamp = 1700000000000

    proof_a = generate_proof_of_logits(
        model=None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        sample_rate=sample_rate,
        top_k=3,
        seed=seed,
        timestamp=timestamp,
        logits_provider=_fake_logits_provider,
    )
    proof_b = generate_proof_of_logits(
        model=None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        sample_rate=sample_rate,
        top_k=3,
        seed=seed,
        timestamp=timestamp,
        logits_provider=_fake_logits_provider,
    )

    assert proof_a == proof_b
    expected_indices = _expected_indices(len(output_tokens), sample_rate, seed)
    assert [entry["index"] for entry in proof_a] == expected_indices
    assert all(entry["nodeSignature"] == "" for entry in proof_a)
