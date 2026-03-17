# Inference Architecture

How Project Dawn runs inference on CPU-class hardware, what the math looks like,
and why the Proof-of-Logits mechanism works in this context.

---

## Why CPU Inference Is Viable

A transformer has two cost drivers:

- **FLOPs** — matrix multiplications inside each attention layer and FFN. GPUs win here.
- **Memory bandwidth** — loading weight matrices from RAM on every forward pass.
  CPUs are competitive for small models because the weights fit in L3 cache.

With 4-bit quantization (GGUF format, run via llama.cpp), realistic numbers on a
modern laptop CPU:

| Model | RAM required | Throughput |
|---|---|---|
| SmolLM2-135M Q4 | ~80 MB | ~400 tokens/sec |
| Qwen2.5-0.5B Q4 | ~300 MB | ~150 tokens/sec |
| TinyLlama-1.1B Q4 | ~700 MB | ~80 tokens/sec |

A micro inference transaction — 128-token input, 32-token output — at 150 t/s takes
**~200ms**. That is fast enough to be economically real.

---

## What Happens Inside One Inference Step

Each transformer layer computes:

```
x  →  LayerNorm
   →  Attention(Q, K, V)  →  residual add
   →  LayerNorm
   →  FFN                 →  residual add
   →  x_next
```

The attention step dominates cost. For hidden dimension `d` and sequence length `s`:

```
Q = x · W_Q        # [s, d] × [d, d]  →  [s, d]
K = x · W_K
V = x · W_V
scores = Q · Kᵀ / √d    # [s, s]  — O(s²) — the quadratic scaling term
attn   = softmax(scores) · V
```

The FFN is two large matrix multiplies:

```
h = ReLU(x · W_1)    # expand to 4×d
y =  h · W_2         # project back to d
```

After `L` layers, the final hidden state passes through the language-model head:

```
logits = x_final · W_vocab    # [s, d] × [d, vocab_size]  →  [s, vocab_size]
```

`logits[position, token_id]` is the un-normalized score for every token in the
vocabulary at that sequence position. Softmax converts these to probabilities.

**This is what the Proof-of-Logits hashes**: the raw top-k values before sampling,
at deterministically sampled positions. Given the same model weights and the same
input, the logit values are identical on every node — that determinism is the basis
of the consensus check.

---

## Pipeline Parallelism (Splitting a Large Model Across Nodes)

If a model is too large for a single node, divide it by layers. For a 12-layer
model split across 3 nodes:

```
Node A:  layers 0–3   →  hidden state h_A   [seq_len × hidden_dim]
Node B:  layers 4–7   →  hidden state h_B
Node C:  layers 8–11  →  hidden state h_C  →  lm_head  →  logits
```

The only data crossing node boundaries is the **hidden state tensor**:

```
seq_len × hidden_dim × bytes_per_float
= 512 tokens × 2048 dim × 2 bytes (fp16)
≈ 2 MB per inter-node transfer
```

Execution is sequential: Node B cannot start until Node A finishes. Latency
compounds across stages.

### Proof chain under pipeline parallelism

```
Node A signs:  sha256(h_A)           →  proof_A
Node B signs:  sha256(h_A ‖ h_B)    →  proof_B   (chains to A's output)
Node C signs:  sha256(logit_sample)  →  proof_C
```

This produces a **cryptographic chain of custody** over the full computation:
each stage attests to its input and output. Peers can verify any segment without
re-running the stages before it, as long as the signed intermediate outputs are
available.

The problem: if any node cheats, finding the break requires checking the chain
segment by segment.

---

## Tensor Parallelism (Parallel Sharding of Each Layer)

Instead of splitting by layers (sequential), split each weight matrix across nodes
and compute in parallel:

```
W_Q sharded column-wise across N nodes:
  Node i computes:  Q_i = x · W_Q[:, shard_i]

All nodes all-reduce (sum):
  Q = concat(Q_1, Q_2, ..., Q_N)
```

