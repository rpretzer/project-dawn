# Project Dawn V2: Decentralized Network

## Overview

Project Dawn V2 is a **decentralized, highly-encrypted network** built on the Model Context Protocol (MCP). Each node can host multiple autonomous agents that communicate via encrypted peer-to-peer connections.

## Key Features

- 🔐 **End-to-End Encryption**: All communications encrypted with AES-256-GCM
- 🌐 **Peer-to-Peer Network**: No single point of failure, mesh topology
- 🤖 **Multi-Agent Support**: Each node hosts multiple agents (owner-controlled)
- 💬 **Modern Chat Interface**: Browser-based chat application
- 🔧 **MCP Protocol**: Full support for Tools, Resources, and Prompts
- 🔄 **Eventually Consistent**: CRDT-based distributed state
- 🎯 **Hybrid Mode**: Supports centralized, decentralized, and hybrid modes

## Architecture

```
[Node A] <-> [Node B] <-> [Node C]
   |           |           |
[Agent 1]  [Agent 4]  [Agent 6]
[Agent 2]  [Agent 5]
[Agent 3]

Each node:
- Cryptographic identity (Ed25519)
- Multiple MCP servers (agents)
- Encrypted P2P connections
- Modern chat frontend
```

## Current Status

### ✅ Completed (Phases 1-7)
- JSON-RPC 2.0 protocol
- WebSocket transport
- MCP Server/Client implementation
- Tools, Resources, Prompts support
- Centralized Host
- First Agent with memory tools
- BBS-style frontend

### 🔨 In Progress (Phases 8-14)
- Node Identity & Cryptography
- Encrypted Transport Layer
- Peer Discovery System
- P2P Transport & Routing
- Distributed Agent Registry
- Hybrid Mode & Migration
- Modern Browser Chat Frontend
- Testing & Integration

## Documentation

### Implementation
- 📋 **[IMPLEMENTATION_PLAN_FINAL.md](docs/IMPLEMENTATION_PLAN_FINAL.md)** - Complete implementation plan (6 weeks)
- 📐 **[DECENTRALIZATION_PHASES.md](docs/DECENTRALIZATION_PHASES.md)** - Detailed phase breakdown
- 🏗️ **[DECENTRALIZED_NETWORK_DESIGN.md](docs/DECENTRALIZED_NETWORK_DESIGN.md)** - Architecture design

### Architecture
- 🤖 **[MULTI_AGENT_ARCHITECTURE.md](docs/MULTI_AGENT_ARCHITECTURE.md)** - Multi-agent per node design
- 💬 **[FRONTEND_MODERNIZATION.md](docs/FRONTEND_MODERNIZATION.md)** - Modern chat UI design
- 🔗 **[INTEGRATION_SUMMARY.md](docs/INTEGRATION_SUMMARY.md)** - Integration work completed

### Progress
- ✅ **[PHASE7_COMPLETE.md](docs/PHASE7_COMPLETE.md)** - Phase 7 completion summary
- 📊 **[PROGRESS.md](docs/PROGRESS.md)** - Overall progress tracking

## Quick Start

### Prerequisites
- Python 3.10+
- Modern browser (Chrome, Firefox, Safari, Edge)
- Network connectivity

### Installation
```bash
cd v2
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Run Current System (Centralized)
```bash
python server.py
```
- Frontend: http://localhost:8080
- WebSocket: ws://localhost:8000

### Run Tests
```bash
pytest tests/
```

## Implementation Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Cryptography | 2-3 days | 🔜 Next |
| Phase 2: Encrypted Transport | 2-3 days | ⏳ Pending |
| Phase 3: Peer Discovery | 3-4 days | ⏳ Pending |
| Phase 4: P2P Routing | 4-5 days | ⏳ Pending |
| Phase 5: Distributed Registry | 4-5 days | ⏳ Pending |
| Phase 7: Hybrid Mode | 2-3 days | ⏳ Pending |
| Phase 10: Modern Frontend | 5-7 days | ⏳ Pending |
| Phase 11: Testing | 3-4 days | ⏳ Pending |
| **Total** | **23-32 days** | **0% Complete** |

## Technology Stack

### Backend
- **Python 3.10+**: Core language
- **websockets**: WebSocket transport
- **cryptography**: Ed25519, X25519, AES-256-GCM
- **asyncio**: Asynchronous I/O

### Frontend
- **Vanilla JavaScript (ES6+)**: No framework dependency
- **Modern CSS**: Flexbox/Grid, responsive design
- **WebSocket API**: Real-time communication
- **IndexedDB**: Local message storage

### Protocols
- **MCP**: Model Context Protocol
- **JSON-RPC 2.0**: Message protocol
- **CRDT**: Conflict-free Replicated Data Types
- **Gossip**: State synchronization

## Key Concepts

### Node Identity
Each node has a cryptographic identity:
- **Public Key**: Node ID (Ed25519)
- **Private Key**: Proof of identity
- **Format**: `node_abc123`

### Agent Identity
Each agent has a unique identity:
- **Format**: `node_id:agent_id`
- **Example**: `node_abc123:agent_memory`
- **Routing**: Messages route to specific `node_id:agent_id`

### Multi-Agent Support
Each node can host multiple agents:
```python
node = P2PNode("node_abc123")
node.register_agent("memory", memory_agent)
node.register_agent("research", research_agent)
node.register_agent("codegen", codegen_agent)
```

### Message Flow
```
User -> Frontend -> Node A -> [P2P Network] -> Node B:Agent -> Process -> Response
```

## Security

### Encryption
- **Transport**: TLS/WSS for WebSocket connections
- **Application**: AES-256-GCM for message payloads
- **Key Exchange**: X25519 Diffie-Hellman
- **Signatures**: Ed25519 digital signatures

### Authentication
- **Node-to-Node**: Mutual authentication via signatures
- **Agent-to-Node**: Signed agent registration
- **Message Integrity**: All messages signed

### Privacy
- **End-to-End**: Only sender and recipient can decrypt
- **No Central Authority**: No single point of surveillance
- **Optional Anonymity**: Mix networks (Phase 8, optional)

## Contributing

This is a personal project, but design feedback and suggestions are welcome.

## License

[Specify your license here]

## Contact

[Specify contact information]

---

**Status**: Implementation Ready
**Version**: 2.0-decentralized
**Last Updated**: 2026-01-07



