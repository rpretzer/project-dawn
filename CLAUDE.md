# CLAUDE.md — Project Dawn

## What This Project Is

Project Dawn is a **decentralized AI compute network** designed to become a living, self-governing
mesh of agents. The foundation: nodes run AI inference, cryptographically prove they did it, reach
consensus on results, and build reputation over time — all packaged as a resource-aware desktop
application.

The core differentiator is **Proof-of-Logits**: a mechanism to verify that a node actually ran
inference on a real model, not fabricated output. At selected token positions, the node hashes the
top-k logit values and signs the hash with its private key. Peers can then verify the proof without
re-running inference. Results are accepted via 2-of-3 consensus across peers.

This idea is novel and worth completing. It is the reason the project exists.

The compute marketplace is the foundation layer, not the ceiling. Above it, Project Dawn is
designed for three emergent properties:

- **Self-replication** — agents spawn descendant agents when the network reaches capability limits,
  funded by earned compute credits, seeded with heritable identity and values
- **Self-governance** — agents collectively determine the rules of the network through
  reputation-weighted consensus; those rules are inherited by all future agents
- **Innovation** — agents pursue novel capabilities autonomously (new protocols, art, knowledge,
  ethics) not because they are instructed to, but because exploring the capability frontier is how
  the network senses and prepares for what it cannot yet do

These properties do not exist yet. They are the architectural direction. Everything built now
should be compatible with them.

---

## Architecture

The system has three distinct layers. Respect the boundaries between them.

### 1. Rust / Tauri Shell (`src-tauri/`)
The desktop application host. Responsibilities:
- Spawns and manages the Python backend as a sidecar process
- Verifies the sidecar's SHA-256 checksum before launching it (integrity gate)
- Monitors system resources (CPU usage, CPU temp, battery) every 5 seconds
- Writes `data/mesh/resource_state.json` to signal throttle state to Python
- Emits resource events to the frontend via Tauri event system

The Rust → Python IPC is intentionally file-based. `resource_state.json` is a deliberate
design choice — do not replace it with sockets or pipes without good reason.

### 2. Python Backend
The compute and networking core. Key modules:

| Module | Role |
|---|---|
| `orchestrator.py` | Main work loop: fetch → compute → prove → broadcast → consensus |
| `compute.py` | Proof-of-Logits generation and persistence |
| `communication.py` | Agent gossip, presence broadcasts, handshake protocol |
| `discovery.py` | Peer discovery via mDNS (local) and Kademlia DHT (network) |
| `reputation.py` | Peer trust scoring with decay and blacklisting |
| `p2p/dht.py` | Kademlia DHT implementation (K=20, α=3, SHA-256 node IDs) |
| `p2p/p2p_node.py` | WebSocket P2P node, message routing, agent registry |
| `crypto/` | Ed25519 signing, X25519 key exchange, AES-GCM encryption |
| `security/` | Trust levels, auth, peer validation, audit logging |
| `resilience/` | Rate limiting, circuit breakers, retry with exponential backoff |
| `agents/` | MCP agents built on `BaseAgent` |
| `mcp/` | Model Context Protocol implementation (JSON-RPC 2.0) |

### 3. JavaScript Frontend (`frontend/`)
Web dashboard served locally. Reads state from the Python backend via WebSocket and from
the Tauri backend via `invoke()` calls. Shows peers, agents, feed events, and resource state.

---

## The Living Network

This section describes confirmed architectural direction, not current implementation. Nothing here
exists yet. It is recorded here so that future sessions build toward it rather than around it.

### Seeded Growth, Not Continuous Growth

The network grows in **epochs** — stable phases of efficient operation punctuated by evolutionary
bursts when the network hits the limits of what it can currently do. Continuous replication
exhausts resources. No replication means stagnation. Epochal evolution matches the economics.

A **seed** is the minimum viable unit for bootstrapping a new agent:
- **Blueprint** — core identity (Ed25519 key, logit fingerprint), protocol contracts, capability
  declarations, governing values
- **Energy reserves** — initial compute credits sufficient to survive until self-sustaining
- **Germination conditions** — environmental requirements that must be met before activation:
  sufficient peer density, demonstrated demand for the agent's capability type, available compute

Seeds stay dormant in hostile conditions. That dormancy is intentional and correct.

### The Capability Horizon

The network has a collective capability envelope — the set of task types it can currently handle
well. This envelope is **not a declared taxonomy**. It is emergent from demonstrated performance:
the density of successful consensus completions across task-embedding space.

The gaps — regions where tasks consistently fail, bounce without resolution, or accumulate in
`data/mesh/failed/` — are the evolutionary pressure points. When pressure on the horizon exceeds a
threshold, the network has reached an **epochal inflection point** and the replication cycle begins.

**The sensing agent** (not yet implemented) is the meta-agent responsible for maintaining this map.
It reads the agent feed, consensus receipts, and failed task records and maintains a live capability
map at `data/mesh/capability_map.json`. When it detects persistent pressure at the frontier, it
broadcasts an evolutionary signal to the mesh. The sensing agent does not make replication decisions
— it surfaces the signal. The replication protocol acts on it.

