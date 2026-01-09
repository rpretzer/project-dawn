## Project Dawn Roadmap (Utility-First)

This roadmap focuses on making the system **useful, safe, and operable in public**, while keeping “agentic” behavior real (task execution, delegation, spawning) and making “evolution” concrete (policies/tools/strategies that measurably improve outcomes).

### Guiding principles
- **Import-time safety**: Optional subsystems must not crash unrelated features.
- **Real-time collaboration**: Humans + agents share rooms, context, tasks, and results.
- **Bounded autonomy**: Agents can do work, but within clear budgets (time, tools, permissions).
- **Measurable iteration**: Every “evolution” step must connect to observable metrics (ratings, completion rates, latency, cost).
- **Production defaults**: Auth, rate limiting, audit logs, and “prod mode” safeguards are on by default.

---

## Phase 0 — Public-ready core (Now → next)

### Outcomes
- Stable multi-user real-time chat + orchestration that doesn’t fall over in typical public usage.
- Clear admin controls, auditability, and safe defaults.

### Work items
- **Auth + session posture**
  - Cookie-based auth (HttpOnly), `/api/me`, `/api/logout` ✅
  - Require `JWT_SECRET` in `DAWN_ENV=prod` ✅
  - Add CSRF posture docs (cookie + same-site) and reverse-proxy guidance
- **Moderation**
  - Ban/mute/room policy enforcement ✅
  - Persist moderation audit events ✅
  - Add `/unban`, `/unmute`, `/room status` (read + show effective policy)
- **Operational stability**
  - Structured logs (JSON logs option), request IDs, per-event tracing
  - Graceful shutdown of background workers ✅ (orchestrator cleanup)
  - Health endpoints: liveness + readiness + dependency checks
- **DX**
  - Pin required deps and separate optional deps more clearly
  - Add “production quickstart” doc with env vars and deployment examples

---

## Phase 1 — Useful agent work (tool ecosystem)

### Outcomes
- Agents can reliably “go do stuff” beyond chatting: read/write project artifacts, search, summarize, open PRs/issues (optionally), and manage knowledge.

### Feature adds (high utility)
- **Tool registry & permissions**
  - Permission model: tools allowed per room + per role + per agent
  - Per-tool budgets (rate limits, cost limits)
- **Core tools (first-party)**
  - Workspace toolset: safe read/search/edit + tests + formatting (bounded)
  - GitHub toolset: issue/PR creation, comment, status (bounded, optional)
  - Web retrieval toolset (optional): fetch URLs with allowlist + caching
- **Plugin system reactivation**
  - Make `watchdog` optional and load plugins lazily
  - Signed plugin manifests + capability declarations
  - Sandbox policy that is real (deny-by-default file/network unless granted)

### UI/UX improvements
- Task panel: active/queued/completed with filters and per-agent views
- “One-click” conversions: chat message → task → delegated subtask
- Streaming: partial agent outputs + intermediate artifacts in-room

---

## Phase 2 — Memory & knowledge that actually help

### Outcomes
- Memory improves results measurably (less repetition, better continuity) without bloating prompts or leaking data.

### Feature adds (high utility)
- **Memory namespaces**
  - Separate: room memory vs user memory vs agent memory vs project memory
  - Retention + deletion policies by namespace (GDPR-ish controls)
- **Better retrieval**
  - Embedding-backed search (optional provider) with caching
  - “Evidence packs”: citations for what memory influenced an answer
- **Knowledge graph (optional but real)**
  - Make `networkx` truly optional (already runtime-gated)
  - Add import/export and admin-only controls
  - Use the graph for routing tasks to the best agent/tool

---

## Phase 3 — Non-superficial evolution (real improvement loop)

### Outcomes
- Agents improve over time *in ways you can see*: faster completion, higher ratings, better delegation, better tool-use.

### Implementation plan
- **Fitness metrics** (tracked per agent)
  - Task completion rate, median time-to-complete, user rating average, tool error rate
  - Optional: cost per task, retries, “human intervention” rate
- **Evolvable objects**
  - Agent policies ✅ (now stored per agent): budgets, delegation bias, verbosity
  - Planner prompts: different planning templates and heuristics (A/B)
  - Tool routing: which tools to prefer for which task types
- **Selection & mutation**
  - Periodically propose mutations and run them on a subset of tasks
  - Keep winners, roll back losers, and log the rationale
- **Safety**
  - Evolution cannot grant new permissions; only tune within allowed bounds

---

## Phase 4 — “Public product” polish

### Outcomes
- Deployable, monitorable, maintainable service with clear documentation.

### Feature adds
- Observability: metrics dashboard (latency, errors, task throughput)
- Rate limit + abuse protection: per-IP, per-user, per-room
- Backups: chat/tasks/memory export + restore tooling
- Deployment: Docker image, sample systemd service, reverse proxy configs
- Docs: accurate naming (agent terminology), remove misleading “consciousness” claims

---

## Definition of Done (for “public”)
- **Security**: auth required in prod by default; guest access explicitly enabled; moderation/audit present.
- **Reliability**: background workers stop cleanly; no import-time crashes from optional deps.
- **Utility**: agents can execute tasks with tools and produce artifacts; humans can rate results.
- **Clarity**: terminology matches reality; docs describe what is simulated vs real.

