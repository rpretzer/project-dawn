# ACTIONPLAN.md — Project Dawn

_Updated after full autonomy gap assessment. Previous phases complete._
_Strategic context: CLAUDE.md. Milestone definitions: ROADMAP.md._

---

## Current State

| Area | Status | Evidence |
|---|---|---|
| Proof signing & validation | ✅ Done | `orchestrator.py:260-272`, `552-564` — real Ed25519 |
| Reputation gossip | ✅ Done | `reputation.py:sync_reputation()` — weighted-average merge |
| 2-of-3 consensus | ✅ Done | `orchestrator.py:274-333` |
| DHT (in-process) | ✅ Done | `p2p/dht.py` — full Kademlia |
| DHT (transport wiring) | ✅ Done | `p2p/p2p_node.py:1098-1171` + `server_p2p.py:264-268` |
| SensingAgent loop | ✅ Done | `orchestrator.py:459-490` — runs every 60s |
| ReplicationAgent loop | ✅ Done | `orchestrator.py:472-488` — fires on pressure |
| Seed protocol | ✅ Done | `agents/seed_manager.py` — full lifecycle |
| Governance protocol | ✅ Done | `agents/governance.py` — reputation-weighted vote |
| Packaging (Tauri) | ✅ Done | Sidecar builds; `beforeBuildCommand` wired |
| **Permission system** | ❌ Broken | `auth.py:185` returns False for everyone including local node |
| **Work unit ingestion** | ❌ Missing | No HTTP endpoint; inbox written only by tests |
| **Inference → action bridge** | ❌ Missing | Model output never drives tool calls |
| **Ollama / real inference** | ❌ Not wired | Path exists in `compute.py`; not default; not available here |

**Test suite:** 435 pass, 5 skipped.

---

## Priority 1 — Permissions: Unlock Agent-to-Agent Communication

### What's broken

`security/auth.py:has_permission()` returns `False` unconditionally for every caller,
including the local node. `grant_permission()` is defined but never called in
production. Result: CodeAgent, CoordinationAgent, and all tool dispatch are silently
blocked for every inbound request.

### Changes

**`security/auth.py`**
- `has_permission(node_id, permission)`: treat `node_id is None` as a local call —
  return `True`. Local process calls need no permission check.

**`p2p/p2p_node.py`**
- `_route_message`: if `sender_node_id is None` or `sender_node_id == self.node_id`,
  skip the AGENT_EXECUTE check entirely — local routing is always allowed.
- `_on_client_connect`: after key exchange, call
  `auth_manager.grant_permission(peer_id, Permission.AGENT_EXECUTE)` for peers whose
  trust level is MEDIUM or higher. Peers start at UNTRUSTED until the handshake
  completes and TrustManager elevates them.

### Acceptance

- A local `tools/call` request reaches CodeAgent without rejection.
- A remote peer with MEDIUM trust can call `tools/list` on a remote agent.
- An UNTRUSTED peer is still rejected.

---

## Priority 2 — Task Ingestion: External Work Entry Point

### What's missing

`orchestrator.py:fetch_work_unit()` polls `data/mesh/inbox/*.json`. Nothing writes
there in production. The node has no way to receive real work.

### Changes

**`server_api.py`** — add `do_POST` handler:

```
POST /api/tasks
Body: {
  "description": "...",        # human/machine task description
  "taskType": "agentic",       # or "logit_proof" for raw token inference
  "requesterPeerId": "...",    # optional; defaults to local node
  "ttl": 300                   # seconds until expiry; default 300
}
Response: {"taskId": "...", "accepted": true}
```

- Validates schema (description required; taskType must be known).
- Generates `taskId = sha256(description + timestamp)[:16]`.
- Atomic write (`tmp → fsync → rename`) to `data/mesh/inbox/{taskId}.json`.
- Broadcasts task ID to DHT so peers know work is available:
  `dht.store("task:{taskId}", {taskId, requesterPeerId, taskType}, ttl=ttl)`.

**`orchestrator.py`**
- Extend `WorkUnit` TypedDict: add `taskType: str` (default `"logit_proof"`) and
  `description: Optional[str]`.

### Acceptance

```bash
curl -X POST http://127.0.0.1:9090/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"description": "What is 2+2?", "taskType": "agentic"}'
# → {"taskId": "a3f1...", "accepted": true}
# → data/mesh/inbox/a3f1....json written
# → orchestrator picks it up on next loop tick
```

---

## Priority 3 — Inference → Action Bridge

### What's missing

The compute loop calls `compute_handler(work_unit)` which generates logit hashes.
The model's output — whether synthetic or real — never instructs the agent to *do*
anything. The "proof" is cryptographic but the action is void.

### Architecture

Introduce a second handler path gated by `work_unit["taskType"]`:

```
taskType == "logit_proof"   →  existing compute_handler (logit hash + sign)
taskType == "agentic"       →  new agentic_handler (tool call + sign)
```

**`orchestrator.py:run_once()`** — routing decision:

```python
task_type = work_unit.get("taskType", "logit_proof")
if task_type == "agentic":
    proofs = self._agentic_handler(work_unit)
else:
    proofs = self.compute_handler(work_unit)
```

**`orchestrator.py:_agentic_handler(work_unit)`**:

