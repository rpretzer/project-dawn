# Multi-Agent Per Node Architecture

## Overview

Each node in the decentralized network can host **multiple agents**, as determined by the node owner. This document outlines the architecture and implementation for supporting multiple agents per node.

## Architecture

### Current State

**Centralized (Current):**
```
[Host]
  ├── [Agent 1 Server]
  ├── [Agent 2 Server]
  └── [Agent 3 Server]
```

**Decentralized (Target):**
```
[Node A]
  ├── [Agent 1 Server]
  ├── [Agent 2 Server]
  └── [Agent 3 Server]
  
[Node B]
  ├── [Agent 4 Server]
  └── [Agent 5 Server]
  
[Node C]
  └── [Agent 6 Server]
```

### Key Principles

1. **Node = Host**: Each node can host multiple MCP servers (agents)
2. **Dynamic Registration**: Agents can be registered/unregistered at runtime
3. **Agent Identity**: Each agent has unique identity: `node_id:agent_id`
4. **Routing**: Messages route to `node_id:agent_id` (not just `node_id`)
5. **Discovery**: Network discovers all agents across all nodes

## Implementation

### Node Structure

Each node maintains:
- **Node Identity**: Cryptographic keypair (node_id)
- **Agent Registry**: Map of `agent_id -> MCPServer`
- **Peer Connections**: Connections to other nodes
- **Agent Announcements**: Broadcasts all agents on connection

### Agent Identity

**Format:** `{node_id}:{agent_id}`

**Examples:**
- `node_abc123:agent_memory` - Memory agent on node abc123
- `node_xyz789:agent_codegen` - Code generation agent on node xyz789
- `node_abc123:agent_research` - Research agent on same node (multi-agent)

### Routing

**Current (Single Agent per Node):**
```
Message -> Route to node -> Process on agent
```

**New (Multiple Agents per Node):**
```
Message -> Route to node:agent -> Process on specific agent
```

**Routing Logic:**
1. Parse `node_id:agent_id` from message
2. Find peer node with `node_id`
3. Send message to that node
4. Node routes to specific `agent_id` server
5. Agent processes message

### Discovery

**Agent Registry Structure:**
```python
{
    "node_abc123": {
        "node_id": "node_abc123",
        "address": "ws://node_abc123:8000",
        "agents": [
            {"agent_id": "agent_memory", "name": "Memory Agent", "tools": [...]},
            {"agent_id": "agent_research", "name": "Research Agent", "tools": [...]},
        ]
    },
    "node_xyz789": {
        "node_id": "node_xyz789",
        "address": "ws://node_xyz789:8000",
        "agents": [
            {"agent_id": "agent_codegen", "name": "Code Gen Agent", "tools": [...]},
        ]
    }
}
```

**Discovery Flow:**
1. Node connects to network
2. Node announces all its agents (`agents/list`)
3. Other nodes update their registry
4. Gossip protocol syncs registry across network
5. Eventually consistent: all nodes know all agents

### Node API

**Agent Management:**
```python
class P2PNode:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.agents: Dict[str, MCPServer] = {}
        self.peers: Dict[str, PeerConnection] = {}
    
    def register_agent(self, agent_id: str, agent: MCPServer) -> None:
        """Register an agent with this node"""
        self.agents[agent_id] = agent
        # Announce to network
        self._announce_agent(agent_id, agent)
    
    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from this node"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            # Announce removal to network
            self._announce_agent_removal(agent_id)
    
    def get_agent(self, agent_id: str) -> Optional[MCPServer]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents on this node"""
        return [
            {
                "agent_id": agent_id,
                "node_id": self.node_id,
                "name": agent.name,
                "tools": agent.get_tools(),
                "resources": agent.get_resources(),
                "prompts": agent.get_prompts(),
            }
            for agent_id, agent in self.agents.items()
        ]
```

### Message Format

