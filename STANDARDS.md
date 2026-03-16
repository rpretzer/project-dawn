# STANDARDS.md — Project Dawn

Code conventions, architectural patterns, and layer boundaries for all contributors.
When a pattern here conflicts with existing code, the existing code is wrong.

---

## Atomic File Writes (Non-Negotiable)

Every write of persistent state uses the `tmp → fsync → rename` pattern. Never write
directly to the target path.

**Python:**
```python
import os
import tempfile

tmp_fd, tmp_path = tempfile.mkstemp(dir=target_path.parent, suffix=".tmp")
try:
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, target_path)
except Exception:
    os.unlink(tmp_path)
    raise
```

**Why:** Project Dawn is designed to run continuously on consumer hardware. A partial write
(power loss, OOM kill, SIGKILL) corrupts state silently. `os.replace()` is atomic on all
POSIX systems. This is not optional.

**Append-only logs** (`agent_feed.jsonl`, etc.) are the exception — sequential appends to
a JSONL file are safe by design. Still flush after each write.

**Scope:** All writes to `data/vault/`, `data/mesh/`, `data/outbox/`, and `data/agents/`.
Not required for build scripts, test fixtures, or ephemeral temp files.

---

## Error Handling

**Never use a bare `except:`** — it catches `KeyboardInterrupt`, `SystemExit`, and
`GeneratorExit`, which will silently eat shutdown signals.

```python
# Wrong
try:
    do_thing()
except:
    pass

# Right — specific, logged
try:
    do_thing()
except Exception as e:
    logger.debug(f"Failed to do thing: {e}")
```

**Never silently swallow exceptions in business logic.** If you can't handle it, let it
propagate or log it at an appropriate level.

**Exception levels:**
- `logger.debug` — expected transient failures (container kill on timeout, optional feature missing)
- `logger.warning` — unexpected but recoverable (peer disconnected mid-handshake)
- `logger.error` — something failed that affects the user (proof validation failed, consensus aborted)
- `raise` — let it propagate when you can't do anything useful locally

---

## Imports

All imports go at the top of the file. In-function imports are permitted only to avoid
genuine circular dependency issues — document why with a comment.

```python
# Wrong — lazy in-function import
def add_peer(node_id):
    import time
    record.added_at = time.time()

# Right — top-level
import time
```

Import order (follow PEP 8):
1. Standard library
2. Third-party packages
3. Local modules

Type imports belong with standard library:
```python
from typing import Any, Dict, List, Optional  # Any must be explicit — do not use bare Any
```

---

## Async

Use `async def` only when the function actually awaits something. A function that returns
a value synchronously without awaiting is just a regular function.

```python
# Wrong — misleads callers into thinking I/O is happening
async def get_agent_count(self) -> int:
    return len(self.agents)

# Right
def get_agent_count(self) -> int:
    return len(self.agents)
```

Exception: MCP resource handler registration requires async callables regardless. This is
a framework constraint — document it with a comment.

---

## Logging

Use module-level loggers, not root logger or print statements:
```python
logger = logging.getLogger(__name__)
```

Never log private keys, raw message content from untrusted peers, or full stack traces at
INFO or above in production paths. Peer-sourced data in logs is an information leak.

Truncate node IDs in log messages: `{node_id[:16]}...`

---

## Architecture Layers

Three layers. Respect the boundaries.

```
Rust / Tauri (src-tauri/)
    ↕ file-based IPC (resource_state.json)
Python Backend
    ↕ WebSocket JSON-RPC 2.0
JavaScript Frontend (frontend/)
```

**Rust → Python:** Only via `data/mesh/resource_state.json`. The Rust layer writes it;
the Python layer reads it. Do not introduce sockets or pipes between them without a
documented reason.

**Python → Frontend:** Only via the WebSocket server in `server_p2p.py`. The frontend
is a consumer of state, not a source of truth.

**Within Python:** The layering is:
```
orchestrator.py          ← main loop, highest level
agents/, mcp/            ← agent framework
p2p/, communication.py   ← networking
crypto/, security/       ← primitives
resilience/              ← cross-cutting infrastructure
```

Lower layers must not import from higher layers. `crypto/` does not import from `agents/`.
`p2p/` does not import from `orchestrator.py`. If you find yourself needing to violate
this, you have a design problem — solve it with an interface or a callback, not a direct
import.

---

## Frontend HTML Injection

All peer-sourced data rendered into the DOM must be escaped. This includes anything from
WebSocket responses, agent tool results, and peer metadata.

Use `escapeHtml()` before inserting any string into `innerHTML`. Every class that renders
dynamic content must have its own `escapeHtml()` — do not assume it comes from a parent.

```javascript
escapeHtml(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
```

For `data-*` attributes, use double-quote delimiters and escape the value:
```javascript
// Wrong — single-quote attribute breaks if value contains '
`data-item='${JSON.stringify(item)}'`

// Right
`data-item="${escapeHtml(JSON.stringify(item))}"`
```

SVG content rendered from peer data follows the same rules — SVG injection is real.

Static HTML strings (hardcoded templates with no interpolation) do not need escaping.

---

## Configuration

Config lives in `config/config.yaml` with `PROJECT_DAWN_*` environment variable overrides.
Ports, timeouts, paths, and feature flags go there — not hardcoded in module bodies.

The canonical defaults are in `config/config.py`. If you find yourself writing a hardcoded
port number somewhere, move it to config.

---

## Testing

Tests that require real sockets or real network I/O are not skipped — they are fixed.
This project is a P2P network. Skipping all network tests is skipping the tests that matter.

Use `synthetic_logits_provider` for tests that exercise the proof pipeline. It is
deterministic, fast, and requires no GPU.

Test file naming: `tests/test_{module_name}.py`. One test file per module.

Do not write tests that mock so heavily they test nothing. A test of `orchestrator.py`
that mocks every dependency is not testing the orchestrator.

---

## Commit Messages

Format: imperative mood, 72-char subject, blank line, body explaining *why* if not obvious.

```
Fix proof validation stub in orchestrator.py

validate_local_proof() was returning bool(proofs), accepting any
non-empty list as valid. A compromised node could submit fabricated
proofs and earn reputation without doing real work. Now calls the
same Ed25519 verification path used for peer proofs.
```

Reference the specific code location in the body when the change is security-relevant.

---

## What Not to Change

These are intentional design decisions. Understand them before touching them.

- **File-based Rust↔Python IPC** (`resource_state.json`) — deliberate choice, not an oversight
- **Atomic write pattern** — non-negotiable, see above
- **PGP-anchored identity** — the public key is the stable peer identity; don't route around it
- **Proof-of-Logits mechanism** — the core differentiator; preserve the sampling and signing logic
- **`synthetic_logits_provider` as default** — correct for development; the path to real inference
  is a config option, not a code change
