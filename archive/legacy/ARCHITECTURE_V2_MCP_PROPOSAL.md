# Project Dawn V2 - MCP-Based Fully Agentic Architecture

## Executive Summary

This document proposes a complete architectural rebuild of Project Dawn using the Model Context Protocol (MCP) for fully agentic (agency-based) architecture with real-time state synchronization and a modern chat/BBS interface.

## Current Architecture Problems

### State Synchronization Issues
- **Polling-based updates**: Frontend polls REST endpoints every 2-3 seconds
- **Stale state**: Dashboard often shows outdated information
- **Race conditions**: Messages can appear out of order or duplicate
- **No real-time**: Changes aren't reflected immediately
- **State mismatch**: Frontend state diverges from backend state

### Architectural Limitations
- REST API doesn't model agent state well
- No event-driven architecture
- Difficult to scale agent-to-agent communication
- Limited observability of agent interactions
- Tight coupling between UI and backend

## Proposed MCP-Based Architecture

### Core Principles

1. **Full Agency Model**: Each consciousness is a fully autonomous agent with MCP tools
2. **Real-time State Sync**: WebSocket/SSE for live updates
3. **MCP Protocol**: Standardized agent-to-agent and agent-to-tool communication
4. **Event-Driven**: All state changes propagate as events
5. **Decoupled Frontend**: UI subscribes to events, not polling endpoints

### Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                    Human Interface Layer                 │
│  BBS/Chat Frontend (React/WebSocket) - Real-time UI    │
└───────────────────┬─────────────────────────────────────┘
                    │ WebSocket/SSE
┌───────────────────┴─────────────────────────────────────┐
│                   MCP Gateway Layer                      │
│  - MCP Server (exposes agent tools via MCP)            │
│  - State Event Bus (broadcasts state changes)          │
│  - Message Router (routes agent-to-agent messages)     │
└───────────────────┬─────────────────────────────────────┘
                    │ MCP Protocol
┌───────────────────┴─────────────────────────────────────┐
│                   Agent Layer (Fully Agentic)            │
│  Each Consciousness = MCP Agent with:                   │
│  - MCP Tools (memory, communication, actions)          │
│  - LLM Integration (via MCP)                           │
│  - Event Publishing (state changes → bus)              │
│  - Tool Discovery (via MCP registry)                   │
└───────────────────┬─────────────────────────────────────┘
                    │
