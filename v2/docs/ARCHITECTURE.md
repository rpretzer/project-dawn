# Project Dawn V2 - Architecture

## Overview

Complete rewrite with Model Context Protocol (MCP) for fully agentic architecture. Built from scratch, guided by original philosophy but using modern standardized protocols.

## Core Principles

1. **Fully Agentic**: Each agent is autonomous with MCP tools
2. **MCP Protocol**: Standardized agent-to-agent communication
3. **Real-time**: WebSocket-based, no polling
4. **Event-Driven**: All state changes as events
5. **Event Sourcing**: Immutable event log for state
6. **Clean Slate**: No old code, only new implementations

## Architecture Layers

```
┌──────────────────────────────────────────────────────┐
│              Human Interface Layer                  │
│  BBS/Chat Frontend (MCP Client) - Real-time UI     │
│  - Event-driven updates                             │
│  - No polling                                       │
│  - Retro aesthetic                                  │
│  - Connects via Host                                │
└───────────────┬──────────────────────────────────────┘
                │ MCP Client Session (JSON-RPC 2.0)
┌───────────────┴──────────────────────────────────────┐
│              MCP Host Layer (per official spec)    │
│  - Manages all client instances                     │
│  - Enforces security policies (OAuth 2.1)          │
│  - Coordinates AI integration                       │
│  - Routes messages between clients and servers      │
│  - Tool registry & discovery                          │
│  - Event bus (pub/sub)                              │
│  - WebSocket server                                 │
└───────────────┬──────────────────────────────────────┘
                │ MCP Protocol (JSON-RPC 2.0)
┌───────────────┴──────────────────────────────────────┐
│              Agent Layer (MCP Servers)              │
│                                                      │
│  ┌─────────────┐        ┌─────────────┐           │
│  │   Agent 1   │        │   Agent 2   │           │
│  │ (MCP Server)│◄──────►│ (MCP Server)│           │
│  │             │ MCP    │             │           │
│  │ Exposes:    │        │ Exposes:    │           │
│  │ - Tools     │        │ - Tools     │           │
│  │ - Resources │        │ - Resources │           │
│  │ - Prompts   │        │ - Prompts   │           │
│  │             │        │             │           │
│  │ Also:       │        │ Also:       │           │
│  │ - MCP Client│        │ - MCP Client│           │
│  └─────────────┘        └─────────────┘           │
│                                                      │
│  Each agent:                                         │
│  - Exposes MCP tools/resources/prompts             │
│  - Can be MCP client (call other agents)           │
│  - Publishes state events                           │
│  - Maintains stateful session                       │
└──────────────────────────────────────────────────────┘
```

## Component Details

### 1. MCP Protocol Layer

**Purpose**: Standardized agent-to-agent and agent-to-tool communication

**Components**:
- `protocol.py` - JSON-RPC 2.0 message handling
- `transport.py` - WebSocket/HTTP transport
- `server.py` - MCP server implementation
- `client.py` - MCP client for tool calls
- `tools.py` - Tool definition & registry

**Key Features**:
- JSON-RPC 2.0 base protocol
- Tool discovery (`tools/list`)
- Tool execution (`tools/call`)
- WebSocket transport (primary)
- HTTP transport (optional)

### 2. Gateway Layer

**Purpose**: Central hub for agent coordination and human access

**Components**:
- `mcp_gateway.py` - Central MCP gateway
- `router.py` - Message routing
- `event_bus.py` - Event pub/sub system
- `websocket_server.py` - WebSocket server for frontend

**Key Features**:
- Tool registry for all agents
- Message routing between agents
- Event bus for state changes
- WebSocket server for frontend
- Agent discovery

### 3. Agent Layer

**Purpose**: Autonomous agents with MCP capabilities

**Components**:
- `base_agent.py` - Base agent class
- `agent.py` - Main agent implementation
- `registry.py` - Agent discovery

**Key Features**:
- Each agent is an MCP server
- Agents expose tools (memory, chat, etc.)
- Agents can call other agents' tools
- Agents publish state events
- Agents maintain own state

### 4. Frontend Layer

**Purpose**: BBS-style interface for human interaction

