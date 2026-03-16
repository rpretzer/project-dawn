# AGENTS.md — Project Dawn

Who is available to work, what they can do, and what they can't yet.

---

## The Interface: BaseAgent

**`agents/base_agent.py`**

All agents extend `BaseAgent`. It provides:

- `register_tool(name, description, handler, inputSchema)` — registers an MCP tool
- `get_tools()` / `has_tool(name)` — introspection
- `async initialize()` — load persisted state; override in subclasses
- `async start()` / `async stop()` — lifecycle
- `save_state()` / `_load_state()` — atomic persistence to `data/agents/{agent_id}/state.json`

Each agent wraps an `MCPServer` instance (`self.server`) that speaks JSON-RPC 2.0. Tools,
resources, and prompts are registered on that server. The `P2PNode` holds a reference to
`self.server`, not the agent directly — keep that boundary in mind.

State is persisted using the `tmp → fsync → rename` pattern. All subclasses inherit this.
Do not bypass it.

---

## Registered Agents

Three agents are instantiated and registered at startup in `server_p2p.py:143–158`.

---

### FirstAgent

**File:** `agents/first_agent.py`
**Registered as:** `agent1`
**Status:** Core tools work. Resource handlers are scaffolding (`pass` in several methods).

A general-purpose utility agent covering memory, search, knowledge, notifications, channels,
and database operations. Originally built to test the MCP system end-to-end. It is the broadest
agent in scope and the least focused.

**Tools (22):**

| Category | Tools |
|---|---|
| Memory | `memory_store`, `memory_recall`, `memory_list`, `memory_delete` |
| Search | `search_text`, `search_semantic`, `index_content`, `knowledge_query`, `web_search` |
| Communication | `notification_send`, `notification_list`, `channel_create`, `channel_message` |
| Database | `db_query`, `db_schema`, `data_transform`, `data_analyze`, `data_export` |
| System | `system_status`, `log_query`, `process_list`, `health_check` |

All storage is in-memory. Nothing persists across restarts. This is correct for a test agent
but limits its usefulness in a long-running mesh.

**Resources:** 11 declared (`memory://stats`, `search://index`, `system://metrics`, etc.).
Several resource handlers contain `pass` — they are declared but return nothing useful.

**Prompts:** 8 (`memory_search`, `search_strategy`, `knowledge_synthesis`, `query_optimization`,
`diagnostic_analysis`, others).

**Honest assessment:** This agent is best understood as a harness for testing the MCP protocol
machinery. It is not a production compute agent. Its 22 tools make it useful for ad-hoc tasks
but it has no meaningful role in the Proof-of-Logits pipeline.

---

### CodeAgent

**File:** `agents/code_agent.py`
**Registered as:** `code`
**Status:** File operations fully working. Code execution sandbox wired. Some resource handlers
are stubs.

A focused agent for file system operations and code execution. Scoped to a `workspace_path`
(defaults to the project root). Has security constraints: path traversal is blocked, execution
is sandboxed with a 30-second timeout and 1MB output limit.

**Tools (8):**

| Tool | What it does |
|---|---|
| `file_read` | Read file contents with path security check |
| `file_write` | Write file using atomic tmp→fsync→rename |
| `file_list` | List directory with optional filters |
| `file_search` | Find files by pattern (fnmatch) |
| `code_analyze` | Static analysis: complexity, security issues, documentation coverage |
| `code_execute` | Execute code in sandbox with timeout |
| `code_format` | Format (black/prettier) and lint |
| `code_test` | Run tests (pytest/jest) |

**Resources:** 4 declared (`file://tree`, `code://dependencies`, `code://metrics`,
`file://history`). `code://dependencies` and `code://metrics` are stubs.

**Prompts:** 3 (`code_review`, `code_explanation`, `refactoring_suggestion`).

**Honest assessment:** The file and execution tools are genuinely useful and correctly
implemented. The static analysis in `code_analyze` is limited — it counts things but does
not do deep semantic analysis. This agent is a solid foundation; the resource stubs are
the main gap.

---

### CoordinationAgent