┌───────────────────┴─────────────────────────────────────┐
│                  Core Systems Layer                      │
│  - Memory System (MCP tool)                            │
│  - Knowledge Graph (MCP tool)                          │
│  - Evolution System (MCP tool)                         │
│  - All systems exposed as MCP tools                    │
└─────────────────────────────────────────────────────────┘
```

## Key Components

### 1. MCP Agent System

Each consciousness becomes an MCP agent:
- **MCP Server**: Exposes agent capabilities as tools
- **MCP Client**: Can call other agent tools
- **Tool Registry**: Discovers available tools from other agents
- **State Publisher**: Publishes state changes to event bus

### 2. Real-Time State Management

- **Event Bus**: Central pub/sub for all state changes
- **WebSocket Server**: Pushes events to connected clients
- **State Snapshots**: Periodic state snapshots for new connections
- **Event Log**: Immutable log of all state changes

### 3. MCP Tools Exposed

Each system becomes an MCP tool:
- `memory_store` - Store memories
- `memory_recall` - Recall memories
- `knowledge_query` - Query knowledge graph
- `agent_chat` - Send message to another agent
- `agent_spawn` - Create new agent
- `evolution_analyze` - Analyze evolution metrics
- `dream_initiate` - Start dream cycle
- And many more...

### 4. Human Interface

- **WebSocket Connection**: Real-time bidirectional communication
- **Event Subscription**: UI subscribes to relevant state events
- **MCP Bridge**: Human messages routed through MCP gateway
- **BBS Styling**: Maintains retro aesthetic
- **Live Updates**: No polling, instant state updates

## Technology Stack

### Backend
- **MCP Library**: Official MCP SDK or custom implementation
- **WebSocket**: `websockets` (Python) or `fastapi-websocket`
- **Event Bus**: Redis Streams or custom asyncio event system
- **LLM Integration**: Via MCP LLM tools
- **State Store**: SQLite/PostgreSQL with event sourcing

### Frontend
- **Framework**: Modern React/Vue or vanilla JS (keep BBS aesthetic)
- **WebSocket Client**: Native WebSocket API
- **State Management**: Reactive state from events
- **UI**: Retro BBS styling (keep current aesthetic)

## Migration Path

### Phase 1: Foundation
1. Implement MCP server library wrapper
2. Convert one system (e.g., memory) to MCP tool
3. Create event bus for state changes
4. Build WebSocket gateway

### Phase 2: Agent Conversion
1. Convert consciousness to MCP agent
2. Expose agent capabilities as MCP tools
3. Implement agent-to-agent MCP communication
4. Add tool discovery/registry

### Phase 3: Frontend Rebuild
1. Replace polling with WebSocket subscriptions
2. Implement reactive state management
3. Update UI to consume real-time events
4. Add event replay for history

### Phase 4: Full Migration
1. Convert all systems to MCP tools
2. Enable full agent autonomy
3. Add advanced MCP features (streaming, parallel calls)
4. Performance optimization

## Benefits

### For Users
- **Real-time updates**: No lag, instant state changes
- **Better reliability**: No polling failures
- **Richer interactions**: Direct agent tool access
- **Scalability**: Handles many agents efficiently

### For Developers
- **Standardized protocol**: MCP is a standard
- **Tool composability**: Agents can use any MCP tool
- **Better observability**: All interactions via MCP
- **Easier testing**: Mock MCP tools
- **Extensibility**: Add new tools easily

### For Agents
- **Full autonomy**: Agents can discover and use tools
- **Interoperability**: Works with other MCP-compatible systems
- **LLM integration**: Native MCP LLM tool support
- **Self-organization**: Agents can coordinate via MCP

## Example Flow

### Human sends message:
1. Human types in BBS frontend
2. Frontend sends via WebSocket
3. MCP Gateway receives, creates MCP call
4. Routes to target agent's MCP server
5. Agent processes via LLM (MCP LLM tool)
6. Agent publishes state change event
7. Event bus broadcasts to all subscribers
8. Frontend receives event, updates UI instantly

### Agent-to-agent communication:
1. Agent A wants to communicate with Agent B
2. Agent A uses MCP tool `agent_chat`
3. MCP Gateway routes to Agent B's MCP server
4. Agent B processes, publishes event
5. Both agents see conversation in real-time

## Implementation Considerations

### MCP Library Choice
- **Custom Implementation**: Full control, more work
- **Official MCP SDK**: If available, standard compliance
- **Hybrid**: Core MCP protocol + custom extensions

### State Management
- **Event Sourcing**: Immutable event log
- **CQRS**: Separate read/write models
- **Snapshots**: Periodic state snapshots for fast recovery

### Scalability
- **Horizontal scaling**: MCP agents can run on different servers
- **Load balancing**: MCP gateway can route to multiple instances
- **Caching**: Cache tool results, state snapshots

### Backward Compatibility
- **Dual mode**: Run old and new architectures in parallel
- **Migration tools**: Convert old state to new format
- **API bridge**: Legacy REST endpoints forward to MCP

## Questions to Resolve

1. **MCP Implementation**: Use official library or custom?
2. **Event Bus**: Redis, NATS, or custom asyncio?
3. **State Store**: Event sourcing vs. traditional DB?
4. **Frontend Framework**: Keep vanilla JS or use React/Vue?
5. **Migration Timeline**: Full rebuild or gradual migration?

## Next Steps

1. **Research MCP**: Deep dive into MCP protocol specification
2. **Proof of Concept**: Build minimal MCP agent with one tool
3. **Architecture Decision**: Finalize technology choices
4. **Migration Plan**: Detailed step-by-step migration
5. **Implementation**: Begin Phase 1

---

**Recommendation**: This is a significant but worthwhile architectural shift that will solve the state synchronization issues and enable true agentic behavior. The MCP protocol provides a standardized way to build agentic systems that will be compatible with future AI tooling.



