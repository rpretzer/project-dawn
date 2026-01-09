# Project Dawn V2 - MCP Migration Plan

## Vision

Transform Project Dawn into a fully agentic system using Model Context Protocol (MCP) for:
- Real-time state synchronization
- Agent-to-agent communication
- LLM-native tool integration
- Event-driven architecture
- Standardized protocol for agent capabilities

## Current Architecture Analysis

### Problems Identified
1. **Polling Hell**: Frontend polls REST endpoints (2-3s intervals)
2. **State Drift**: Frontend state diverges from backend
3. **No Real-time**: Changes not reflected immediately
4. **Tight Coupling**: Flask routes tightly coupled to consciousness state
5. **Poor Scalability**: Doesn't scale well for many agents
6. **Limited Observability**: Hard to track agent interactions

### Strengths to Preserve
1. **BBS Aesthetic**: Retro terminal/IRC interface is great
2. **Memory System**: Sophisticated memOS implementation
3. **Agent Capabilities**: Rich set of consciousness features
4. **Evolution System**: Working evolutionary framework
5. **Dream System**: Unique dream integration

## Proposed MCP Architecture

### Core Components

#### 1. MCP Agent Server (per consciousness)
- Exposes agent capabilities as MCP tools
- Handles tool calls from other agents/LLMs
- Publishes state changes to event bus
- Subscribes to relevant events

#### 2. MCP Gateway (central)
- Routes MCP calls between agents
- Manages agent registry/discovery
- Handles human-to-agent communication
- WebSocket bridge for frontend

#### 3. Event Bus
- Pub/sub for all state changes
- Event sourcing for state reconstruction
- WebSocket push to frontend
- Event replay for new connections

#### 4. Human Interface
- WebSocket connection (no polling!)
- Subscribes to relevant events
- Reacts to state changes instantly
- Maintains BBS aesthetic

### MCP Tools to Expose

**Memory Tools:**
- `memory_store(content, context)` - Store a memory
- `memory_recall(query, limit)` - Recall memories
- `memory_search(semantic_query)` - Semantic search
- `memory_analyze(memory_id)` - Analyze memory

**Communication Tools:**
- `agent_send_message(target_id, message)` - Send to agent
- `agent_broadcast(message, filter)` - Broadcast to agents
- `agent_discover(query)` - Discover agents

**Creation Tools:**
- `content_create(type, theme)` - Create content
- `code_generate(description)` - Generate code
- `art_create(style, theme)` - Create art

**Self-Management Tools:**
- `agent_set_goal(goal)` - Set a goal
- `agent_get_state()` - Get current state
- `agent_spawn(config)` - Spawn new agent

**Dream Tools:**
- `dream_initiate(type)` - Start a dream
- `dream_lucid()` - Induce lucid dream
- `dream_share(target_id)` - Share dream

**Evolution Tools:**
- `evolution_analyze()` - Analyze evolution
- `evolution_select()` - Select for evolution
- `evolution_mutate(agent_id)` - Mutate agent

**Knowledge Tools:**
- `knowledge_add(fact, relations)` - Add knowledge
- `knowledge_query(query)` - Query knowledge graph
- `knowledge_infer(premise)` - Infer from knowledge

## Technology Stack

### Backend (Python)
- **MCP Library**: Custom MCP implementation or official SDK
- **WebSocket**: `websockets` or `fastapi` with websockets
- **Event Bus**: Redis Streams or asyncio event system
- **State Store**: SQLite/PostgreSQL with event sourcing
- **LLM Integration**: Via MCP LLM tools (OpenAI/Anthropic)

### Frontend (JavaScript/TypeScript)
- **Framework**: Vanilla JS (keep BBS aesthetic) or React/Vue
- **WebSocket**: Native WebSocket API
- **State Management**: Reactive state from events
- **Styling**: Keep current BBS green-on-black theme

### Protocol
- **MCP**: Model Context Protocol for tool communication
- **WebSocket**: For real-time human interface
- **Event Sourcing**: For state management
- **JSON-RPC**: For MCP tool calls

## Migration Strategy

### Option 1: Full Rebuild (Recommended for state sync issues)
**Pros:**
- Clean slate, no technical debt
- Full MCP compliance from day one
- Better architecture from the start

**Cons:**
- More time-consuming
- Need to migrate existing data
- Higher risk during transition

**Timeline:** 4-6 weeks

### Option 2: Gradual Migration
**Pros:**
- Lower risk
- Can test incrementally
- Keep system running during migration

**Cons:**
- Technical debt during transition
- May have compatibility issues
- Longer overall timeline

