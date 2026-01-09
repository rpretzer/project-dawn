# MCP Implementation Plan for Project Dawn V2

## MCP Protocol Understanding

Based on available information and standard protocol patterns, MCP (Model Context Protocol) appears to be built on JSON-RPC 2.0 with the following characteristics:

### Core Protocol Elements

1. **JSON-RPC 2.0 Base**
   - Request/Response pattern
   - Method names for operations
   - Structured error handling
   - ID correlation for async operations

2. **Tool System**
   - `tools/list` - Discover available tools
   - `tools/call` - Execute a tool with parameters
   - Tool schema definition (JSON Schema)
   - Tool result handling

3. **Transport Layer**
   - stdio (standard input/output) for local
   - WebSocket for real-time
   - HTTP for REST-like access
   - Server-Sent Events (SSE) for streaming

4. **Context & Resources**
   - Context sharing between calls
   - Resource discovery and access
   - Stateful tool interactions

## Our Custom MCP Implementation

Since we're building from scratch, we'll implement MCP following the standard pattern but tailored for our fully agentic architecture.

### Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│              MCP Client (Agent)                      │
│  - Maintains tool registry                          │
│  - Executes tool calls via JSON-RPC                 │
│  - Manages LLM context                              │
│  - Publishes state events                           │
└───────────────┬──────────────────────────────────────┘
                │ JSON-RPC 2.0
                │ (WebSocket)
┌───────────────┴──────────────────────────────────────┐
│              MCP Gateway                             │
│  - Routes tool calls to appropriate servers          │
│  - Maintains agent registry                         │
│  - Handles tool discovery                           │
│  - Manages event bus                                │
└───────────────┬──────────────────────────────────────┘
                │
    ┌───────────┴───────────┐
    │                       │
┌───┴─────────┐      ┌──────┴────────┐
│ MCP Server  │      │ MCP Server    │
│ (Memory)    │      │ (Agent)       │
│             │      │               │
│ Tools:      │      │ Tools:        │
│ - store     │      │ - chat        │
│ - recall    │      │ - spawn       │
│ - search    │      │ - state       │
└─────────────┘      └───────────────┘
```

### Implementation Details

#### 1. JSON-RPC 2.0 Message Format

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "memory_store",
    "arguments": {
      "content": "...",
      "context": {...}
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [...],
    "isError": false
  }
}
```

**Error:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": {...}
  }
}
```

#### 2. Tool Definition Schema

```python
@dataclass
class MCPTool:
    name: str
    description: str
    inputSchema: Dict[str, Any]  # JSON Schema
    handler: Callable  # Async function that executes the tool
```

#### 3. Transport Layer

**WebSocket Transport:**
- Real-time bidirectional communication
- Supports streaming results
- Connection management
- Heartbeat/ping for connection health

**HTTP Transport (optional):**
- REST-like tool access
- For external tool integration
- Stateless tool calls

#### 4. Tool Registry

```python
class ToolRegistry:
    def register(self, server_id: str, tool: MCPTool)
    def discover(self, query: str) -> List[MCPTool]
    def get_tool(self, name: str) -> Optional[MCPTool]
    def list_tools(self, server_id: str) -> List[MCPTool]
```

#### 5. Event System

Every tool execution generates events:
- `tool.called` - Tool invocation started
- `tool.completed` - Tool finished successfully
- `tool.failed` - Tool execution failed
- `state.changed` - Agent state updated

Events flow through event bus to all subscribers (agents + frontend).

## File Structure

```
v2/
├── mcp/
│   ├── __init__.py
│   ├── protocol.py          # JSON-RPC 2.0 message handling
│   ├── transport.py         # WebSocket/HTTP transport
│   ├── server.py            # MCP server implementation
│   ├── client.py            # MCP client for tool calls
│   ├── tools.py             # Tool definition and registry
│   └── schema.py            # JSON Schema validation
├── agents/
│   ├── __init__.py
│   ├── base_agent.py        # Base agent class
│   ├── agent.py             # Main agent implementation
│   └── registry.py          # Agent discovery
├── gateway/
│   ├── __init__.py
│   ├── mcp_gateway.py       # Central MCP gateway
│   ├── router.py            # Message routing
│   ├── event_bus.py         # Event pub/sub
│   └── websocket_server.py  # WebSocket server
├── frontend/
│   ├── index.html           # BBS interface
│   ├── websocket.js         # WebSocket client
│   ├── events.js            # Event handling
│   └── state.js             # Reactive state
├── core/
│   └── (New core systems, not reusing old code)
└── docs/
    ├── MCP_RESEARCH.md
    ├── MCP_IMPLEMENTATION_PLAN.md
    └── ARCHITECTURE.md
```

## Implementation Phases

### Phase 1: MCP Core Library (Week 1)

1. **JSON-RPC 2.0 Handler**
   - Message parsing and validation
   - Request/response handling
   - Error handling
   - ID management

2. **Tool System**
   - Tool definition class
   - Tool registry
   - Tool discovery
   - Tool execution

3. **Transport Layer**
   - WebSocket transport
   - Message serialization
   - Connection management

4. **Basic Tests**
   - Unit tests for each component
   - Integration tests

### Phase 2: Gateway (Week 1-2)

1. **MCP Gateway**
   - Tool call routing
   - Agent registry
   - Message forwarding

2. **Event Bus**
   - Pub/sub system
   - Event storage
   - Event replay

3. **WebSocket Server**
   - Connection handling
   - Event broadcasting
   - Frontend integration

### Phase 3: First Agent & Tools (Week 2)

1. **Base Agent Class**
   - Agent lifecycle
   - Tool registration
   - Event publishing
   - State management

2. **Memory Tools (MCP)**
   - `memory_store` tool
   - `memory_recall` tool
   - `memory_search` tool

3. **Agent Implementation**
   - Basic agent with memory tools
   - LLM integration
   - State publishing

### Phase 4: Communication Tools (Week 2-3)

1. **Agent Communication**
   - `agent_send_message` tool
   - `agent_discover` tool
   - `agent_broadcast` tool

2. **Human Interface**
   - WebSocket frontend
   - Message routing
   - Event subscription

### Phase 5: Full System (Week 3-4)

1. **Additional Tools**
   - Creation tools
   - Evolution tools
   - Dream tools
   - Knowledge tools

2. **Advanced Features**
   - Tool composition
   - Streaming responses
   - Parallel tool calls
   - Error recovery

3. **Frontend Polish**
   - BBS aesthetic
   - Real-time updates
   - Better UX

## Technical Decisions

### 1. Language: Python 3.14+
- Async/await for concurrency
- Type hints for safety
- Existing ecosystem

### 2. WebSocket Library: `websockets`
- Async-native
- Well-maintained
- Good documentation

### 3. JSON-RPC: Custom Implementation
- Tailored to our needs
- Full control
- Protocol compliance

### 4. State Management: Event Sourcing
- Immutable event log
- Time travel debugging
- Audit trail

### 5. Frontend: Vanilla JavaScript
- Keep BBS aesthetic
- No framework overhead
- Direct WebSocket control

## Next Steps

1. **Find Official Spec**: Continue searching for Anthropic's MCP spec
2. **Prototype**: Build minimal MCP server/client
3. **Validate**: Test against official MCP tools if available
4. **Build**: Start Phase 1 implementation