Every node participates in every layer simultaneously. This is how production LLM
serving clusters work (Megatron-LM, etc.). Latency stays flat regardless of depth,
but it requires an all-reduce synchronization barrier on every attention layer.

Over a WebSocket LAN transport with ~1ms round-trip, the synchronization cost would
dominate. Tensor parallelism is not appropriate for Project Dawn's transport layer.

---

## The Right Architecture for This Network

Neither pipeline nor tensor parallelism is the right model for Project Dawn.
The network has a fundamentally different shape:

```
Task arrives at 3 nodes simultaneously (via DHT broadcast)

Node A: runs SmolLM2-135M on input  →  logits_A  →  hash_A  →  sig_A
Node B: runs SmolLM2-135M on input  →  logits_B  →  hash_B  →  sig_B
Node C: runs SmolLM2-135M on input  →  logits_C  →  hash_C  →  sig_C

Consensus: hash_A == hash_B == hash_C  (deterministic given identical weights + input)
```

Each node runs **full independent inference** on a small model. The Proof-of-Logits
guarantee is: *I ran this specific model on this specific input — here is a signed
hash of my top-k logits at these sampled positions*.

The "split" that makes sense here is **task decomposition**, not model parallelism:

- Long context → split into chunks; each node handles a chunk independently
- Large batch → distribute tasks across nodes; each handles a subset
- Each micro-transaction is sized to be fast on CPU: 128-token input, 32-token output

---

## The Model Fingerprint and Consensus Compatibility

The `logit_fingerprint` in `vault/logit_fingerprint.txt` and `manifest.json` is a
stable signature of a specific model's behaviour on a fixed benchmark input. It is
generated once at node genesis and does not change.

Two nodes with **matching fingerprints** run the same model and will produce matching
logit hashes for the same task. Two nodes with **different fingerprints** are running
different models and will never agree on logit hashes — they should not be in the
same consensus group.

This has a direct implication for the sensing agent's capability map: regions of
the task-embedding space are not just typed by task kind but by the fingerprint of
the model required to serve them. Routing a task to a node with a mismatched
fingerprint produces guaranteed consensus failure, which is correctly recorded as a
failure in `data/mesh/failed/` and feeds back into evolutionary pressure detection.

---

## Wiring Real Inference (Ollama Path)

When Ollama is available (`ollama list` returns models), the compute handler can
be replaced with a real logits provider:

```python
# compute.py — planned ollama_logits_provider
POST /api/generate
{
  "model": "smollm2:135m",
  "prompt": "<tokens>",
  "options": {"logprobs": true, "top_k": 5}
}
# response includes per-token logprob arrays
# extract top-k at sampled positions → same output shape as synthetic provider
```

Ollama runs quantized models on CPU with no GPU required. SmolLM2-135M at Q4 is
the recommended starting point: small enough to be fast, real enough to produce
meaningful logit distributions.

The synthetic provider (`synthetic_logits_provider`) remains the fallback for
development and testing. It produces deterministic logit-shaped data that exercises
the full proof generation, signing, broadcast, and consensus pipeline without
requiring a model on disk.

---

## Summary

| Approach | Latency | Coordination | Right for Dawn? |
|---|---|---|---|
| Pipeline parallelism | Additive (stage × latency) | Sequential hand-off | Only for models > single-node RAM |
| Tensor parallelism | Flat (+ all-reduce cost) | All-reduce per layer | No — sync cost too high over WS |
| Independent full inference | Per-node model latency | None (async broadcast) | **Yes — primary architecture** |
| Task decomposition | Chunk latency | DHT task routing | Yes — for long contexts |

The primary model is independent full inference on a tiny quantized model per node,
with the Proof-of-Logits providing cryptographic evidence of honest computation.
Pipeline parallelism is reserved for future capability expansion where task
complexity demands a larger model than any single node can serve alone.