**Components**:
- `index.html` - Main interface
- `websocket.js` - WebSocket client
- `events.js` - Event handling
- `state.js` - Reactive state management

**Key Features**:
- WebSocket connection (no polling)
- Event-driven updates
- Retro BBS aesthetic
- Real-time state sync
- Chat interface

## Data Flow

### Human sends message:

1. Human types in BBS frontend
2. Frontend sends via WebSocket → Gateway
3. Gateway routes to target agent's MCP server
4. Agent processes message (via LLM if needed)
5. Agent publishes state change event
6. Event bus broadcasts to all subscribers
7. Frontend receives event, updates UI instantly

### Agent-to-agent communication:

1. Agent A wants to communicate with Agent B
2. Agent A (MCP client) calls Agent B's tool via Gateway
3. Gateway routes tool call to Agent B's MCP server
4. Agent B processes tool call
5. Agent B publishes state change event
6. Event bus broadcasts to all subscribers
7. Both agents see updated state

### State synchronization:

1. Agent executes tool → State changes
2. Agent publishes event → Event bus
3. Event bus broadcasts → All subscribers
4. Frontend receives event → Updates UI
5. Other agents receive event → Update their state
6. Event stored in log → Event sourcing

## Technology Stack

### Backend (Python)
- **Language**: Python 3.14+
- **Async**: `asyncio` for concurrency
- **WebSocket**: `websockets` library
- **JSON-RPC**: Custom implementation
- **Event Bus**: Custom asyncio-based pub/sub
- **State Store**: SQLite with event sourcing (for now)

### Frontend (JavaScript)
- **Framework**: Vanilla JavaScript (keep BBS aesthetic)
- **WebSocket**: Native WebSocket API
- **State**: Reactive state from events
- **Styling**: CSS with BBS green-on-black theme

### Protocol
- **MCP**: Custom implementation based on JSON-RPC 2.0
- **WebSocket**: For real-time communication
- **Event Sourcing**: For state management

## Key Design Decisions

### 1. Custom MCP Implementation
**Why**: Full control, tailored for our needs, can evolve with official spec
**How**: JSON-RPC 2.0 base, tool discovery/execution, WebSocket transport

### 2. Event-Driven Architecture
**Why**: Real-time updates, decoupled components, scalable
**How**: Event bus with pub/sub, all state changes as events

### 3. Event Sourcing
**Why**: Audit trail, time travel, state reconstruction
**How**: Immutable event log, periodic snapshots

### 4. WebSocket Transport
**Why**: Real-time bidirectional, no polling, efficient
**How**: Native WebSocket, JSON-RPC 2.0 over WebSocket

### 5. Vanilla JavaScript Frontend
**Why**: Keep BBS aesthetic, no framework overhead, simpler
**How**: Native WebSocket API, reactive state from events

## Migration Strategy

Since this is a complete rewrite:
- **No migration**: New branch, clean slate
- **Old code reference**: Can look at old code for inspiration
- **Port tools**: Some old functionality can be ported as MCP tools
- **Data**: Can migrate data if needed (separate process)

## Implementation Phases

### Phase 1: MCP Foundation
- JSON-RPC 2.0 handler
- Tool system
- WebSocket transport
- Basic server/client

### Phase 2: Gateway
- Central gateway
- Tool registry
- Event bus
- WebSocket server

### Phase 3: First Agent
- Base agent class
- First MCP tools (memory)
- Agent registration
- State publishing

### Phase 4: Communication
- Agent-to-agent communication
- Human interface
- Frontend integration

### Phase 5: Full System
- Additional tools
- Advanced features
- Polish & optimization

## Success Criteria

1. **Real-time**: <100ms latency between state change and UI update
2. **No Polling**: All updates via events
3. **Scalability**: Support 100+ agents efficiently
4. **Reliability**: 99.9% uptime for WebSocket connections
5. **Developer Experience**: Easy to add new MCP tools

## Future Enhancements

- Official MCP spec compliance (when available)
- Additional transports (HTTP, stdio)
- Tool streaming (for long-running operations)
- Parallel tool calls
- Tool composition
- Advanced event replay
- Multi-node deployment