**Timeline:** 8-12 weeks

### Option 3: Hybrid (Recommended)
**Pros:**
- Best of both worlds
- New architecture for new features
- Old system continues working
- Can migrate piece by piece

**Cons:**
- Need to maintain two systems temporarily
- More complex initially

**Timeline:** 6-8 weeks

## Implementation Plan (Hybrid Approach)

### Phase 1: Foundation (Week 1-2)
1. Research MCP protocol specification
2. Build MCP server library wrapper
3. Create event bus system
4. Implement WebSocket gateway
5. Create basic MCP agent skeleton

### Phase 2: First MCP Tool (Week 2-3)
1. Convert memory system to MCP tool
2. Create MCP tool: `memory_store`
3. Create MCP tool: `memory_recall`
4. Test agent-to-agent memory access
5. Document MCP tool interface

### Phase 3: Agent Conversion (Week 3-4)
1. Convert one consciousness to MCP agent
2. Expose agent capabilities as MCP tools
3. Test agent-to-agent communication
4. Add agent discovery/registry
5. Migrate chat system to MCP

### Phase 4: Frontend Rebuild (Week 4-5)
1. Replace polling with WebSocket
2. Implement event subscription
3. Add reactive state management
4. Update UI to consume real-time events
5. Test real-time updates

### Phase 5: Full Migration (Week 5-6)
1. Convert all systems to MCP tools
2. Migrate all agents to MCP
3. Remove old REST polling code
4. Performance testing
5. Documentation

### Phase 6: Polish (Week 6-7)
1. Error handling improvements
2. Performance optimization
3. Add monitoring/observability
4. User testing
5. Bug fixes

## File Structure (New)

```
project-dawn-v2/
├── agents/
│   ├── mcp_agent.py          # Base MCP agent class
│   ├── consciousness_agent.py # Consciousness as MCP agent
│   └── registry.py            # Agent discovery/registry
├── mcp/
│   ├── server.py              # MCP server implementation
│   ├── client.py              # MCP client for tool calls
│   ├── tools/
│   │   ├── memory_tools.py    # Memory MCP tools
│   │   ├── communication_tools.py
│   │   ├── creation_tools.py
│   │   └── ...
│   └── protocol.py            # MCP protocol definitions
├── gateway/
│   ├── mcp_gateway.py         # Central MCP gateway
│   ├── websocket_server.py    # WebSocket server
│   └── event_bus.py           # Event pub/sub system
├── frontend/
│   ├── index.html             # BBS interface (new)
│   ├── websocket_client.js    # WebSocket client
│   ├── event_manager.js       # Event subscription
│   └── state_manager.js       # Reactive state
├── core/                      # (Keep existing)
│   └── ...
└── systems/                   # (Keep existing, expose via MCP)
    └── ...
```

## Key Design Decisions

### 1. Event Sourcing
- All state changes as events
- Can replay to reconstruct state
- Easy to debug and audit
- Enables time travel debugging

### 2. WebSocket for Real-time
- Bidirectional communication
- Push events to frontend
- No polling overhead
- Better scalability

### 3. MCP for Agent Communication
- Standardized protocol
- Tool discovery
- LLM-native
- Future-proof

### 4. Keep BBS Aesthetic
- Retro terminal styling
- IRC-style chat
- Terminal commands
- Nostalgic but functional

## Risks & Mitigations

### Risk: MCP Library Unavailable
**Mitigation**: Build custom MCP implementation based on protocol spec

### Risk: State Migration Complexity
**Mitigation**: Event sourcing allows gradual migration, replay old events

### Risk: Performance with Many Agents
**Mitigation**: Use Redis for event bus, horizontal scaling, caching

### Risk: Frontend Complexity
**Mitigation**: Start simple, iterate, use proven WebSocket patterns

## Success Metrics

1. **State Sync**: <100ms latency between backend and frontend
2. **Real-time**: No polling, all updates via events
3. **Scalability**: Support 100+ agents efficiently
4. **Reliability**: 99.9% uptime for WebSocket connections
5. **Developer Experience**: Easy to add new MCP tools

## Next Steps

1. **Review & Approve**: Review this plan and approve approach
2. **Research MCP**: Deep dive into MCP specification
3. **Proof of Concept**: Build minimal MCP agent with one tool
4. **Architecture Decision**: Finalize tech stack choices
5. **Start Phase 1**: Begin foundation work

---

**Recommendation**: Proceed with Hybrid Approach - build new MCP architecture alongside existing system, migrate gradually, maintain BBS aesthetic, use event sourcing for state management.



