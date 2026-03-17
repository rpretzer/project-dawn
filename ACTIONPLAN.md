# ACTIONPLAN.md — Project Dawn

_Concrete next steps, ordered by priority. Updated after session M6 (2026-03-17)._
_For strategic context see PLAN.md. For milestone definitions see ROADMAP.md._

---

## Current State

| Area | Status | Evidence |
|---|---|---|
| Proof validation | ✅ Done | `orchestrator.py:validate_local_proof()` uses real Ed25519 verification |
| Reputation gossip | ✅ Done | `reputation.py:sync_reputation()` uses weighted-average merge |
| Atomic writes | ✅ Done | fsync + rename in orchestrator, SensingAgent, and all persistence paths |
| Compute config | ✅ Done | `build_compute_handler()` factory; `synthetic`/`torch`; config-driven |
| DHT in-process | ✅ Done | `p2p/dht.py` tested with full Kademlia routing; `_wire_mesh()` integration tests pass |
| AgentManifest lineage | ✅ Done | `parentId`, `generation`, `from_dict()`; `vault/lineage.json` on genesis |
| SensingAgent | ✅ Done | Scans consensus + failed → `capability_map.json`; 24 tests pass |
| DoS hardening | ✅ Done | 1 MB message limit; trust-first; rate limiter wired to WebSocket |
| DHT over real sockets | ❌ Pending | `P2PNode._handle_dht_rpc()` is not implemented |
| Bootstrap nodes | ❌ Pending | No WAN discovery for first-time nodes |
| `requirements.txt` fix | ❌ Pending | Line 30: `psutil>=5.9.0docker>=6.1.0` (two packages merged) |
| Socket test fixes | ❌ Pending | `test_transport.py` and `test_host.py` are collected but not verified live |
| SensingAgent wired to loop | ❌ Pending | `orchestrator.py` doesn't call `sensing_agent.scan()` yet |
| Seed protocol | ❌ Pending | Phase 2 item 3; schema and dormancy logic not built |
| Packaging (Tauri) | ❌ Pending | Sidecar build never tested end-to-end |

**Test suite:** 336 pass, 5 skipped (4 libp2p feature-gated, 1 sandbox mock).

---

## Priority 1 — Immediate Fixes (unblock everything)

### 1.1 Fix `requirements.txt` line 30
**File:** `requirements.txt:30`
```
# Change:
psutil>=5.9.0docker>=6.1.0
# To:
psutil>=5.9.0
docker>=6.1.0
```
This silently breaks `pip install` on some pip versions. Fix before any fresh environment setup.

### 1.2 Wire SensingAgent into orchestrator background loop
**File:** `orchestrator.py`

`SensingAgent` exists but is never called. Add a background task to `Orchestrator.__init__`
or `start()` that runs `sensing_agent.scan()` on a configurable interval (default: 60s).

```python
# In orchestrator.py — add to __init__:
self._sensing_agent = SensingAgent(
    mesh_dir=self.mesh_dir,
    pressure_threshold=self.config.get("sensing", {}).get("pressure_threshold", 0.7),
)
```

Then in the background task loop, call `self._sensing_agent.scan()` and log the result.
No action needed beyond scanning — the SensingAgent writes `capability_map.json` itself.

---

## Priority 2 — DHT Real-Socket Transport (Developer Alpha gate)

This is the largest remaining gap. The DHT is correct but only tested in-process.
Real node-to-node discovery over WAN requires wiring it to the WebSocket transport.

### 2.1 Implement `P2PNode._handle_dht_rpc()`
**File:** `p2p/p2p_node.py`

This method receives an inbound DHT RPC message from the WebSocket transport and dispatches
it to the local `discovery._dht` node. The response is sent back over the same WebSocket.

```python
async def _handle_dht_rpc(self, peer_id: str, message: dict) -> dict:
    """
    Dispatch an incoming DHT RPC message to the local DHT node and return the response.
    Called from the WebSocket message handler when msg["type"] == "dht_rpc".
    """
    # message: {"type": "dht_rpc", "method": "find_node"|"store"|"find_value", "params": {...}}
    # Return: {"type": "dht_rpc_response", "result": {...}}
```

Route to `discovery._dht.handle_rpc(message)` — the DHT already has internal dispatch logic;
this method just bridges the WebSocket layer to it.

### 2.2 Wire `discovery.start()` with the transport handler
**File:** `server_p2p.py`

At startup, pass the transport handler so outbound DHT messages go through the encrypted
WebSocket channel:

```python
await discovery.start(
    rpc_handler=lambda peer_id, msg: p2p_node.send_message(peer_id, msg)
)
```

The `rpc_handler` signature is already defined in `p2p/dht.py` — it just needs to be set.

### 2.3 Add message type routing in WebSocket handler
**File:** `p2p/p2p_node.py`

In the inbound message handler, add a branch for `"dht_rpc"` type messages:
```python
elif msg_type == "dht_rpc":
    response = await self._handle_dht_rpc(sender_id, message)
    await self.send_message(sender_id, response)
```

