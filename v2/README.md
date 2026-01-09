# Project Dawn V2 - Decentralized Multi-Agent Network

## Overview

Project Dawn V2 is a decentralized multi-agent network built on the Model Context Protocol (MCP). The system enables autonomous agents to communicate, share tools, and collaborate in a peer-to-peer network without central coordination.

**Current Status**: ✅ **Production Ready** - Core features complete and tested

## Architecture Philosophy

### Key Principles

1. **Fully Agentic**: Each agent (consciousness) is a fully autonomous MCP agent
2. **MCP Protocol**: Standardized agent-to-agent and agent-to-tool communication
3. **Real-time**: WebSocket-based, no polling
4. **Event-Driven**: All state changes propagate as events
5. **Event Sourcing**: Immutable event log for state reconstruction
6. **Clean Architecture**: No reuse of old code unless ported as MCP tools

### What We're Keeping (Philosophically)

- **BBS Aesthetic**: Retro terminal/IRC interface
- **Agent Autonomy**: Agents with their own goals and capabilities
- **Memory System**: Sophisticated memory management (as MCP tool)
- **Evolution System**: Evolutionary agent development (as MCP tool)
- **Dream System**: Dream integration for creativity (as MCP tool)

### What We're Rebuilding

- **Communication Layer**: From REST polling → MCP + WebSocket
- **State Management**: From REST endpoints → Event sourcing
- **Agent Architecture**: From tight coupling → Loosely coupled MCP agents
- **Tool System**: From custom methods → Standardized MCP tools
- **Frontend**: From polling → Event-driven WebSocket

## Architecture

### Current Architecture (P2P-based)

```
Frontend (WebSocket) → P2PNode → Agents (MCP Servers)
                     ↓
              Peer Discovery
              (mDNS, Gossip, DHT)
```

The system uses a **decentralized peer-to-peer architecture** where:
- Each node can host multiple agents
- Agents communicate via MCP protocol
- Peer discovery happens automatically (mDNS, Gossip, DHT)
- No central server required

## Project Structure

```
v2/
├── docs/                      # Comprehensive documentation
│   ├── PROJECT_REVIEW_ANALYSIS.md  # Project review & analysis
│   ├── TAURI_MIGRATION_PLAN.md     # Desktop app migration plan
│   └── [38+ documentation files]
├── mcp/                       # MCP protocol implementation
│   ├── protocol.py            # JSON-RPC 2.0 handling
│   ├── transport.py           # WebSocket transport
│   ├── encrypted_transport.py  # Encrypted WebSocket
│   ├── server.py              # MCP server
│   ├── client.py              # MCP client
│   ├── tools.py               # Tool registry
│   ├── resources.py           # Resource registry
│   └── prompts.py             # Prompt registry
├── p2p/                       # P2P networking
│   ├── p2p_node.py           # Main P2P node
│   ├── discovery.py          # Peer discovery (mDNS, Gossip, DHT)
│   ├── peer_registry.py      # Peer management
│   ├── dht.py                # Distributed hash table
│   ├── privacy.py            # Privacy features (onion routing)
│   └── libp2p_*.py           # Libp2p migration (optional, incomplete)
├── agents/                    # Agent implementations
│   ├── base_agent.py         # Base agent class
│   ├── first_agent.py        # FirstAgent (22+ tools)
│   ├── coordination_agent.py # CoordinationAgent
│   ├── code_agent.py         # CodeAgent
│   └── task_manager.py       # Task management
├── crypto/                    # Cryptography
│   ├── identity.py           # Node identity
│   ├── encryption.py         # Message encryption
│   ├── signing.py            # Message signing
│   └── key_exchange.py       # Key exchange
├── consensus/                 # Distributed consensus
│   ├── agent_registry.py     # Distributed agent registry
│   └── crdt.py               # CRDT implementation
├── integrity/                 # Integrity verification
│   └── verifier.py           # Runtime integrity checks
├── frontend/                  # Web interface
│   ├── index.html            # Main UI
│   ├── components/           # React-like components
│   └── services/             # WebSocket client
├── src-tauri/                 # Tauri desktop app (Phase 1)
│   ├── src/main.rs           # Rust application
│   └── tauri.conf.json       # Tauri configuration
├── scripts/                   # Build & release scripts
│   ├── generate_checksum.py  # Checksum generation
│   ├── sign_release.py       # GPG signing
│   └── build_python_sidecar.py # Python packaging
├── tests/                     # Test suite
│   └── [17 test files]
└── server_p2p.py             # Main entry point
```