**Extended MCP Message:**
```json
{
  "jsonrpc": "2.0",
  "id": "request_id",
  "method": "tools/call",
  "params": {
    "name": "tool_name",
    "arguments": {...},
    "target": "node_abc123:agent_memory"  // NEW: Target node:agent
  }
}
```

**Routing Headers:**
```json
{
  "encrypted": true,
  "sender": "node_xyz789",
  "recipient": "node_abc123:agent_memory",  // Target node:agent
  "ciphertext": "<encrypted_mcp_message>",
  "signature": "<signature>"
}
```

### Agent Registry (CRDT)

**Distributed Registry Structure:**
```python
# Per-node structure
{
    "node_abc123": {
        "node_id": "node_abc123",
        "address": "ws://...",
        "agents": CRDT_ORSet([  # CRDT for agent list
            "agent_memory",
            "agent_research",
        ]),
        "last_seen": timestamp,
    },
    # ... other nodes
}
```

**CRDT Operations:**
- **Add Agent**: Add to node's agent set
- **Remove Agent**: Remove from node's agent set
- **Merge**: Conflict-free merge of agent lists
- **Node Removal**: Remove entire node entry on timeout

### Discovery Protocol

**Agent Announcement:**
```python
# On node connection
{
    "type": "agent_announcement",
    "node_id": "node_abc123",
    "agents": [
        {
            "agent_id": "agent_memory",
            "name": "Memory Agent",
            "tools": [...],
            "resources": [...],
            "prompts": [...],
        },
        {
            "agent_id": "agent_research",
            "name": "Research Agent",
            "tools": [...],
            "resources": [...],
            "prompts": [...],
        }
    ]
}
```

**Gossip Protocol:**
1. Node announces its agents on connection
2. Peers update their registry
3. Peers gossip to their neighbors
4. Eventually all nodes know all agents

## Code Changes

### Phase 4: P2P Node Implementation

**`v2/p2p/node.py`:**
```python
class P2PNode:
    def __init__(self, node_id: str, identity: NodeIdentity):
        self.node_id = node_id
        self.identity = identity
        self.agents: Dict[str, MCPServer] = {}  # Multiple agents
        self.peer_registry: PeerRegistry = PeerRegistry()
        self.agent_registry: DistributedAgentRegistry = DistributedAgentRegistry()
        # ...
    
    def register_agent(self, agent_id: str, agent: MCPServer) -> None:
        """Register an agent with this node"""
        self.agents[agent_id] = agent
        # Announce to network
        await self._announce_agent(agent_id, agent)
    
    async def _announce_agent(self, agent_id: str, agent: MCPServer) -> None:
        """Announce agent to network"""
        announcement = {
            "type": "agent_announcement",
            "node_id": self.node_id,
            "agent_id": agent_id,
            "agent_info": {
                "name": agent.name,
                "tools": agent.get_tools(),
                "resources": agent.get_resources(),
                "prompts": agent.get_prompts(),
            }
        }
        # Broadcast to all peers
        await self.broadcast_to_peers(announcement)
    
    async def route_message(self, message: Dict[str, Any]) -> Optional[str]:
        """Route message to appropriate agent"""
        target = message.get("target")  # "node_id:agent_id"
        if not target:
            return None
        
        node_id, agent_id = target.split(":", 1)
        
        # Route to local agent?
        if node_id == self.node_id:
            agent = self.agents.get(agent_id)
            if agent:
                return await agent.handle_message(message)
            return None
        
        # Route to peer node
        peer = self.peer_registry.get_peer(node_id)
        if peer:
            return await peer.send_message(message)
        
        return None
```

### Phase 5: Distributed Agent Registry

