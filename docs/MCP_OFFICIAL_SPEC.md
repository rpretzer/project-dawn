# MCP Official Specification Review

Source: [https://modelcontextprotocol.io](https://modelcontextprotocol.io)

## Overview

MCP (Model Context Protocol) is an **open-source standard** for connecting AI applications to external systems. It allows AI applications like Claude or ChatGPT to connect to:
- **Data sources** (e.g., local files, databases)
- **Tools** (e.g., search engines, calculators)
- **Workflows** (e.g., specialized prompts)

Think of MCP like a "USB-C port for AI applications" - a standardized way to connect AI applications to external systems.

## Architecture: Client-Host-Server Model

MCP follows a **client-host-server** architecture (not just client-server):

### Components

1. **Host**
   - Manages multiple client instances
   - Controls client connections
   - Enforces security policies
   - Coordinates AI integration

2. **Clients**
   - Establish **stateful sessions** with servers
   - Handle requests, responses, and notifications
   - Bidirectional communication with servers
   - Created and managed by the host

3. **Servers**
   - Provide context, tools, and prompts to clients
   - Facilitate AI interaction with external systems
   - Expose capabilities via the protocol

### Architecture Benefits

This architecture ensures:
- **Clear security boundaries**
- **Effective coordination** between components
- **Scalability** (host can manage many clients)
- **Isolation** (each client has its own session)

## Protocol Details

### Communication Protocol

- **Base Protocol**: **JSON-RPC 2.0**
  - Structured and efficient message exchange
  - Stateful connections
  - Capability negotiation between clients and servers
  - Support for **JSON-RPC batching** (recent update)

### Key Features

1. **Resources**
   - Servers can expose data (e.g., files, database schemas)
   - Clients can access these resources
   - Examples: local files, database tables, API endpoints

2. **Tools**
   - Servers provide functions that clients can invoke
   - Enable models to interact with external systems
   - Defined with **JSON Schema** for input validation
   - **Enhanced tool annotations** for better describing behavior (recent update)

3. **Prompts**
   - Servers define reusable prompt templates and workflows
   - Clients can use these prompts for AI interactions
   - Enables standardized prompt patterns

## Transport Options

MCP supports multiple transport protocols:

1. **stdio** (Standard Input/Output)
   - For local MCP servers
   - Direct process communication

2. **WebSocket**
   - Real-time bidirectional communication
   - For networked servers

3. **HTTP/SSE** (Server-Sent Events)
   - Streaming responses
   - HTTP-based transport

4. **Streamable HTTP** (Recent update)
   - More flexible HTTP transport
   - Enhanced streaming capabilities

## Security

### Authorization Framework

- **OAuth 2.1** based authorization (recent addition)
- Comprehensive security framework
- Enforced by the host
- Secure client-server connections

## SDKs and Development

### Official SDKs

MCP offers official SDKs for building:
- **MCP Servers** - Expose data and tools
- **MCP Clients** - Connect to any MCP server
- **Local and remote transport** protocols
- **Protocol compliance** with type safety

SDKs are designed to:
- Follow idioms and best practices of respective languages
- Provide core functionality
- Ensure full protocol support
- Enable type-safe development

### Developer Tools

- **MCP Inspector** - Tool for inspecting MCP connections

## Specification Versions

The MCP specification is **continually evolving**:

- **Current version**: 2025-03-26 (as of recent changelog)
- **Previous version**: 2024-11-05
- Specification includes detailed architecture documentation

### Recent Updates (2025-03-26)

1. **Authorization Framework**
   - Comprehensive OAuth 2.1 based authorization

2. **Streamable HTTP Transport**
   - More flexible HTTP transport option

3. **JSON-RPC Batching**
   - Support for batch requests/responses

4. **Enhanced Tool Annotations**
   - Better describing tool behavior

## Use Cases

MCP enables various capabilities:

- **Agents** can access Google Calendar and Notion, acting as personalized AI assistants
- **Code generation** can use Figma designs to generate entire web apps
- **Enterprise chatbots** can connect to multiple databases for data analysis via chat
- **AI models** can create 3D designs in Blender and print them via 3D printer

## Benefits

Depending on your role in the ecosystem:

1. **Developers**
   - Reduces development time and complexity
   - Standardized protocol for AI integration
   - Reusable SDKs and tools

2. **AI Applications/Agents**
   - Access to ecosystem of data sources, tools, and apps
   - Enhanced capabilities
   - Better end-user experience

3. **End-Users**
   - More capable AI applications
   - Access to user's data
   - Ability to take actions on user's behalf

## Key Differences from Our Initial Assumptions

### What We Got Right ✅

1. JSON-RPC 2.0 base protocol ✓
2. Tool system (`tools/list`, `tools/call`) ✓
3. Multiple transport options ✓
4. Server-client model (with host added) ✓
5. Resources and tools concept ✓

### What We Missed or Need to Adjust

1. **Host Component** - We didn't account for the host that manages clients
2. **Resources** - We focused on tools but resources are a key feature
3. **Prompts** - We didn't consider prompt templates/workflows
4. **OAuth 2.1** - We need to implement authorization framework
5. **JSON-RPC Batching** - We should support batch operations
6. **Stateful Sessions** - Important for client-server communication

## Implementation Implications for Project Dawn V2

### Architecture Adjustments Needed

1. **Add Host Component**
   - Our "Gateway" should be the "Host"
   - Host manages all agent clients
   - Host enforces security policies
   - Host coordinates AI integration

2. **Agent Architecture**
   - Each agent is an **MCP Server** (exposes tools/resources/prompts)
   - Agents can also be **MCP Clients** (use other agents' tools)
   - Human interface connects as an **MCP Client** via the Host

3. **Resources Support**
   - Agents should expose resources (memory data, knowledge graphs)
   - Not just tools, but also resources for context

4. **Prompts Support**
   - Agents can provide prompt templates
   - Enables standardized workflows

5. **Security Framework**
   - Implement OAuth 2.1 authorization
   - Host enforces security boundaries
   - Secure client-server connections

### Updated Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Human Interface                    │
│              (MCP Client via Host)                  │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│                   MCP Host                          │
│  - Manages all clients                              │
│  - Enforces security policies                       │
│  - Coordinates AI integration                       │
│  - Routes messages between clients and servers      │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
┌───────┴────────┐          ┌────────┴────────┐
│ Agent 1       │          │ Agent 2         │
│ (MCP Server)  │◄────────►│ (MCP Server)    │
│               │  MCP     │                 │
│ Exposes:      │          │ Exposes:        │
│ - Tools       │          │ - Tools         │
│ - Resources   │          │ - Resources     │
│ - Prompts     │          │ - Prompts       │
│               │          │                 │
│ Also:         │          │ Also:           │
│ - MCP Client  │          │ - MCP Client    │
│   (can call   │          │   (can call     │
│    other      │          │    other        │
│    agents)    │          │    agents)      │
└───────────────┘          └─────────────────┘
```

## Next Steps for Implementation

1. **Review Official SDK**
   - Check if we should use official SDK or build custom
   - Official SDK ensures protocol compliance
   - Custom implementation gives more control

2. **Update Architecture Design**
   - Incorporate Host component properly
   - Add Resources and Prompts support
   - Design OAuth 2.1 authorization flow

3. **Protocol Implementation**
   - Implement JSON-RPC 2.0 properly
   - Add JSON-RPC batching support
   - Implement stateful sessions

4. **Security Implementation**
   - OAuth 2.1 authorization framework
   - Security boundaries enforcement
   - Secure transport (WSS for WebSocket)

## References

- Official MCP Website: https://modelcontextprotocol.io
- Getting Started: https://modelcontextprotocol.io/docs/getting-started/intro
- Architecture: https://modelcontextprotocol.io/specification/2024-11-05/architecture/index
- Specification: https://modelcontextprotocol.io/specification/draft/index
- SDK Documentation: https://modelcontextprotocol.io/docs/sdk
- Changelog: https://modelcontextprotocol.io/specification/2025-03-26/changelog



