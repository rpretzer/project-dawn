# ACTIONPLAN.md — Project Dawn

_Concrete next steps, ordered by priority. Updated after session work through Phase 2 seeds._
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
| Replication agent | ❌ Pending | Phase 2 item 4: triggered by sensing signal, coordinates seed issuance |
| Governance protocol | ❌ Pending | Phase 2 item 5: reputation-weighted vote + rule propagation |
| Packaging (Tauri) | ❌ Pending | Sidecar build never tested end-to-end |
| Real inference (torch) | ❌ Pending | Config path exists; requires GPU hardware to test |

**Test suite:** 381 pass, 5 skipped (4 libp2p feature-gated, 1 sandbox mock).

---

## Priority 1 — Replication Agent (Phase 2, item 4)

Prerequisites are complete: SensingAgent detects pressure, AgentManifest has lineage fields,
SeedManager issues/activates/culls seeds with commons pool accounting.

The replication agent closes the loop: sensing signal → candidate parent selection → seed issuance.

### 1.1 Define the replication trigger protocol

When `SensingAgent.scan()` returns `evolutionary_pressure = True`, the orchestrator should
emit a replication signal to the mesh.  The signal is a DHT broadcast:

```python
key = f"replication_signal:{timestamp_bucket}"
value = {
    "pressureRegions": cap_map["pressure_regions"],
    "triggerTime": time.time(),
    "originPeerId": self.peer_id,
}
await dht.store(key, value, ttl=3600)
```

### 1.2 Implement `ReplicationAgent` (`agents/replication_agent.py`)

**Trigger:** `SensingAgent.is_under_pressure()` returns True.

**Algorithm:**
1. Load `data/mesh/reputation.json` — find peers with reputation ≥ threshold (default 0.7)
2. Among those, identify candidates closest to pressure regions (by capability intersection)
3. For each candidate, generate a child `AgentBlueprint`:
   - `parentId` = candidate's `peerId`
   - `generation` = candidate's `generation` + 1
   - `logitFingerprint` = variant of parent's fingerprint (see §1.3)
   - `capabilityDeclarations` = biased toward the pressure region's capability type
4. Call `SeedManager.issue(blueprint, compute_reserves)` for each candidate
5. Broadcast seed issuance to mesh via DHT

**File:** `agents/replication_agent.py`

### 1.3 Logit fingerprint inheritance

From CLAUDE.md: "The logit fingerprint is heritable genetic material."
Children should have related but variant fingerprints.

Simple implementation:
```python
def _child_fingerprint(parent_fingerprint: str, generation: int) -> str:
    raw = f"{parent_fingerprint}:gen{generation}:{uuid.uuid4()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
```

The distance between two fingerprints (edit distance or XOR of their SHA256 prefixes)
is their evolutionary distance.  The lineage chain is cryptographically traceable via
`vault/lineage.json` → `parentId` chain.

### 1.4 Wire germination checker into orchestrator loop

After `_maybe_sensing_scan()`, check whether any dormant seeds can be activated:

```python
# In orchestrator.py run() loop:
await self._maybe_activate_seeds()
```

`_maybe_activate_seeds()` calls `SeedManager.check_germination_conditions()` for each
dormant seed using current peer count and demand signals from the inbox queue.

---

## Priority 2 — Governance Protocol (Phase 2, item 5)

**Not started.** Depends on: working mesh with multiple nodes (Priority 1 complete,
real hardware test).

High-level design (from CLAUDE.md):

1. Any agent with sufficient reputation can propose a rule change
2. Proposal is broadcast to the mesh as a DHT entry
3. Peers vote (weight = their reputation score at vote time)
4. If weighted approval ≥ threshold (default 0.66), the rule is accepted
5. Accepted rules are propagated to all agents and encoded into future seeds

**Schema:** `data/mesh/governance/` — pending proposals, votes, accepted rules.

---

## Priority 3 — Packaging (Public Beta gate)

### 3.1 Fix Python sidecar build
**File:** `scripts/build_python_sidecar.py`

Build script exists but has never produced a tested distributable. Run it, fix failures.
Output must include SHA-256 checksum that matches what `src-tauri/` verifies.

### 3.2 Platform builds
Test on macOS first. Then Linux (`.deb` / `.AppImage`). Then Windows (`.msi`).
For each platform:
- Build runs to completion without `continue-on-error: true`
- Installer launches without OS security warnings (requires code signing)
- Node starts, generates identity, finds local peers

### 3.3 Code signing
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

The test suite is the ground truth.  The next major milestone is the replication agent
(Priority 1 above) which closes the Phase 2 loop: sensing → replication → germination → culling.
