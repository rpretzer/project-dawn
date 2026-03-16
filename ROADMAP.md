# ROADMAP.md — Project Dawn

This document is the honest path to public release. It supersedes
`PRODUCTION_READINESS.md` and `ROADMAP_TO_90_PERCENT.md`, both of which were generated
by earlier AI sessions and contain ✅ markers that reflect scaffolding, not working code.

Current state: **~50-55% complete** for a developer alpha release.

---

## Release Definitions

**Developer Alpha** — Works for technical users who can debug. The core Proof-of-Logits loop
runs end-to-end. Two nodes can find each other over WAN. Proof validation is real. Not
packaged as an installer — run from source.

**Public Beta** — Installs without a terminal. Nodes self-discover, form a mesh, and run
inference tasks without manual intervention. The reputation system is trustworthy. Suitable
for early adopters willing to tolerate rough edges.

**v1.0** — Stable enough for non-technical users. Documented. Tested on consumer hardware
across platforms. Network has public bootstrap nodes. The living network foundations (Phase 2)
are designed but not yet required.

---

## Milestone 0 — Make It Runnable

**Target: Developer Alpha prerequisite. Estimated: 1–2 days.**

These are table-stakes fixes that block everything downstream. Do them first.

- [ ] Fix `requirements.txt` line 30: split `psutil>=5.9.0docker>=6.1.0` into two lines
- [ ] Fix `security/trust.py:191` — missing `Any` import causes `NameError` at test collection
- [ ] Install `cryptography` in dev environment — blocks `test_communication.py` and `test_crypto.py`
- [ ] Verify `pytest -q` collects without errors after the above fixes

**Exit criterion:** `pytest --co -q` runs to completion with no collection errors.

---

## Milestone 1 — Security Foundation

**Target: Developer Alpha prerequisite. Estimated: 1 week.**

The core defense mechanism is currently disabled. This must be fixed before any node
interacts with untrusted peers.

### Proof Validation (CRITICAL — 2–4 hours)

`orchestrator.py:validate_local_proof()` returns `bool(proofs)` — it accepts any non-empty
list as valid. This means a compromised node can fabricate proofs and earn reputation for
work it never did.

The fix already exists: `orchestrator.py:_verify_peer_result()` (line 437) does real
Ed25519 signature verification via `MessageSigner.verify_with_public_key_bytes()`. Copy
that logic to `validate_local_proof()`. This is the highest-impact/lowest-effort fix in
the entire codebase.

- [ ] Implement `validate_local_proof()` using the same verification path as `_verify_peer_result()`
- [ ] Write a test: a tampered proof must be rejected
- [ ] Write a test: a valid proof from `synthetic_logits_provider` must pass

### Reputation Gossip (HIGH — 4–6 hours)

`reputation.py:sync_reputation()` uses `max()` to merge scores. Reputation can only increase
via gossip. A coordinated group of peers can inflate each other to maximum reputation without
doing any real work.

- [ ] Replace `max()` merge with weighted average: `new = 0.7 * current + 0.3 * (incoming * sender_reputation)`
- [ ] Add a test: colluding peers cannot inflate each other's scores above what honest work would produce
- [ ] Verify `apply_decay()` is still called after sync (it's already implemented — don't break it)

### DoS Hardening (MEDIUM — 6–8 hours)

- [ ] Add message size limit before `json.loads()` in `p2p/p2p_node.py:386`
  (reject messages over a configurable limit, default 1MB)