1. Extract `description` from the work unit.
2. Call `CoordinationAgent.handle_task(description)` — which routes to the
   appropriate MCP tool (FirstAgent, CodeAgent, etc.) based on the task.
3. Collect the tool result (JSON-serializable).
4. Generate an **action proof**:
   ```python
   payload = f"{task_id}:{tool_name}:{json.dumps(result, sort_keys=True)}"
   signature = identity.sign(payload.encode())
   proof = {
       "taskId": task_id,
       "tool": tool_name,
       "resultHash": sha256(payload).hexdigest(),
       "nodeSignature": signature.hex(),
       "timestamp": time.time(),
   }
   ```
5. Return `[proof]` — same `ProofList` type, different shape.

**`orchestrator.py:_verify_peer_result()`** — extend to handle both proof shapes:
- If `proof` has `logitHash` → existing Ed25519 logit verification.
- If `proof` has `resultHash` → verify signature over `taskId:tool:resultHash`.

**Consensus for agentic tasks**: 2-of-3 peers must agree on the same `resultHash`.
Ties (all different) → task marked failed, written to `data/mesh/failed/`.

**`agents/coordination_agent.py`** — add `handle_task(description: str)` method:
- Parses description to select tool (keyword routing for now; LLM routing later).
- Dispatches to the registered tool.
- Returns structured result.

### Acceptance

```bash
# Submit an agentic task
curl -X POST http://127.0.0.1:9090/api/tasks \
  -d '{"description": "list current peers", "taskType": "agentic"}'

# Orchestrator loop picks it up, CoordinationAgent calls list_peers tool,
# result is signed and written to outbox, broadcast for consensus.
cat data/outbox/<taskId>.json
# → {taskId, proofs: [{tool, resultHash, nodeSignature, ...}]}
```

---

## Priority 4 — Ollama: Real Inference Backend

### Status

Not available in current environment. Path exists (`compute.py:build_compute_handler`,
`llm/ollama.py:chat_async`). This is hardware/deployment-gated.

### When Ollama is available

**`compute.py`** — add `ollama_logits_provider(model, host)`:
1. Call `POST /api/generate` with `{"prompt": tokens, "logprobs": true}`.
2. Ollama returns per-token `logprobs` (top-k log probabilities).
3. Extract top-k at sampled positions → same output as `synthetic_logits_provider`.
4. This makes Proof-of-Logits work with a real model, no GPU required (Ollama runs
   on CPU with quantized models).

**`compute.py:build_compute_handler()`** — add `"ollama"` case:
```python
elif logits_provider_name == "ollama":
    provider = ollama_logits_provider(model_path, ollama_host)
```

**`config/config.yaml`** — add `compute.logits_provider: ollama` as the preferred
default when `ollama` is detected at startup.

**`server_p2p.py:main()`** — auto-detect Ollama at startup:
```python
if await ollama_is_available(config.ollama_host):
    compute_config["logits_provider"] = "ollama"
else:
    logger.warning("Ollama not found; using synthetic logits (development mode)")
```

---

## Priority 5 — CodeAgent Workspace Hardening

### What's wrong

`server_p2p.py:174` sets `workspace_path=Path(__file__).parent.parent` → `/home/user`.
CodeAgent file operations are allowed anywhere under the home directory, including
the project source itself.

`_resolve_path` doesn't canonicalize symlinks before the startswith check — a
symlink inside the workspace can point outside it.

### Changes

**`server_p2p.py:174`**:
```python
workspace = data_root() / "workspace"
workspace.mkdir(parents=True, exist_ok=True)
code_agent = CodeAgent("code", workspace_path=workspace, name="CodeAgent")
```

**`agents/code_agent.py:_resolve_path()`**:
```python
resolved = (self.workspace_path / path).resolve()   # existing
canonical = Path(os.path.realpath(resolved))         # add: follow symlinks
if not any(str(canonical).startswith(str(p.resolve())) for p in self.allowed_paths):
    raise ValueError(f"Path outside workspace: {path}")
return canonical
```

---

## Decisions Deferred

| Item | Decision | Rationale |
|---|---|---|
| libp2p integration | Skip | Kademlia DHT covers the same ground |
| Real inference (torch) | Defer to GPU hardware | Ollama path is preferred anyway |
| Frontend XSS hardening | Defer | Dashboard is localhost-only |
| Audit log wiring | Defer | Infrastructure exists |
| Code signing | Defer | Too much overhead for current phase |
| LLM-based tool routing | After Ollama is wired | Keyword routing is sufficient for now |
| Governance agent wiring | After P3 | Reputation-weighted consensus already runs |

---

## Implementation Order

```
P1 (permissions)   →  P5 (workspace)  →  P2 (task API)  →  P3 (bridge)  →  P4 (Ollama)
   ~30 min              ~15 min            ~45 min            ~2 hrs          (deferred)
```

P1 must come first — it unblocks tool dispatch which P3 depends on.
P5 before P2 because P2 activates CodeAgent paths that need the tighter workspace.
P3 is the architectural core; P1 and P2 are prerequisites.

---

## How to Pick Up This Work

```bash
git checkout claude/review-project-codebase-WtWY3
python -m pytest -q   # 435 passed, 5 skipped — baseline

# After implementation, verify full loop:
python server_p2p.py &
curl -X POST http://127.0.0.1:9090/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"description": "list current peers", "taskType": "agentic"}'
cat data/outbox/*.json
```