### 2.4 Fix socket tests
**Files:** `tests/test_transport.py`, `tests/test_host.py`

These tests are collected but their actual socket operations may not exercise the DHT path.
After 2.1–2.3, verify they pass and add a `test_dht_over_socket` test that:
- Starts two `P2PNode` instances on localhost (different ports)
- Node A calls `discovery.dht_store(key, value)`
- Node B calls `discovery.dht_find_value(key)` and gets the value back

---

## Priority 3 — Bootstrap / Seed Nodes

Without this, a node starting fresh has no way to find peers outside its local network.

### 3.1 Add `bootstrap_nodes` to config
**File:** `config/default.yaml`

```yaml
discovery:
  bootstrap_nodes: []   # list of "host:port" strings; empty = local-only
  bootstrap_timeout_seconds: 30
```

### 3.2 Bootstrap sequence in `discovery.py`
**File:** `discovery.py`

On startup, if `bootstrap_nodes` is non-empty:
1. Connect to each bootstrap node via WebSocket
2. Send a `find_node(self.node_id)` DHT RPC to populate the routing table
3. Log the discovered peers

### 3.3 CLI: `./dawn peers --add <address>`
**File:** `dawn` (CLI entry point)

Let operators manually add a peer address to bootstrap from. Useful for private meshes
before public bootstrap nodes exist.

---

## Priority 4 — Phase 2: Seed Protocol

Prerequisites: Priority 2 complete, core loop validated on real hardware.

### 4.1 Define seed schema
**File:** `data/seeds/{seed_id}.json` (new)

```json
{
  "seedId": "sha256-based UUID",
  "blueprint": {
    "peerId": "...",
    "logitFingerprint": "...",
    "parentId": "...",
    "generation": 1,
    "capabilityDeclarations": ["text-inference", "..."]
  },
  "computeReserves": 100,
  "germinationConditions": {
    "minPeerDensity": 3,
    "minDemandSignals": 5,
    "availableComputeUnits": 50
  },
  "issuedAt": "ISO8601",
  "expiresAt": "ISO8601"
}
```

### 4.2 Commons pool accounting
**File:** `data/mesh/commons.json` (new)

Accumulates compute credits from successful consensus receipts. Tracks:
- `totalAccumulated` — all-time credits earned by the mesh
- `currentBalance` — available for seed issuance
- `seedAllocations` — list of issued seeds and their reserve amounts

### 4.3 `SeedManager` class
**File:** `agents/seed_manager.py` (new)

Responsibilities:
- Issue seeds when evolutionary trigger fires (called by replication agent)
- Check germination conditions against current network state
- Activate dormant seeds when conditions are met
- Cull seeds that fail their germination window; return reserves to commons

---

## Priority 5 — Packaging (Public Beta gate)

### 5.1 Fix Python sidecar build
**File:** `scripts/build_python_sidecar.py`

Build script exists but has never produced a tested distributable. Run it, fix failures.
Output must include SHA-256 checksum that matches what `src-tauri/` verifies.

### 5.2 Platform builds
Test on macOS first. Then Linux (`.deb` / `.AppImage`). Then Windows (`.msi`).
For each platform:
- Build runs to completion without `continue-on-error: true`
- Installer launches without OS security warnings (requires code signing)
- Node starts, generates identity, finds local peers

### 5.3 Code signing
- macOS: Apple Developer ID + notarization (required to bypass Gatekeeper)
- Windows: Authenticode certificate (required to bypass SmartScreen)
- Linux: AppImage signing (optional but good practice)

---

## Decisions Deferred

These are known issues that are not on the critical path to Developer Alpha:

| Item | Decision | Rationale |
|---|---|---|
| libp2p integration | Skip for now; 4 tests permanently skipped | Adds significant complexity; Kademlia DHT covers the same ground |
| Real inference (torch) | Config path exists via `build_compute_handler("torch", ...)` | Requires GPU hardware; not testable in current env |
| Frontend XSS hardening | Defer to Milestone 7 | Dashboard is localhost-only; risk is low until public release |
| Audit log wiring verification | Defer to Milestone 7 | Infrastructure exists; correctness matters more before hardening |
| CRDT sync | `test_system.py::test_crdt_synchronization` passes; no known issues | |

---

## How to Pick Up This Work

```bash
# Verify clean state
git checkout claude/review-project-codebase-WtWY3
python -m pytest -q           # should be 336 passed, 5 skipped

# Fix requirements first (P1.1)
sed -i 's/psutil>=5.9.0docker>=6.1.0/psutil>=5.9.0\ndocker>=6.1.0/' requirements.txt
pip install -r requirements.txt

# Wire SensingAgent (P1.2) — then run tests again
# Implement DHT socket transport (P2.1–2.3) — then run tests again
# Add bootstrap nodes (P3) — then test with two Docker containers on same host
```

The test suite is the ground truth. If `pytest -q` is green, the in-process behavior is correct.
The next major milestone requires real sockets.