- [ ] Move sender trust check before JSON parsing (currently trust is validated after parse)
- [ ] Add rate limiting to incoming WebSocket connections (resilience primitives exist but
  aren't wired — wire `RateLimiter` to the connection handler)

**Exit criterion:** A proof with an invalid signature is rejected. Colluding peers cannot
inflate scores above earned levels. Oversized messages are dropped before parsing.

---

## Milestone 2 — Network

**Target: Developer Alpha prerequisite. Estimated: 3–4 weeks.**

This is the largest remaining block of work. Two nodes cannot find each other over WAN
without it.

### Wire DHT to Transport (CRITICAL — 40–60 hours)

The Kademlia DHT in `p2p/dht.py` is correctly implemented but `rpc_handler` is never set
at startup. Every `find_node()` and `store()` call returns `[]` silently.

The chain to complete:
1. Implement `P2PNode._handle_dht_rpc()` — receives DHT RPC messages from the WebSocket
   transport and dispatches them to the local DHT node
2. Call `discovery.start(rpc_handler=node._handle_dht_rpc)` in `server_p2p.py` during startup
3. Wire outbound DHT messages through `P2PNode.send_message()` with the encrypted WebSocket
   transport (X25519 key exchange + AES-GCM is already implemented in `crypto/`)
4. Test: two nodes on separate machines can store and retrieve a key via DHT

The `crypto/` layer, `p2p/p2p_node.py` transport, and `p2p/dht.py` are all individually
functional. This milestone is connecting them.

- [ ] Implement `P2PNode._handle_dht_rpc()` inbound handler
- [ ] Wire `discovery.start()` call at server startup
- [ ] Wire outbound DHT messages through encrypted transport
- [ ] Get `test_host.py` socket tests passing (currently skipped — fix them, don't document the skip)
- [ ] Get `test_transport.py` socket tests passing (same)
- [ ] End-to-end test: two nodes exchange a DHT store/retrieve over a real socket

### Bootstrap / Seed Nodes (HIGH — 8–12 hours)

A new node starting for the first time has no way to find peers outside its local network.

- [ ] Add a `bootstrap_nodes` list to `config/config.yaml` (default empty, configurable)
- [ ] Add 2–3 hardcoded fallback bootstrap addresses to `discovery.py` for when config is empty
- [ ] Implement initial DHT bootstrap sequence: on startup, connect to bootstrap nodes,
  run `find_node(self.node_id)` to populate the routing table
- [ ] CLI command: `./dawn peers --add <address>` to manually add a peer
- [ ] Deploy at least 2 bootstrap nodes before any public release

**Exit criterion:** Two nodes on different machines, different networks, no manual
configuration, find each other and complete a handshake within 60 seconds of startup.

---

## Milestone 3 — Core Loop

**Target: Developer Alpha. Estimated: 1–2 weeks.**

The core value proposition of the system must demonstrably work before anything else matters.

Steps 4–7 from CLAUDE.md are the loop. Steps 5–6 (DHT broadcast and collection) are
currently the most incomplete and are unblocked by Milestone 2.

- [ ] End-to-end test with `synthetic_logits_provider`: node A receives a work unit, generates
  a Proof-of-Logits, broadcasts via DHT, nodes B and C collect and return their proofs,
  2-of-3 consensus runs, consensus receipt written
- [ ] Verify `validate_local_proof()` is called in the loop (Milestone 1 fix must be wired in)
- [ ] Verify reputation is updated after consensus (scores go up for honest nodes, down for failures)
- [ ] Verify resource throttling works: set CPU threshold low, confirm orchestrator pauses
- [ ] Run the loop 100 times without crashing or corrupting state

**Exit criterion:** A three-node mesh runs the Proof-of-Logits loop continuously for 1 hour
using `synthetic_logits_provider` without crashes, data corruption, or false consensus.

---

## Milestone 4 — Real Inference

**Target: Developer Alpha (optional) / Public Beta (required). Estimated: 1–2 weeks.**

The `synthetic_logits_provider` is correct for development and testing. Real inference needs
to be a first-class option, not buried.

- [ ] Surface `USE_REAL_INFERENCE=true` as a documented environment variable
- [ ] When enabled, route through `_default_logits_provider` (torch-based)
- [ ] Add `torch` to `requirements.txt` as an optional dependency with clear install instructions
- [ ] Document minimum hardware requirements for real inference (RAM, VRAM)
- [ ] Test: Proof-of-Logits from real inference passes the same validation as synthetic

**Exit criterion:** A node running real model inference produces proofs that pass validation
and achieve consensus with other nodes.

---

## Milestone 5 — Packaging

**Target: Public Beta. Estimated: 6–8 weeks (includes platform testing).**

Currently there is no installer. The Tauri shell, sidecar build scripts, and CI workflows
exist but have never produced a working distributable artifact.

- [ ] Fix Python sidecar build: `scripts/build_python_sidecar.py` must produce a working binary
- [ ] Verify SHA-256 checksum generation and Tauri integrity check work end-to-end
- [ ] Build and test on macOS (primary), Linux (.deb/.AppImage), Windows (.msi)
- [ ] Automated CI: every merge to main produces build artifacts for all three platforms
- [ ] Remove `continue-on-error: true` from critical steps in `build-and-sign.yml`
- [ ] Code signing: macOS notarization, Windows Authenticode (without these, OS security
  warnings will prevent installation for most users)
- [ ] Auto-update mechanism (Tauri has built-in support — wire it to a release endpoint)

**Exit criterion:** A non-technical user on macOS/Windows/Linux can download and run Project
Dawn without opening a terminal.

---

## Milestone 6 — First-Run Experience & Documentation

**Target: Public Beta. Estimated: 2–3 weeks.**

- [ ] First-run wizard: key generation, display peer ID, verify network connectivity
- [ ] Dashboard: show meaningful state (peers, recent tasks, your reputation score, resource load)
- [ ] User-facing README: what Project Dawn is, how to get started, what to expect
- [ ] Troubleshooting guide: "I don't see any peers" (most common early-adopter problem)
- [ ] Security disclosure process (before public release, someone needs to be able to report vulnerabilities)

---

## Milestone 7 — Hardening

**Target: Between Beta and v1.0. Estimated: 3–4 weeks.**

- [ ] Load test: 50-node mesh running continuously for 24 hours, no memory leaks, no crashes
- [ ] Fuzz `p2p/p2p_node.py` message handler with malformed input
- [ ] Verify circuit breakers actually trip under sustained peer failures
- [ ] Frontend: sanitize `innerHTML` usage (XSS risk with untrusted peer data)
- [ ] Audit logging for all consensus decisions (already implemented in `security/` — verify it's wired)
- [ ] Fix libp2p integration (currently all skipped tests) or remove it if not planned

---

## Phase 2 — The Living Network

These capabilities are defined in `CLAUDE.md` under "The Living Network." They are not
on the critical path to v1.0 but should be designed to be compatible with everything built
in Milestones 0–7.

Prerequisites before any Phase 2 work begins:
- DHT wiring complete (Milestone 2)
- Core loop validated (Milestone 3)
- Proof validation real (Milestone 1)

Phase 2 sequence:
1. **Sensing agent** — reads failed tasks + consensus receipts, builds capability map
2. **AgentManifest fields** — add `parentId` and `generation` to support lineage
3. **Seed protocol** — blueprint format, commons pool, germination logic
4. **Replication agent** — triggered by sensing agent's evolutionary signal
5. **Governance protocol** — reputation-weighted proposal/vote/propagation

Do not begin Phase 2 until the core loop runs reliably on real hardware. A living network
built on a broken compute layer will exhibit behavior that is impossible to reason about.

---

## Summary

| Milestone | Target | Status | Estimate |
|---|---|---|---|
| 0 — Runnable | Alpha prereq | Not done | 1–2 days |
| 1 — Security | Alpha prereq | Not done | 1 week |
| 2 — Network | Alpha prereq | ~70% (DHT unwired) | 3–4 weeks |
| 3 — Core Loop | **Developer Alpha** | Blocked by M2 | 1–2 weeks |
| 4 — Real Inference | Beta | Not done | 1–2 weeks |
| 5 — Packaging | Beta | Foundation exists | 6–8 weeks |
| 6 — Docs / UX | **Public Beta** | Not done | 2–3 weeks |
| 7 — Hardening | Pre-v1.0 | Not done | 3–4 weeks |
| Phase 2 | **v1.0+** | Designed only | TBD |

**Realistic timeline to Developer Alpha:** 6–8 weeks of focused engineering.
**Realistic timeline to Public Beta:** 4–5 months.
**Realistic timeline to v1.0:** 6–8 months.

These estimates assume one focused engineer. They are not padded — the DHT wiring alone
is 40–60 hours of real work and platform packaging is typically underestimated.