**`v2/consensus/agent_registry.py`:**
```python
class DistributedAgentRegistry:
    """CRDT-based distributed agent registry"""
    
    def __init__(self):
        self.nodes: Dict[str, NodeAgentSet] = {}  # node_id -> agent set
    
    def add_agent(self, node_id: str, agent_id: str, agent_info: Dict) -> None:
        """Add agent to registry"""
        if node_id not in self.nodes:
            self.nodes[node_id] = NodeAgentSet(node_id)
        self.nodes[node_id].add_agent(agent_id, agent_info)
    
    def remove_agent(self, node_id: str, agent_id: str) -> None:
        """Remove agent from registry"""
        if node_id in self.nodes:
            self.nodes[node_id].remove_agent(agent_id)
    
    def find_agent(self, agent_id: str) -> Optional[Tuple[str, str]]:
        """Find which node hosts an agent: returns (node_id, agent_id)"""
        for node_id, node_set in self.nodes.items():
            if node_set.has_agent(agent_id):
                return (node_id, agent_id)
        return None
    
    def list_all_agents(self) -> List[Dict[str, Any]]:
        """List all agents across all nodes"""
        all_agents = []
        for node_id, node_set in self.nodes.items():
            for agent_id, agent_info in node_set.agents.items():
                all_agents.append({
                    "node_id": node_id,
                    "agent_id": agent_id,
                    **agent_info
                })
        return all_agents
```

## Usage Examples

### Registering Multiple Agents on a Node

```python
# Node setup
node = P2PNode("node_abc123", identity)

# Create multiple agents
memory_agent = FirstAgent("memory", "Memory Agent")
research_agent = ResearchAgent("research", "Research Agent")
codegen_agent = CodeGenAgent("codegen", "Code Generator")

# Register all agents on same node
await node.register_agent("memory", memory_agent.server)
await node.register_agent("research", research_agent.server)
await node.register_agent("codegen", codegen_agent.server)

# All agents accessible via node
# Routes: node_abc123:memory, node_abc123:research, node_abc123:codegen
```

### Calling Agent on Specific Node

```python
# From another node
target = "node_abc123:memory"
message = {
    "method": "tools/call",
    "params": {
        "name": "memory_store",
        "arguments": {"content": "Hello"},
        "target": target  # Specify target node:agent
    }
}

response = await node.send_to_peer(target, message)
```

### Discovering All Agents

```python
# Get all agents across network
all_agents = node.agent_registry.list_all_agents()

for agent in all_agents:
    print(f"{agent['node_id']}:{agent['agent_id']} - {agent['name']}")
    print(f"  Tools: {len(agent['tools'])}")
    print(f"  Resources: {len(agent['resources'])}")
    print(f"  Prompts: {len(agent['prompts'])}")
```

## Benefits

1. **Resource Efficiency**: Multiple agents share node resources
2. **Logical Grouping**: Related agents can be co-located
3. **Cost Optimization**: Node owner controls agent density
4. **Flexibility**: Add/remove agents dynamically
5. **Scalability**: Network scales by nodes, not agents

## Migration Path

### Current → Multi-Agent

**Step 1: Update Node to Support Multiple Agents**
- Change `agents` from single to dict
- Update routing to support `node_id:agent_id`

**Step 2: Update Agent Registry**
- Track agents per node
- Update discovery protocol

**Step 3: Update Frontend**
- Show agents grouped by node
- Allow selection of specific node:agent

**Backward Compatibility:**
- Single agent per node still works (default agent_id = "default")
- Routing defaults to first agent if agent_id not specified

## Testing

### Unit Tests
- Register/unregister multiple agents
- Route messages to specific agents
- Handle agent removal

### Integration Tests
- Multiple agents on same node
- Cross-node agent communication
- Agent discovery across network
- Agent registry synchronization

### Performance Tests
- Routing performance with many agents
- Discovery performance with many nodes/agents
- Memory usage with multiple agents per node

## Summary

**Key Changes:**
- Node hosts multiple agents (not just one)
- Agent identity: `node_id:agent_id`
- Routing: `node_id:agent_id` format
- Registry: Track agents per node
- Discovery: Announce all agents per node

**Benefits:**
- Flexible: Node owner controls agent count
- Efficient: Share node resources
- Scalable: Network scales by nodes
- Dynamic: Add/remove agents at runtime