**File:** `agents/coordination_agent.py`
**Registered as:** `coordinator`
**Status:** Fully implemented. All tools and resources functional. Integrated with P2PNode.

The most important agent currently in the system. It has a direct reference to the `P2PNode`
and can see the full distributed agent registry. It is the network's connective tissue —
the agent that knows what other agents exist, manages tasks, and can call tools on remote peers.

**Tools (9):**

| Tool | What it does |
|---|---|
| `agent_list` | List agents (local and remote) with optional filtering |
| `agent_call` | Call a tool on another agent by agent ID |
| `agent_broadcast` | Broadcast a message to multiple agents |
| `task_create` | Create a task with dependencies and priority |
| `task_list` | List tasks with filtering |
| `network_peers` | Discover and list network peers |
| `network_info` | Get network statistics |
| `node_info` | Get info about a specific node |
| `agent_discover` | Discover agents on the network |

**Resources:** 6 (`agent://registry`, `room://active`, `task://queue`, `agent://api-reference`,
`network://topology`, `network://stats`). All implemented.

**Prompts:** 5 (`agent_coordination`, `task_decomposition`, `agent_selection`,
`network_analysis`, `peer_recommendation`).

**Honest assessment:** This is the agent to reach for when orchestrating work across the mesh.
Its network visibility makes it the natural home for any logic that needs to reason about
what the network as a whole is doing. It will be the primary integration point for the
sensing agent and replication protocol when those are built.

---

## Supporting Infrastructure

### DistributedAgentRegistry

**File:** `consensus/agent_registry.py`

Not an agent — a CRDT-based registry for distributed agent discovery. Stores `AgentInfo`
records (agent_id, node_id, name, tools, resources, prompts, health_score, availability)
and syncs them across peers via the gossip layer. The `CoordinationAgent` reads from this
registry when listing remote agents.

Fully implemented with eventual-consistency semantics.

### TaskManager

**File:** `agents/task_manager.py`

Not an agent — a utility class used by `CoordinationAgent`. Manages task lifecycle
(OPEN → ASSIGNED → IN_PROGRESS → COMPLETED / FAILED / CANCELLED), persistence, and
distributed sync. Tasks have dependencies, priority, and timestamps.

Fully implemented.

---

## Agents That Don't Exist Yet

These are gaps, not proposals. They are documented here because future sessions should
build toward them rather than discover the absence and improvise.

### Sensing Agent (needed for Phase 2)

Responsible for maintaining the capability map at `data/mesh/capability_map.json`. Reads
the agent feed, consensus receipts, and failed task records. Identifies regions of consistent
failure in task space. Broadcasts evolutionary signals when the capability horizon is under
sustained pressure. Does not make replication decisions — surfaces the signal only.

This agent is the prerequisite for the entire self-replication architecture. Nothing in
Phase 2 can be built without it.

### Replication Agent (needed for Phase 2)

Handles the seed lifecycle: receives evolutionary signals from the sensing agent, identifies
candidate parent agents, generates seed blueprints, issues compute reserves from the commons
pool, monitors germination windows, and culls agents that fail to self-sustain.

Should not be built until the sensing agent exists and the capability map has real data in it.

### Compute Agent (gap in current system)

There is no agent whose primary role is running inference and generating Proof-of-Logits.
The orchestrator (`orchestrator.py`) handles this directly, not through the agent framework.
At some point the compute work should be surfaced as a first-class agent so it can be
registered, discovered, called remotely, and governed like other agents. This is a medium-term
gap — the orchestrator works, but the architecture is inconsistent.

---

## Quick Reference

| Agent ID | Class | File | Tools | Ready |
|---|---|---|---|---|
| `agent1` | FirstAgent | `agents/first_agent.py` | 22 | Partial |
| `code` | CodeAgent | `agents/code_agent.py` | 8 | Mostly |
| `coordinator` | CoordinationAgent | `agents/coordination_agent.py` | 9 | Yes |
| *(sensing)* | — | — | — | Not built |
| *(replication)* | — | — | — | Not built |
| *(compute)* | — | — | — | Not built |

When building a new agent: extend `BaseAgent`, register tools via `register_tool()`, add
instantiation to `server_p2p.py`, and document it here.
