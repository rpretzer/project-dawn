# Implementation Updates Based on Official MCP Spec

## Changes Based on Official Documentation

After reviewing the official MCP specification at [modelcontextprotocol.io](https://modelcontextprotocol.io), we need to update our implementation plan.

## Key Architecture Changes

### 1. Client-Host-Server Model (Not Just Client-Server)

**Original Plan**: Gateway between clients and servers
**Updated Plan**: **MCP Host** manages clients, enforces security, coordinates AI integration

**What Changed**:
- "Gateway" → "MCP Host" (per official spec)
- Host has additional responsibilities:
  - Manages multiple client instances
  - Controls client connections
  - Enforces security policies (OAuth 2.1)
  - Coordinates AI integration

### 2. Three Core Features: Tools, Resources, Prompts

**Original Plan**: Focus primarily on tools
**Updated Plan**: Support **Tools**, **Resources**, and **Prompts**

**What Changed**:
- **Resources**: Agents expose data sources (files, database schemas, etc.)
- **Prompts**: Agents provide reusable prompt templates and workflows
- **Tools**: Still primary feature, but now alongside resources and prompts

### 3. Stateful Sessions

**Original Plan**: Event-driven stateless communication
**Updated Plan**: **Stateful sessions** for client-server communication

**What Changed**:
- Clients establish stateful sessions with servers
- Sessions maintain state across requests
- Important for context continuity

### 4. OAuth 2.1 Authorization

**Original Plan**: Basic security
**Updated Plan**: **OAuth 2.1** based authorization framework

**What Changed**:
- Implement OAuth 2.1 authorization
- Host enforces security policies
- Secure client-server connections

### 5. JSON-RPC Batching

**Original Plan**: Single request/response
**Updated Plan**: Support **JSON-RPC batching**

**What Changed**:
- Support batch requests/responses
- More efficient for multiple operations
- Better performance

## Updated Implementation Plan

### Phase 1: MCP Foundation (Updated)

1. **JSON-RPC 2.0 Handler**
   - Message parsing/validation
   - Request/response handling
   - **JSON-RPC batching support** (NEW)
   - Error handling
   - ID management

2. **Tool System**
   - Tool definition (JSON Schema)
   - Tool registry
   - Tool discovery (`tools/list`)
   - Tool execution (`tools/call`)

3. **Resources System** (NEW)
   - Resource definition
   - Resource registry
   - Resource discovery (`resources/list`)
   - Resource access

4. **Prompts System** (NEW)
   - Prompt template definition
   - Prompt registry
   - Prompt discovery (`prompts/list`)
   - Prompt execution

5. **Transport Layer**
   - WebSocket (primary)
   - stdio (optional)
   - HTTP/SSE (optional)
   - Streamable HTTP (optional)

### Phase 2: MCP Host (Updated from Gateway)

1. **Host Implementation**
   - Client instance management
   - Client connection control
   - **OAuth 2.1 authorization** (NEW)
   - Security policy enforcement (NEW)
   - AI integration coordination (NEW)
   - Message routing
   - Tool/resource/prompt registry

2. **Event Bus**
   - Pub/sub system
   - Event storage
   - Event replay

3. **WebSocket Server**
   - Connection handling
   - Stateful session management (NEW)
   - Event broadcasting
   - Frontend integration

### Phase 3: First Agent (Updated)

1. **Base Agent Class**
   - Agent lifecycle
   - **MCP Server** implementation (exposes tools/resources/prompts)
   - **MCP Client** capability (can call other agents) (NEW)
   - **Stateful session** management (NEW)
   - State publishing

2. **Memory Tools/Resources** (Updated)
   - `memory_store` tool
   - `memory_recall` tool
   - `memory_search` tool
   - Memory resources (expose memory data) (NEW)

3. **Agent Implementation**
   - Basic agent with memory tools/resources
   - LLM integration
   - State publishing
   - Stateful session with host

### Phase 4: Communication (Updated)

1. **Agent-to-Agent Communication**
   - Agents as MCP clients
   - Tool call routing via host
   - Resource access
   - Prompt template usage

2. **Human Interface**
   - WebSocket frontend
   - MCP client connection to host (NEW)
   - Event subscription
   - Stateful session (NEW)

### Phase 5: Full System (Updated)

1. **Additional Tools/Resources/Prompts**
   - Creation tools
   - Evolution tools
   - Dream tools
   - Knowledge tools/resources
   - Standard prompt templates

2. **Advanced Features**
   - Tool composition
   - Resource composition
   - Prompt workflows
   - Streaming responses
   - Parallel tool calls
   - JSON-RPC batching optimization

3. **Security**
   - OAuth 2.1 implementation
   - Security policy enforcement
   - Secure transport (WSS)

## File Structure Updates

```
v2/
├── docs/
│   ├── MCP_OFFICIAL_SPEC.md         # Official spec review (NEW)
│   ├── IMPLEMENTATION_UPDATES.md    # This file (NEW)
│   └── ...
├── mcp/
│   ├── protocol.py                  # JSON-RPC 2.0 + batching
│   ├── transport.py                 # WebSocket/stdio/HTTP/SSE
│   ├── server.py                    # MCP server
│   ├── client.py                    # MCP client
│   ├── tools.py                     # Tool system
│   ├── resources.py                 # Resource system (NEW)
│   ├── prompts.py                   # Prompt system (NEW)
│   └── session.py                   # Stateful session (NEW)
├── host/                            # Renamed from gateway/
│   ├── __init__.py
│   ├── mcp_host.py                  # MCP Host (renamed)
│   ├── router.py                   # Message routing
│   ├── event_bus.py                 # Event pub/sub
│   ├── websocket_server.py          # WebSocket server
│   └── auth.py                      # OAuth 2.1 (NEW)
├── agents/
│   └── ...
└── frontend/
    └── ...
```

## Implementation Priority

1. **JSON-RPC 2.0 with batching** - Core protocol
2. **MCP Host** - Central coordination
3. **Tool system** - Primary feature
4. **Stateful sessions** - Important for context
5. **Resources system** - Secondary feature
6. **Prompts system** - Tertiary feature
7. **OAuth 2.1** - Security framework
8. **Advanced features** - Optimization

## Decision: Use Official SDK or Custom?

**Recommendation**: Start with **custom implementation** to:
- Understand the protocol deeply
- Tailor to our agentic architecture
- Maintain full control
- Learn and adapt

**Consider official SDK** later if:
- We need faster development
- We want guaranteed protocol compliance
- Official SDK has features we need

## Next Steps

1. Update architecture diagrams to show Host component
2. Implement JSON-RPC 2.0 with batching support
3. Build MCP Host (not just gateway)
4. Add Resources and Prompts support
5. Implement stateful sessions
6. Add OAuth 2.1 authorization
7. Build first agent with tools/resources/prompts

## References

- Official MCP Spec: https://modelcontextprotocol.io/specification/draft/index
- Architecture: https://modelcontextprotocol.io/specification/2024-11-05/architecture/index
- Changelog: https://modelcontextprotocol.io/specification/2025-03-26/changelog
- SDK: https://modelcontextprotocol.io/docs/sdk