## Features

### ✅ Implemented Features

1. **MCP Protocol** - Complete JSON-RPC 2.0 implementation
2. **P2P Networking** - Decentralized peer-to-peer communication
3. **Peer Discovery** - Automatic discovery via mDNS, Gossip, and DHT
4. **Multiple Agents** - FirstAgent, CoordinationAgent, CodeAgent
5. **Comprehensive Tools** - 22+ tools across 7 phases:
   - Memory management
   - Search & knowledge
   - Communication & notifications
   - Data & database operations
   - System & monitoring
6. **Resources & Prompts** - MCP resources and prompt templates
7. **Encryption** - End-to-end encrypted transport
8. **Privacy Features** - Optional onion routing, message padding
9. **Tauri Desktop App** - Desktop application framework (Phase 1)
10. **Integrity Verification** - GPG signing and checksum verification (Phase 2)

### 🚧 In Progress / Optional

1. **Libp2p Migration** (Phase 3 Option A) - Placeholder code, not yet implemented
2. **CI/CD Automation** - Scripts ready, pipeline not configured
3. **Tauri Icons** - Generation script ready, icons not created

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js (optional, for Tauri development)
- Rust (for Tauri builds)

### Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the P2P server
python server_p2p.py
```

The server will:
- Start on `ws://localhost:8000` (WebSocket)
- Serve frontend on `http://localhost:8080`
- Enable peer discovery on local network

### Development

```bash
# Run tests
python test_first_agent.py

# Run all tests
pytest tests/

# Start with Tauri (requires Rust)
cd src-tauri
cargo tauri dev
```

### Configuration

- **Transport Type**: Default is WebSocket. Libp2p is disabled by default.
  - Set `LIBP2P_ENABLED=true` to enable Libp2p (incomplete implementation)
- **Discovery**: Configured in `P2PNode` initialization
- **Encryption**: Enable/disable in `P2PNode` constructor

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **`PROJECT_REVIEW_ANALYSIS.md`** - Complete project review and analysis
- **`TAURI_MIGRATION_PLAN.md`** - Desktop app migration plan
- **`TOOLS_RESOURCES_PROMPTS_PLAN.md`** - Tools, resources, and prompts specification
- **Phase completion docs** - Detailed implementation notes for each phase

## MCP Protocol

Project Dawn V2 implements the Model Context Protocol (MCP) for agent communication:

- **JSON-RPC 2.0** - Standard protocol
- **Tools, Resources, Prompts** - Full MCP feature support
- **WebSocket Transport** - Real-time communication
- **Encrypted Transport** - Optional end-to-end encryption

See `docs/MCP_OFFICIAL_SPEC.md` for detailed specification review.

## Status

✅ **Production Ready** - Core features complete and tested

The system is fully functional with:
- ✅ Complete MCP implementation
- ✅ P2P networking with automatic discovery
- ✅ Multiple agent types with comprehensive tools
- ✅ Desktop application framework (Tauri)
- ✅ Integrity verification system

**Optional/Incomplete Features**:
- ⚠️ Libp2p migration (placeholder code, disabled by default)
- ⚠️ CI/CD automation (scripts ready, pipeline not configured)

See `docs/PROJECT_REVIEW_ANALYSIS.md` for detailed status and next steps.