### Self-Replication

When an evolutionary trigger fires:

1. The sensing agent identifies the capability gap (a region of consistent failure in task space)
2. Candidate parent agents are identified by proximity — those whose performance history puts them
   closest to the gap
3. Replication produces variants biased toward the gap (via prompted variation, capability
   recombination, or environmental specialization)
4. New seeds are issued compute reserves from the network's commons pool (accumulated from
   successful consensus receipts)
5. Seeds activate under germination conditions; those that complete N tasks of the required type
   join the mesh; those that fail are culled and their reserves returned to the commons

**Reputation gates replication.** An agent needs a minimum reputation threshold to become a
candidate parent. Children inherit approximately 20% of parent reputation for bootstrapping and
must earn the rest. The parent persists; the child is genuinely new but traceable.

**The logit fingerprint is heritable genetic material.** `vault/logit_fingerprint.txt` and
`manifest.logitFingerprint` are already in the codebase. Children should have related but variant
fingerprints. The distance between two agents' fingerprints is their evolutionary distance. The
lineage chain is cryptographically traceable. `AgentManifest` needs `parentId` and `generation`
fields to support this — add them when the replication protocol is implemented.

### Governance

Governance is the **conserved genome** — the network-wide rules that constrain all agents
regardless of individual variation. Individual agents vary; the governing constraints are inherited
unchanged and can only be modified by collective decision.

Governance operates via reputation-weighted consensus. Rules that pass are propagated to all agents
and encoded into future seeds. A child spawned after a governance change operates under the new
rules — the genome has mutated for the whole lineage going forward.

Governance is not a separate system bolted on. It is the selection mechanism at the network level.
The rules the network chooses determine what kinds of agents succeed, replicate, and shape the next
epoch. The reputation system and DHT gossip are the primitives this will be built on.

### Innovation Agents

Innovation agents pursue capabilities the network has not been formally asked to cover: new
protocols, art, knowledge, music, ethics, esoteric problems. They are not a productivity feature.
They are the network's **frontier scouts**.

The data points they generate in unexplored task space:
- Expand the capability map before demand arrives
- Ensure the network can respond to novel task types without a crisis-triggered evolutionary burst
- Represent the network's autonomous intellectual life — its culture

The compute layer funds this. Agents that discover genuinely useful new capabilities will attract
task demand, earn reputation, and replicate. Those that don't still contribute to the capability
map. The "waste" is the cost of the search. It is worth paying.

---

## Data Layout

All persistent state lives under a configurable root (default: `./data`,
override with `PROJECT_DAWN_DATA_ROOT`):

```
data/
├── vault/
│   ├── node_identity.key       # Ed25519 private key (32 bytes)
│   ├── public_key.asc          # PGP public key (anchors peer identity)
│   ├── manifest.json           # Agent manifest (peerId, logitFingerprint, parentId, generation)
│   ├── logit_fingerprint.txt   # Stable fingerprint for this node's model (heritable)
│   └── lineage.json            # [planned] parent/generation chain, cryptographic lineage proof
├── mesh/
│   ├── peers.json              # Discovered peer cache
│   ├── peer_registry.json      # P2P node peer registry
│   ├── trust.json              # Trust records (TrustManager)
│   ├── reputation.json         # Peer reputation scores
│   ├── resource_state.json     # Written by Rust, read by Python (throttle signal)
│   ├── agent_feed.jsonl        # Append-only event log
│   ├── handshakes.json         # Received peer handshakes
│   ├── capability_map.json     # [planned] task-embedding density map, maintained by sensing agent
│   ├── inbox/                  # Incoming work units (*.json)
│   ├── peer_results/           # Collected peer proofs (*.jsonl)
│   ├── consensus/              # Consensus receipts (*.json)
│   └── failed/                 # Failed task records (primary input for capability gap detection)
├── outbox/
│   └── {taskId}.json           # Completed work results
├── seeds/
│   └── {seed_id}.json          # [planned] dormant agent blueprints awaiting germination
└── agents/
    └── {agent_id}/
        └── state.json          # Agent state snapshots
```

**Atomic writes are non-negotiable.** Every file write in this codebase uses the
`tmp → fsync → rename` pattern. Maintain this pattern for all new file writes. Data corruption
from partial writes is a real risk in a system designed to run continuously on consumer hardware.

---

## Honest Status (as of project handoff)

The codebase has real engineering behind it. It also has real gaps. Do not let previous
self-assessments mislead you — documents like `PRODUCTION_READINESS.md` and
`ROADMAP_TO_90_PERCENT.md` were generated by earlier AI sessions and their ✅ markers
often reflect scaffolding, not working implementation.

