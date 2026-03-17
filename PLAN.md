# PLAN.md — Project Dawn

_Strategic plan. Updated as of session M6 (2026-03-17). For concrete next steps see ACTIONPLAN.md._

---

## What We Are Building

A decentralized AI compute network where nodes cryptographically prove they ran inference,
reach consensus on results, and build durable reputation over time.

The core mechanism — **Proof-of-Logits** — lets peers verify that a node actually ran a model,
not fabricated output, without re-running inference themselves. This is the reason the project exists.
Everything else is infrastructure around it.

Above the compute marketplace, the network is designed to become self-governing and self-replicating:
agents spawn descendants when capability limits are reached, collectively determine the rules of the
network, and pursue novel capabilities autonomously. These properties are the architectural direction.
Phase 1 must be solid before Phase 2 begins.

---

## Architectural Layers

### Layer 1 — Tauri Shell (`src-tauri/`)
Desktop app host. Spawns and monitors the Python sidecar. Verifies sidecar SHA-256 before launch.
Monitors CPU/battery every 5 seconds. Writes `data/mesh/resource_state.json` to signal throttle
state. IPC with Python is intentionally file-based — do not replace with sockets.

### Layer 2 — Python Backend
Compute and networking core. Key modules:

| Module | Role | Status |
|---|---|---|
| `orchestrator.py` | Main work loop: fetch → compute → prove → broadcast → consensus | Core loop solid; DHT broadcast over real sockets pending |
| `compute.py` | Proof-of-Logits generation; `build_compute_handler()` factory | Done; synthetic + torch paths both work |
| `communication.py` | Gossip, handshakes, `AgentManifest` with lineage fields | Done; `parentId`/`generation` added |
| `discovery.py` | mDNS (local) + Kademlia DHT (network) peer discovery | DHT in-process verified; real-socket transport pending |
| `reputation.py` | Peer trust scoring with weighted-average merge and decay | Done; collusion-resistant merge implemented |
| `p2p/dht.py` | Kademlia DHT (K=20, α=3, SHA-256 node IDs) | Correct and tested in-process |
| `p2p/p2p_node.py` | WebSocket P2P node, message routing | `_handle_dht_rpc()` not yet implemented |
| `crypto/` | Ed25519 signing, X25519 key exchange, AES-GCM encryption | Done |
| `security/` | Trust levels, auth, peer validation, audit logging | Done; rate-limiter wired to WebSocket |
| `resilience/` | Rate limiting, circuit breakers, retry with backoff | Done and wired |
| `agents/sensing_agent.py` | Reads consensus + failed tasks, builds capability map | Done |

### Layer 3 — JavaScript Frontend (`frontend/`)
Local web dashboard. Reads state via WebSocket from Python and via `invoke()` from Tauri.
Shows peers, agents, feed events, resource state.

---

## Two Phases

### Phase 1 — A Working Node

A complete Phase 1 node:
1. Generates a stable identity from a PGP key
2. Discovers peers via mDNS locally and DHT over WAN
3. Receives a work unit, generates a Proof-of-Logits, signs with node key
4. Broadcasts proof via DHT to peers
5. Collects peer proofs, runs 2-of-3 consensus, writes receipt
6. Updates peer reputation after consensus
7. Throttles when Tauri signals high CPU or low battery

Steps 1–3 and 6–7 are solid. Step 4–5 (DHT over real sockets) is the primary remaining gap.

**Developer Alpha** = Phase 1 complete, run from source.
**Public Beta** = Phase 1 packaged as an installer on macOS/Linux/Windows.

### Phase 2 — A Living Mesh

Built on top of a verified Phase 1. Sequence:
1. **Sensing** — `SensingAgent` maps capability envelope from consensus + failed records ✅
2. **Lineage** — `AgentManifest` `parentId`/`generation`; `vault/lineage.json` genesis record ✅
3. **Seeds** — dormant agent blueprints with germination conditions and compute reserves
4. **Replication** — sensing agent triggers → candidate parents → variant seeds → germination → culling
5. **Governance** — reputation-weighted proposal/vote/rule propagation to all agents

Phase 2 items 1–2 are implemented. Items 3–5 are designed but not yet built.

---

## Key Design Decisions (Non-Negotiable)

| Decision | Rationale |
|---|---|
| File-based Rust↔Python IPC (`resource_state.json`) | Survives process restarts; no socket lifecycle management |
| Atomic writes everywhere (`tmp → fsync → rename`) | Continuous operation on consumer hardware; partial writes corrupt state |
| `synthetic_logits_provider` as default | Full proof pipeline testable without GPU or real model |
| Ed25519 / X25519 / AES-GCM crypto stack | Battle-tested; no dependency on TLS for P2P messages |
| PGP-anchored identity | Long-lived, portable, generates stable peer ID via SHA-256 |
| Logit fingerprint as heritable identity | Cryptographically traceable lineage chain between parent and child agents |
| 2-of-3 consensus | Simple majority; tolerates one Byzantine or offline peer per task |

---

## What Success Looks Like

**Now (Phase 1 in-progress):** `pytest -q` runs 336 tests, 5 skipped, 0 failures.
All core pipeline logic is tested in-process. Real-socket DHT is the primary gap.

**Developer Alpha:** Three nodes on separate machines (or separate Docker containers) run the
Proof-of-Logits loop continuously for 1 hour using `synthetic_logits_provider`. Consensus
receipts are written. No crashes. No data corruption. No false consensus.

**Public Beta:** Non-technical user installs via `.dmg`/`.deb`/`.msi`. Node self-configures,
finds peers, joins the mesh, processes tasks without manual intervention.

**v1.0:** Stable on consumer hardware across platforms. Public bootstrap nodes. Documentation
for end users. Phase 2 foundations present but not required.

---

## What We Are Not Building

- A centralized coordination server (nodes are peers, not clients of a hub)
- A continuous replication model (epochal evolution, not constant spawning)
- A separate governance system (reputation system and DHT gossip are the primitives; governance is built on them)
- Logit verification via re-running inference (that defeats the purpose; we verify proofs, not outputs)
