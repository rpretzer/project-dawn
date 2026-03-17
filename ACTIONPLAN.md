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
| Packaging (Tauri) | ✅ Done | Sidecar builds (PyInstaller → 12MB ELF); starts cleanly; `beforeBuildCommand` wired |
| Real inference (torch) | ❌ Pending | Config path exists; requires GPU hardware to test |

**Test suite:** 435 pass, 5 skipped (4 libp2p feature-gated, 1 sandbox mock).

---

## Priority 1 — Packaging (Public Beta gate)

### How the sidecar mechanism works

`main.rs` uses manual path resolution (not Tauri's `new_sidecar()`):
1. Looks for the executable at `{resource_dir}/sidecar/project-dawn-server[.exe]`
2. Reads `{resource_dir}/sidecar/project-dawn-server[.exe].sha256`
3. Verifies SHA-256 before launching

`tauri.conf.json` bundles the sidecar via `resources` (not `externalBin`, which was
removed — it was declared but never used). `beforeBuildCommand` now runs the
PyInstaller step automatically when `cargo tauri build` is invoked.

### 1.1 Run the sidecar build and verify output

```bash
cd /path/to/project-dawn
python scripts/build_python_sidecar.py
# Expect: src-tauri/sidecar/project-dawn-server (binary)
#         src-tauri/sidecar/project-dawn-server.sha256
ls -lh src-tauri/sidecar/
```

The build script writes the SHA-256 checksum automatically. Verify `main.rs`
can find and verify it before proceeding to a full Tauri build.

Known PyInstaller pitfalls for this codebase:
- `asyncio`, `websockets`, `zeroconf` all use dynamic imports — add `--hidden-import`
  entries in `build_python_sidecar.py` if the built binary crashes on startup
- `config/` and `data/` directories must either be bundled with `--add-data` or
  resolved relative to the executable at runtime (not `__file__`)
- Test the built binary standalone before wrapping it in Tauri:
  ```bash
  src-tauri/sidecar/project-dawn-server --help
  ```

### 1.2 Platform builds

PyInstaller produces platform-native binaries — **you cannot cross-compile**.
Each platform requires its own CI runner.

Recommended CI matrix (GitHub Actions):

```yaml
strategy:
  matrix:
    include:
      - os: ubuntu-22.04   → project-dawn-server (ELF), .deb / .AppImage
      - os: macos-13       → project-dawn-server (Mach-O), .dmg
      - os: windows-2022   → project-dawn-server.exe, .msi
```

For each platform, the full sequence is:
1. `pip install -r requirements.txt pyinstaller`
2. `python scripts/build_python_sidecar.py`
3. `cargo tauri build`
4. Smoke test: launch installer, start app, verify node identity is generated

### 1.3 Audit and remove `src-tauri/bin/`

`src-tauri/bin/project-dawn-server-x86_64-unknown-linux-gnu` is a stripped ELF
with no documented provenance. It was likely placed there manually during early
development. It is no longer referenced by `tauri.conf.json` (the `externalBin`
entry has been removed).

**Action:** Verify it is not needed, then delete it and remove the `bin/` directory.
Do not commit binaries of unknown origin into the repository.

---

## Decisions Deferred

| Item | Decision | Rationale |
|---|---|---|
| libp2p integration | Skip; 4 tests permanently skipped | Kademlia DHT covers the same ground |
| Real inference (torch) | Config path exists via `build_compute_handler("torch", ...)` | Requires GPU hardware |
| Frontend XSS hardening | Defer to hardening phase | Dashboard is localhost-only |
| Audit log wiring verification | Defer to hardening phase | Infrastructure exists |
| Code signing | Defer to public release | Too much overhead for current phase; users can build from source |

---

## How to Pick Up This Work

```bash
# Verify clean state
git checkout claude/review-project-codebase-WtWY3
python -m pytest -q           # should be 435 passed, 5 skipped

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

The test suite is the ground truth. Phase 1 and Phase 2 are both complete. Packaging is done.

## What's Left

The remaining gaps are narrow:

| Item | What remains |
|---|---|
| Real inference | Wire `build_compute_handler("torch", ...)` to a real Ollama/llama.cpp endpoint; test Proof-of-Logits with real model output. Blocked on hardware. |
| Live two-node smoke test | Run two sidecar instances on the same LAN, exchange a real work unit, reach consensus. Tests simulate this in-process; it has not been done with actual OS processes. |
| Platform builds | macOS + Windows sidecar binaries (PyInstaller is platform-native; needs CI runners). Linux `.deb`/`.AppImage` builds on top of current working sidecar. |
| `libp2p_node._announce_agent()` | Stub (`pass`) in the experimental libp2p transport, feature-gated by `LIBP2P_ENABLED=true`. Low priority; default transport is fully wired. |