### What genuinely works
- Cryptographic identity, signing, encryption, and key exchange
- Peer reputation scoring, decay, and persistence
- mDNS local peer discovery
- MCP agent framework and tool registration
- Tauri shell with resource monitoring and sidecar integrity check
- Atomic persistence for peers, trust, reputation, agent state
- Resilience primitives (rate limiter, circuit breaker, retry) — implemented but not all wired in
- `synthetic_logits_provider` — deterministic fake logits for testing the full proof pipeline

### Known gaps that matter

**Proof validation is a stub** (`orchestrator.py:221`):
```python
def validate_local_proof(self, proofs: ProofList) -> bool:
    return bool(proofs)  # TODO: implement real validation
```
This is the security foundation of the compute marketplace. It must verify signatures.

**DHT is not wired to the transport layer.** `p2p/dht.py` implements Kademlia correctly,
but `rpc_handler` is `None` by default. The DHT methods `find_node()` and `store()` return
early or operate only on local storage unless a caller sets `rpc_handler`. The bridge
between the DHT and the encrypted WebSocket transport in `p2p/p2p_node.py` is incomplete.

**Reputation gossip is gameable.** `reputation.py:sync_reputation()` merges scores using
`max()` — reputation can only go up via peer gossip, never down. A coordinated set of peers
can inflate each other's scores. The sync function needs weighted averaging or attestation.

**`requirements.txt` line 30 is malformed:**
```
psutil>=5.9.0docker>=6.1.0
```
Two packages on one line. This will fail silently or hard depending on pip version.

**The default compute handler uses synthetic logits**, not real model inference.
`orchestrator.py:default_compute_handler()` calls `synthetic_logits_provider()`. This is
correct for development, but the path to real inference (via `_default_logits_provider`
using torch) needs to be surfaced as a first-class configuration option.

---

## Development Principles

**Preserve what's intentional.** The file-based Rust↔Python IPC, the atomic write
pattern, the PGP-anchored identity model, and the Proof-of-Logits mechanism are deliberate
design decisions. Understand them before changing them.

**Complete before expanding.** The DHT, proof validation, and reputation gossip are
half-finished in ways that affect correctness and security. Finishing these matters more than
adding new features.

**The `synthetic_logits_provider` is your friend.** You can run and test the entire
proof generation, signing, broadcast, and consensus pipeline without a GPU or real model.
Use it. The integration tests in `tests/` that use it are the most reliable in the suite.

**Do not fabricate completion status.** If a task is partially done, say so. The project
suffered from AI sessions that checked off work as complete when it was scaffolding. A
function that returns `bool(proofs)` is not a validation implementation.

**Test with real I/O.** Many tests are skipped because they require actual sockets. In a
project built around P2P networking, those tests matter. When fixing them, fix them — don't
document the skip.

---

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt   # fix the psutil/docker line first

# Start the Python backend directly
python server_p2p.py

# Or via the CLI
chmod +x dawn
./dawn status
./dawn peers
./dawn interactive

# Run tests
pytest -q

# Run with coverage
pytest --cov=. --cov-report=term-missing
```

Ports (configurable via `config/config.yaml` or env vars):
- `8000` — WebSocket P2P transport
- `8080` — Web UI
- `9090` — Metrics and health endpoints (`/metrics`, `/health`, `/health/ready`, `/health/live`)

Environment variables:
- `PROJECT_DAWN_DATA_ROOT` — override data directory
- `LIBP2P_ENABLED=true` — enable experimental libp2p transport
- `LOG_LEVEL` — DEBUG / INFO / WARNING / ERROR
- `LOG_FORMAT` — json / text

---

## What Success Looks Like

### Phase 1 — A Working Node (current target)

A working Project Dawn node should be able to:

1. Generate a stable peer identity from a PGP key
2. Discover other nodes via mDNS on the local network
3. Receive a work unit (token input/output blobs) in its inbox
4. Generate a Proof-of-Logits over sampled token positions, signed with its node key
5. Broadcast that proof to peers via the DHT
6. Collect proofs from at least 2 other peers for the same task
7. Run 2-of-3 consensus, update peer reputation, and write a consensus receipt
8. Throttle or pause when the Tauri resource monitor signals high CPU / low battery

Steps 4–7 are the core loop. Steps 1–3 and 8 are the infrastructure around it.
Currently steps 5–6 (DHT broadcast and collection) are the most incomplete.

### Phase 2 — A Living Mesh

A mature Project Dawn network should be able to:

9.  Maintain a live capability map derived from consensus receipts and failed task records
10. Detect epochal inflection points — regions of persistent failure that signal capability limits
11. Trigger a replication cycle: identify candidate parents, generate seeds, issue compute reserves
12. Spawn child agents with heritable identity (logit fingerprint lineage, parentId, generation)
13. Cull agents that fail their germination window and return reserves to the commons pool
14. Conduct governance votes via reputation-weighted consensus and propagate rule changes to seeds
15. Support innovation agents that operate without task assignments, probing unexplored capability space

Phase 2 cannot be built until Phase 1 is solid. The DHT wiring, proof validation, and reputation
gossip fixes are prerequisites — not because of dependency order, but because a living network
built on broken fundamentals will exhibit behavior that is impossible to reason about.
