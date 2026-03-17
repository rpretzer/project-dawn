# ACTIONPLAN.md — Project Dawn

_Concrete next steps, ordered by priority. Updated after completing Phase 2 (Governance Protocol)._
_For strategic context see PLAN.md. For milestone definitions see ROADMAP.md._

---

## Current State

| Area | Status | Evidence |
|---|---|---|
| Proof validation | ✅ Done | `orchestrator.py:validate_local_proof()` uses real Ed25519 verification |
| Reputation gossip | ✅ Done | `reputation.py:sync_reputation()` uses weighted-average merge |
| Atomic writes | ✅ Done | fsync + rename in orchestrator, SensingAgent, SeedManager, all persistence paths |
| Compute config | ✅ Done | `build_compute_handler()` factory; `synthetic`/`torch`; config-driven |
| DHT in-process | ✅ Done | `p2p/dht.py` tested with full Kademlia routing |
| DHT real-socket wiring | ✅ Done | `P2PNode._handle_dht_rpc()` routes outbound over WebSocket; inbound in `_handle_node_method` |
| DHT bridge (orchestrator) | ✅ Done | `server_p2p.py` replaces orchestrator DHT with P2PNode DHT when `enable_dht=True` |
| Discovery routing-table seeding | ✅ Done | `SovereignDiscovery.record_peer()` calls `dht.add_node()`; `set_dht()` seeds from known peers |
| Bootstrap discovery | ✅ Done | Real `node/get_info` WebSocket handshake; placeholder fallback for unreachable nodes |
| Bootstrap CLI | ✅ Done | `./dawn peers --add ws://host:port` |
| AgentManifest lineage | ✅ Done | `parentId`, `generation`, `from_dict()`; `vault/lineage.json` on genesis |
| SensingAgent | ✅ Done | Scans consensus + failed → `capability_map.json`; wired into orchestrator loop |
| Seed protocol | ✅ Done | `agents/seed_manager.py`: `SeedManager`, `CommonsPool`, full lifecycle + tests |
| DoS hardening | ✅ Done | 1 MB message limit; trust-first; rate limiter wired to WebSocket |
| Socket tests | ✅ Done | `test_transport.py` (3 tests), `test_discovery_dht_wiring.py` (7 tests) pass |
| Replication agent | ✅ Done | `agents/replication_agent.py`: selects parents, derives blueprints, issues seeds; wired into orchestrator |
| Governance protocol | ✅ Done | `agents/governance.py`: reputation-weighted proposal/vote/tally; accepted rules persisted + inherited |
| Packaging (Tauri) | ❌ Pending | Sidecar build never tested end-to-end |
| Real inference (torch) | ❌ Pending | Config path exists; requires GPU hardware to test |

**Test suite:** 435 pass, 5 skipped (4 libp2p feature-gated, 1 sandbox mock).

---

## Priority 1 — Packaging (Public Beta gate)

### 1.1 Fix Python sidecar build
**File:** `scripts/build_python_sidecar.py`

Build script exists but has never produced a tested distributable. Run it, fix failures.
Output must include SHA-256 checksum that matches what `src-tauri/` verifies.

### 1.2 Platform builds
Test on macOS first. Then Linux (`.deb` / `.AppImage`). Then Windows (`.msi`).
For each platform:
- Build runs to completion without `continue-on-error: true`
- Installer launches without OS security warnings (requires code signing)
- Node starts, generates identity, finds local peers

### 1.3 Code signing
- macOS: Apple Developer ID + notarization
- Windows: Authenticode certificate
- Linux: AppImage signing (optional)

---

## Decisions Deferred

| Item | Decision | Rationale |
|---|---|---|
| libp2p integration | Skip; 4 tests permanently skipped | Kademlia DHT covers the same ground |
| Real inference (torch) | Config path exists via `build_compute_handler("torch", ...)` | Requires GPU hardware |
| Frontend XSS hardening | Defer to hardening phase | Dashboard is localhost-only |
| Audit log wiring verification | Defer to hardening phase | Infrastructure exists |

---

## How to Pick Up This Work

```bash
# Verify clean state
git checkout claude/review-project-codebase-WtWY3
python -m pytest -q           # should be 381 passed, 5 skipped

# Run with DHT enabled and bootstrap nodes
PROJECT_DAWN_ENABLE_DHT=true \
PROJECT_DAWN_BOOTSTRAP_NODES=ws://node1.example.com:8000 \
python server_p2p.py

# Add a peer manually
./dawn peers --add ws://10.0.0.1:8000

# Trigger a sensing scan (runs automatically every 60s in orchestrator loop)
# Or check capability map directly:
cat data/mesh/capability_map.json

# Issue a seed manually (REPL)
from agents.seed_manager import SeedManager, AgentBlueprint, GerminationConditions
mgr = SeedManager()
mgr.commons.accumulate(1000)
bp = AgentBlueprint(peerId="...", logitFingerprint="...", parentId="...", generation=1)
seed = mgr.issue(bp, compute_reserves=100)
```

The test suite is the ground truth.  Phase 2 is complete.  The next milestone is packaging
(Priority 1): building and testing the Tauri sidecar distributable end-to-end.
