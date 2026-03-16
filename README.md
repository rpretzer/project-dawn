# Project Dawn

A decentralized AI compute network where nodes run inference, cryptographically prove they
did it, reach consensus on results, and build reputation over time.

The core mechanism is **Proof-of-Logits**: at selected token positions, a node hashes its
top-k logit values and signs the hash with its Ed25519 private key. Peers can verify the
proof without re-running inference. Results are accepted via 2-of-3 consensus. This is the
reason the project exists.

> **Status:** Under active development. The cryptographic identity, persistence, and agent
> framework are solid. The DHT transport and proof validation are the current focus.
> See [ROADMAP.md](ROADMAP.md) for an honest picture of where things stand.

---

## What It Does

- Nodes discover each other via mDNS (local) and Kademlia DHT (network)
- Each node has a stable Ed25519 identity anchored to a PGP key
- Work units arrive in the node's inbox; the node generates a signed Proof-of-Logits
- Proofs are broadcast to peers; 2-of-3 consensus produces a consensus receipt
- Peer reputation is tracked with decay — honest nodes gain standing over time
- The Tauri desktop shell monitors CPU/battery and throttles compute accordingly
- MCP agents (coordination, code execution, general tools) are exposed via JSON-RPC 2.0

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js (for Tauri frontend, optional for backend-only use)
- Rust + Cargo (for Tauri desktop app, optional)

### Run the backend directly

```bash
# Install dependencies
pip install -r requirements.txt

# Start the P2P node
python server_p2p.py
```

Ports:
- `ws://localhost:8000` — WebSocket P2P transport
- `http://localhost:8080` — Web UI
- `http://localhost:9090` — Metrics and health (`/metrics`, `/health`, `/health/ready`)

### CLI

```bash
chmod +x dawn
./dawn status
./dawn peers
./dawn interactive
```

### Run tests

```bash
pytest -q
pytest --cov=. --cov-report=term-missing
```

---

## Configuration

YAML config lives in `config/config.yaml`. Environment variable overrides use the
`PROJECT_DAWN_*` prefix.

Key variables:
- `PROJECT_DAWN_DATA_ROOT` — override data directory (default: `./data`)
- `LIBP2P_ENABLED=true` — enable experimental libp2p transport
- `LOG_LEVEL` — DEBUG / INFO / WARNING / ERROR
- `LOG_FORMAT` — json / text

---

## Project Layout

```
project-dawn/
├── src-tauri/       # Rust / Tauri desktop shell
├── frontend/        # Web dashboard (vanilla JS, no build step)
├── agents/          # MCP agents (BaseAgent, FirstAgent, CodeAgent, CoordinationAgent)
├── cli/             # Command-line interface
├── config/          # Configuration management
├── consensus/       # Distributed agent registry (CRDT)
├── crypto/          # Ed25519 signing, X25519 key exchange, AES-GCM encryption
├── p2p/             # Kademlia DHT, WebSocket P2P node
├── mcp/             # Model Context Protocol (JSON-RPC 2.0)
├── security/        # Trust levels, auth, peer validation, audit logging
├── resilience/      # Rate limiter, circuit breaker, retry with backoff
├── health/          # Health check framework
├── metrics/         # Prometheus metrics
├── orchestrator.py  # Main work loop: fetch → compute → prove → broadcast → consensus
├── compute.py       # Proof-of-Logits generation
├── communication.py # Agent gossip, presence broadcasts, handshake protocol
├── discovery.py     # Peer discovery (mDNS + Kademlia)
├── reputation.py    # Peer trust scoring with decay and blacklisting
└── server_p2p.py    # Entry point
```

Data lives under `./data/` (or `PROJECT_DAWN_DATA_ROOT`). See [CLAUDE.md](CLAUDE.md) for
the full data layout.

---

## Key Documents

| Document | Purpose |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Architecture, design decisions, honest status, development principles |
| [AGENTS.md](AGENTS.md) | Available agents, their tools, and implementation status |
| [ROADMAP.md](ROADMAP.md) | Honest path to public release with effort estimates |
| [STANDARDS.md](STANDARDS.md) | Code conventions, patterns, layer boundaries |

---

## Security

- End-to-end encryption: X25519 key exchange + AES-GCM per message
- Ed25519 signing on all proofs and peer communications
- PGP-anchored peer identity
- Trust levels: UNTRUSTED → UNKNOWN → VERIFIED → TRUSTED → BOOTSTRAP
- Audit logging for consensus decisions and trust changes
- Proof validation verifies signatures before accepting results

**Known gaps:** Proof validation for locally-generated proofs is a stub (scheduled for
Milestone 1). Reputation gossip uses `max()` merge and is gameable by colluding peers
(also Milestone 1). See [ROADMAP.md](ROADMAP.md).

---

## License

[Add license]
