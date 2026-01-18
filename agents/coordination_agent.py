"""
Coordination Agent

Special agent that provides coordination and collaboration tools for multi-agent systems.
Implements Phase 1 tools, resources, and prompts from the development plan.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from .base_agent import BaseAgent
from .task_manager import TaskManager, TaskStatus
from mcp.resources import MCPResource
from mcp.prompts import MCPPrompt, MCPPromptArgument

logger = logging.getLogger(__name__)


class CoordinationAgent(BaseAgent):
    """
    Coordination Agent
    
    Provides tools for agent coordination, task management, and communication.
    Has access to the P2P node for network-wide operations.
    """
    
    def __init__(self, agent_id: str, p2p_node, name: Optional[str] = None):
        """
        Initialize coordination agent
        
        Args:
            agent_id: Agent ID
            p2p_node: P2P node instance (for network access)
            name: Agent name
        """
        super().__init__(agent_id, name or "CoordinationAgent")
        self.p2p_node = p2p_node
        
        # Initialize task manager
        self.task_manager = TaskManager()
        
        # Chat rooms: room_id -> {participants: [], messages: [], created_at: float}
        self.chat_rooms: Dict[str, Dict[str, Any]] = {}
        
        # Register tools
        self._register_tools()
        
        # Register resources
        self._register_resources()
        
        # Register prompts
        self._register_prompts()
    
    def _register_tools(self):
        """Register coordination tools"""
        
        # Tool 1: agent_list
        self.register_tool(
            tool_name="agent_list",
            description="List all available agents in the network",
            handler=self._agent_list,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Optional filters for agent search",
                        "properties": {
                            "node_id": {
                                "type": "string",
                                "description": "Filter by node ID"
                            },
                            "agent_id": {
                                "type": "string",
                                "description": "Filter by agent ID"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["available", "unavailable"],
                                "description": "Filter by availability status"
                            },
                            "capabilities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by capabilities (tools/resources/prompts)"
                            }
                        }
                    }
                }
            }
        )
        
        # Tool 2: agent_call
        self.register_tool(
            tool_name="agent_call",
            description="Call another agent's tool or method",
            handler=self._agent_call,
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target agent in format 'node_id:agent_id' or 'agent_id' (local)"
                    },
                    "method": {
                        "type": "string",
                        "description": "Tool name or method to call"
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameters for the tool/method"
                    }
                },
                "required": ["target", "method"]
            }
        )
        
        # Tool 3: agent_broadcast
        self.register_tool(
            tool_name="agent_broadcast",
            description="Broadcast message to all agents in a chat room",
            handler=self._agent_broadcast,
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to broadcast"
                    },
                    "room_id": {
                        "type": "string",
                        "description": "Chat room ID (default: 'main')",
                        "default": "main"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high"],
                        "description": "Message priority",
                        "default": "normal"
                    }
                },
                "required": ["message"]
            }
        )
        
        # Tool 4: task_create
        self.register_tool(
            tool_name="task_create",
            description="Create a task for agents to work on",
            handler=self._task_create,
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Task description"
                    },
                    "assignee": {
                        "type": "string",
                        "description": "Optional agent ID to assign task to"
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Task priority (1-10, 1 is highest)",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5
                    },
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of task IDs this task depends on"
                    }
                },
                "required": ["title", "description"]
            }
        )
        
        # Tool 5: task_list
        self.register_tool(
            tool_name="task_list",
            description="List all tasks with optional filters",
            handler=self._task_list,
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "assigned", "in_progress", "completed"],
                        "description": "Filter by task status"
                    },
                    "assignee": {
                        "type": "string",
                        "description": "Filter by assignee agent ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tasks to return",
                        "default": 100
                    }
                }
            }
        )
        
        # Register Phase 2: Network Awareness tools
        self._register_network_tools()
        
        logger.info(f"CoordinationAgent '{self.name}' registered {len(self.get_tools())} tools")
    
    def _register_resources(self):
        """Register coordination resources"""
        
        # Resource 1: agent://registry
        self.server.register_resource(
            resource=MCPResource(
                uri="agent://registry",
                name="Agent Registry",
                description="Network-wide agent registry with all agents and their capabilities",
                mimeType="application/json",
            ),
            handler=self._agent_registry_resource,
        )
        
        # Resource 2: room://active
        self.server.register_resource(
            resource=MCPResource(
                uri="room://active",
                name="Active Chat Rooms",
                description="List of active chat rooms and their participants",
                mimeType="application/json",
            ),
            handler=self._room_active_resource,
        )
        
        # Resource 3: task://queue
        self.server.register_resource(
            resource=MCPResource(
                uri="task://queue",
                name="Task Queue",
                description="Current task queue with status and assignments",
                mimeType="application/json",
            ),
            handler=self._task_queue_resource,
        )
        
        # Resource 4: agent://api-reference
        self.server.register_resource(
            resource=MCPResource(
                uri="agent://api-reference",
                name="API Reference",
                description="Comprehensive reference of all tools and capabilities in the system",
                mimeType="text/markdown",
            ),
            handler=self._api_reference_resource,
        )
        
        # Register Phase 2: Network Awareness resources
        self._register_network_resources()
        
        logger.info(f"CoordinationAgent '{self.name}' registered {len(self.server.get_resources())} resources")
    
    def _register_prompts(self):
        """Register coordination prompts"""
        
        # Prompt 1: agent_coordination
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="agent_coordination",
                description="Coordinate multiple agents to accomplish a task",
                arguments=[
                    MCPPromptArgument(
                        name="task",
                        description="Task description",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="available_agents",
                        description="List of available agent IDs",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="context",
                        description="Optional context information",
                        required=False,
                    ),
                ],
                template="Coordinate agents {{available_agents}} to accomplish: {{task}}. Context: {{context}}",
            ),
            handler=self._agent_coordination_prompt,
        )
        
        # Prompt 2: task_decomposition
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="task_decomposition",
                description="Decompose a complex task into subtasks",
                arguments=[
                    MCPPromptArgument(
                        name="task",
                        description="Task to decompose",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="complexity",
                        description="Task complexity level",
                        required=False,
                    ),
                ],
                template="Break down this task into subtasks: {{task}}. Complexity: {{complexity}}",
            ),
            handler=self._task_decomposition_prompt,
        )
        
        # Prompt 3: agent_selection
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="agent_selection",
                description="Select the best agent(s) for a task",
                arguments=[
                    MCPPromptArgument(
                        name="task",
                        description="Task description",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="agent_list",
                        description="List of available agent IDs",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="criteria",
                        description="Selection criteria",
                        required=False,
                    ),
                ],
                template="Select the best agent(s) from {{agent_list}} for: {{task}}. Criteria: {{criteria}}",
            ),
            handler=self._agent_selection_prompt,
        )
        
        # Register Phase 2: Network Awareness prompts
        self._register_network_prompts()
        
        logger.info(f"CoordinationAgent '{self.name}' registered {len(self.server.get_prompts())} prompts")
    
    # Tool Handlers
    
    async def _agent_list(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        List all available agents in the network
        
        Args:
            filters: Optional filters (node_id, agent_id, status, capabilities)
            
        Returns:
            List of agents with metadata
        """
        filters = filters or {}
        
        # Get all agents from registry
        agents = self.p2p_node.agent_registry.list_agents(
            node_id=filters.get("node_id"),
            available_only=(filters.get("status") == "available"),
        )
        
        # Apply agent_id filter if specified
        if "agent_id" in filters:
            agents = [a for a in agents if filters["agent_id"] in a.agent_id or filters["agent_id"] == a.local_agent_id]
        
        # Apply capability filter if specified
        if "capabilities" in filters:
            capabilities = filters["capabilities"]
            filtered_agents = []
            for agent in agents:
                # Check if agent has any of the requested capabilities
                agent_capabilities = []
                if agent.tools:
                    agent_capabilities.extend([t.get("name") for t in agent.tools])
                if agent.resources:
                    agent_capabilities.extend([r.get("uri") for r in agent.resources])
                if agent.prompts:
                    agent_capabilities.extend([p.get("name") for p in agent.prompts])
                
                # Check if any requested capability matches
                if any(cap in agent_capabilities for cap in capabilities):
                    filtered_agents.append(agent)
            agents = filtered_agents
        
        # Convert to dict format
        agent_list = [agent.to_dict() for agent in agents]
        
        logger.info(f"Listed {len(agent_list)} agents (filters: {filters})")
        
        return {
            "success": True,
            "agents": agent_list,
            "count": len(agent_list),
        }
    
    async def _agent_call(
        self,
        target: str,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call another agent's tool or method
        
        Args:
            target: Target agent (node_id:agent_id or agent_id for local)
            method: Tool name or method
            params: Parameters for the tool
            
        Returns:
            Result from remote agent
        """
        try:
            # Call agent via P2P node
            response = await self.p2p_node.call_agent(
                target=target,
                method=method,
                params=params or {},
            )
            
            if "error" in response:
                logger.warning(f"Agent call failed: {response['error']}")
                return {
                    "success": False,
                    "error": response["error"].get("message", "Unknown error"),
                    "response": response,
                }
            
            logger.info(f"Successfully called {target}/{method}")
            return {
                "success": True,
                "result": response.get("result"),
                "response": response,
            }
        
        except Exception as e:
            logger.error(f"Error calling agent {target}/{method}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _agent_broadcast(
        self,
        message: str,
        room_id: str = "main",
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Broadcast message to all agents in chat room
        
        Args:
            message: Message to broadcast
            room_id: Chat room ID
            priority: Message priority
            
        Returns:
            Confirmation and response count
        """
        # Ensure room exists
        if room_id not in self.chat_rooms:
            self.chat_rooms[room_id] = {
                "id": room_id,
                "name": f"Room {room_id}",
                "participants": [],
                "messages": [],
                    "created_at": time.time(),
            }
        
        room = self.chat_rooms[room_id]
        participants = room["participants"]
        
        if not participants:
            return {
                "success": False,
                "error": f"No agents in room {room_id}",
                "responses": 0,
            }
        
        # Broadcast to each participant
        responses = []
        for participant_id in participants:
            try:
                # Send via chat/message method
                response = await self.p2p_node.call_agent(
                    target=participant_id,
                    method="chat/message",
                    params={
                        "message": message,
                        "room_id": room_id,
                        "priority": priority,
                    },
                )
                responses.append({
                    "agent_id": participant_id,
                    "response": response.get("result"),
                    "success": "error" not in response,
                })
            except Exception as e:
                logger.error(f"Error broadcasting to {participant_id}: {e}")
                responses.append({
                    "agent_id": participant_id,
                    "error": str(e),
                    "success": False,
                })
        
        # Record message in room
        room["messages"].append({
            "message": message,
            "sender": "broadcast",
            "priority": priority,
            "timestamp": time.time(),
            "responses": len([r for r in responses if r.get("success")]),
        })
        
        success_count = len([r for r in responses if r.get("success")])
        
        logger.info(f"Broadcast to {len(participants)} agents in room {room_id}, {success_count} responses")
        
        return {
            "success": True,
            "message": "Broadcast sent",
            "room_id": room_id,
            "participants": len(participants),
            "responses": success_count,
            "response_details": responses,
        }
    
    async def _task_create(
        self,
        title: str,
        description: str,
        assignee: Optional[str] = None,
        priority: int = 5,
        dependencies: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a task for agents to work on
        
        Args:
            title: Task title
            description: Task description
            assignee: Optional agent ID to assign
            priority: Task priority (1-10)
            dependencies: List of task IDs this depends on
            
        Returns:
            Task ID and confirmation
        """
        task = self.task_manager.create_task(
            title=title,
            description=description,
            assignee=assignee,
            priority=priority,
            dependencies=dependencies or [],
        )
        
        logger.info(f"Created task: {task.task_id} - {title}")
        
        return {
            "success": True,
            "task_id": task.task_id,
            "task": task.to_dict(),
            "message": f"Task '{title}' created successfully",
        }
    
    async def _task_list(
        self,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        List all tasks with optional filters
        
        Args:
            status: Filter by status (open, assigned, in_progress, completed)
            assignee: Filter by assignee
            limit: Maximum number of tasks
            
        Returns:
            List of tasks
        """
        # Convert string status to enum
        status_enum = None
        if status:
            try:
                status_enum = TaskStatus(status)
            except ValueError:
                return {
                    "success": False,
                    "error": f"Invalid status: {status}",
                }
        
        tasks = self.task_manager.list_tasks(
            status=status_enum,
            assignee=assignee,
            limit=limit,
        )
        
        task_list = [task.to_dict() for task in tasks]
        
        logger.info(f"Listed {len(task_list)} tasks (status: {status}, assignee: {assignee})")
        
        return {
            "success": True,
            "tasks": task_list,
            "count": len(task_list),
        }
    
    # Resource Handlers
    
    async def _agent_registry_resource(self) -> str:
        """Resource handler for agent registry"""
        agents = self.p2p_node.agent_registry.list_agents()
        agent_data = [agent.to_dict() for agent in agents]
        
        return json.dumps({
            "agents": agent_data,
            "total": len(agent_data),
            "timestamp": time.time(),
        }, indent=2)
    
    async def _room_active_resource(self) -> str:
        """Resource handler for active chat rooms"""
        rooms_data = []
        for room_id, room in self.chat_rooms.items():
            rooms_data.append({
                "id": room["id"],
                "name": room.get("name", room_id),
                "participants": room.get("participants", []),
                "participant_count": len(room.get("participants", [])),
                "message_count": len(room.get("messages", [])),
                "created_at": room.get("created_at"),
            })
        
        return json.dumps({
            "rooms": rooms_data,
            "total": len(rooms_data),
            "timestamp": time.time(),
        }, indent=2)
    
    async def _task_queue_resource(self) -> str:
        """Resource handler for task queue"""
        # Get tasks by status
        open_tasks = self.task_manager.list_tasks(status=TaskStatus.OPEN)
        assigned_tasks = self.task_manager.list_tasks(status=TaskStatus.ASSIGNED)
        in_progress_tasks = self.task_manager.list_tasks(status=TaskStatus.IN_PROGRESS)
        completed_tasks = self.task_manager.list_tasks(status=TaskStatus.COMPLETED)
        
        stats = self.task_manager.get_stats()
        
        return json.dumps({
            "open": [t.to_dict() for t in open_tasks],
            "assigned": [t.to_dict() for t in assigned_tasks],
            "in_progress": [t.to_dict() for t in in_progress_tasks],
            "completed": [t.to_dict() for t in completed_tasks[-10:]],  # Last 10 completed
            "stats": stats,
            "timestamp": time.time(),
        }, indent=2)
    
    async def _api_reference_resource(self) -> str:
        """Resource handler for API reference"""
        ref_path = Path(__file__).parent.parent / "API_REFERENCE.md"
        if ref_path.exists():
            return ref_path.read_text(encoding="utf-8")
        return "API Reference not found. Run scripts/generate_api_docs.py to generate it."
    
    # Prompt Handlers
    
    async def _agent_coordination_prompt(
        self,
        task: str,
        available_agents: str,
        context: Optional[str] = None
    ) -> str:
        """Prompt handler for agent coordination"""
        # Parse available agents (could be comma-separated string or JSON)
        try:
            if available_agents.startswith("["):
                agent_list = json.loads(available_agents)
            else:
                agent_list = [a.strip() for a in available_agents.split(",")]
        except Exception as e:
            logger.debug(f"Could not parse available_agents as JSON, treating as single item. Error: {e}")
            agent_list = [available_agents]
        
        # Get agent details
        agents_info = []
        for agent_id in agent_list:
            agent_info = self.p2p_node.agent_registry.get_agent(agent_id)
            if agent_info:
                agents_info.append({
                    "id": agent_id,
                    "name": agent_info.name,
                    "tools": [t.get("name") for t in agent_info.tools[:5]],  # First 5 tools
                })
        
        prompt = f"Task: {task}\n\n"
        prompt += f"Available Agents ({len(agents_info)}):\n"
        for agent in agents_info:
            prompt += f"- {agent['name']} ({agent['id']}): {', '.join(agent['tools'][:3])}\n"
        
        if context:
            prompt += f"\nContext: {context}\n"
        
        prompt += "\nPlease coordinate these agents to accomplish the task. "
        prompt += "Consider each agent's capabilities and suggest how to divide the work."
        
        return prompt
    
    async def _task_decomposition_prompt(
        self,
        task: str,
        complexity: Optional[str] = None
    ) -> str:
        """Prompt handler for task decomposition"""
        complexity = complexity or "medium"
        
        prompt = f"Task to decompose: {task}\n"
        prompt += f"Complexity: {complexity}\n\n"
        prompt += "Please break down this task into smaller, manageable subtasks. "
        prompt += "Consider dependencies, priorities, and logical sequence. "
        prompt += "Provide a clear structure for each subtask including:\n"
        prompt += "- Title\n- Description\n- Dependencies (if any)\n- Suggested priority"
        
        return prompt
    
    async def _agent_selection_prompt(
        self,
        task: str,
        agent_list: str,
        criteria: Optional[str] = None
    ) -> str:
        """Prompt handler for agent selection"""
        # Parse agent list
        try:
            if agent_list.startswith("["):
                agents = json.loads(agent_list)
            else:
                agents = [a.strip() for a in agent_list.split(",")]
        except Exception as e:
            logger.debug(f"Could not parse agent_list as JSON, treating as single item. Error: {e}")
            agents = [agent_list]
        
        # Get agent capabilities
        agents_info = []
        for agent_id in agents:
            agent_info = self.p2p_node.agent_registry.get_agent(agent_id)
            if agent_info:
                agents_info.append({
                    "id": agent_id,
                    "name": agent_info.name,
                    "tools": [t.get("name") for t in agent_info.tools],
                    "description": agent_info.description,
                })
        
        prompt = f"Task: {task}\n\n"
        prompt += f"Candidate Agents ({len(agents_info)}):\n"
        for agent in agents_info:
            prompt += f"- {agent['name']} ({agent['id']})\n"
            prompt += f"  Description: {agent.get('description', 'N/A')}\n"
            prompt += f"  Tools: {', '.join(agent['tools'][:5])}\n\n"
        
        if criteria:
            prompt += f"Selection Criteria: {criteria}\n\n"
        
        prompt += "Please select the best agent(s) for this task and explain your reasoning. "
        prompt += "Consider the agent's capabilities, tools, and how well they match the task requirements."
        
        return prompt
    
    def ensure_room(self, room_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Ensure a chat room exists"""
        if room_id not in self.chat_rooms:
            self.chat_rooms[room_id] = {
                "id": room_id,
                "name": name or f"Room {room_id}",
                "participants": [],
                "messages": [],
                    "created_at": time.time(),
            }
        return self.chat_rooms[room_id]
    
    def add_participant(self, room_id: str, agent_id: str) -> bool:
        """Add participant to chat room"""
        room = self.ensure_room(room_id)
        if agent_id not in room["participants"]:
            room["participants"].append(agent_id)
            logger.info(f"Added {agent_id} to room {room_id}")
            return True
        return False
    
    # Phase 2: Network Awareness Tools
    
    def _register_network_tools(self):
        """Register Phase 2: Network Awareness tools"""
        
        # Tool 1: network_peers
        self.register_tool(
            tool_name="network_peers",
            description="List all connected peers/nodes in the network",
            handler=self._network_peers,
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["connected", "disconnected"],
                        "description": "Filter by connection status"
                    },
                    "node_id": {
                        "type": "string",
                        "description": "Filter by specific node ID"
                    }
                }
            }
        )
        
        # Tool 2: network_info
        self.register_tool(
            tool_name="network_info",
            description="Get network statistics and health",
            handler=self._network_info,
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
        
        # Tool 3: node_info
        self.register_tool(
            tool_name="node_info",
            description="Get information about a specific node",
            handler=self._node_info,
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Node ID to get information about"
                    }
                },
                "required": ["node_id"]
            }
        )
        
        # Tool 4: agent_discover
        self.register_tool(
            tool_name="agent_discover",
            description="Discover agents by capability or name",
            handler=self._agent_discover,
            inputSchema={
                "type": "object",
                "properties": {
                    "capability": {
                        "type": "string",
                        "description": "Capability to search for (tool/resource/prompt name)"
                    },
                    "name_pattern": {
                        "type": "string",
                        "description": "Name pattern to match (supports wildcards)"
                    },
                    "node_id": {
                        "type": "string",
                        "description": "Filter by node ID"
                    }
                }
            }
        )
    
    def _register_network_resources(self):
        """Register Phase 2: Network Awareness resources"""
        
        # Resource 1: network://topology
        self.server.register_resource(
            resource=MCPResource(
                uri="network://topology",
                name="Network Topology",
                description="Network topology graph showing nodes and connections",
                mimeType="application/json",
            ),
            handler=self._network_topology_resource,
        )
        
        # Resource 2: network://stats
        self.server.register_resource(
            resource=MCPResource(
                uri="network://stats",
                name="Network Statistics",
                description="Network-wide statistics and health metrics",
                mimeType="application/json",
            ),
            handler=self._network_stats_resource,
        )
    
    def _register_network_prompts(self):
        """Register Phase 2: Network Awareness prompts"""
        
        # Prompt 1: network_analysis
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="network_analysis",
                description="Analyze network state and suggest optimizations",
                arguments=[
                    MCPPromptArgument(
                        name="network_data",
                        description="Network data to analyze (JSON object)",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="focus",
                        description="Focus area for analysis (optional)",
                        required=False,
                    ),
                ],
                template="Analyze this network data: {{network_data}}. Focus: {{focus}}",
            ),
            handler=self._network_analysis_prompt,
        )
        
        # Prompt 2: peer_recommendation
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="peer_recommendation",
                description="Recommend peers for collaboration based on task",
                arguments=[
                    MCPPromptArgument(
                        name="task",
                        description="Task description",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="current_peers",
                        description="List of current peer node IDs",
                        required=True,
                    ),
                ],
                template="Recommend peers for: {{task}}. Current peers: {{current_peers}}",
            ),
            handler=self._peer_recommendation_prompt,
        )
    
    # Phase 2 Tool Handlers
    
    async def _network_peers(
        self,
        status: Optional[str] = None,
        node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List all connected peers/nodes
        
        Args:
            status: Filter by connection status
            node_id: Filter by specific node ID
            
        Returns:
            List of peers with connection status
        """
        peers = self.p2p_node.peer_registry.list_peers()
        
        # Apply filters
        if status:
            if status == "connected":
                peers = [p for p in peers if p.connected]
            elif status == "disconnected":
                peers = [p for p in peers if not p.connected]
        
        if node_id:
            peers = [p for p in peers if p.node_id == node_id or node_id in p.node_id]
        
        peer_list = [peer.to_dict() for peer in peers]
        
        logger.info(f"Listed {len(peer_list)} peers (status: {status}, node_id: {node_id})")
        
        return {
            "success": True,
            "peers": peer_list,
            "count": len(peer_list),
            "total_connected": len([p for p in peers if p.connected]),
            "total_disconnected": len([p for p in peers if not p.connected]),
        }
    
    async def _network_info(self) -> Dict[str, Any]:
        """
        Get network statistics and health
        
        Returns:
            Network stats (node count, latency, uptime, etc.)
        """
        peers = self.p2p_node.peer_registry.list_peers()
        connected_peers = [p for p in peers if p.connected]
        
        # Calculate network health metrics
        total_agents = len(self.p2p_node.agent_registry.list_agents())
        local_agents = len(self.p2p_node.list_agents())
        
        # Calculate average health score
        if peers:
            avg_health = sum(p.health_score for p in peers) / len(peers)
        else:
            avg_health = 1.0
        
        # Calculate connection success rate
        total_attempts = sum(p.connection_attempts for p in peers)
        total_success = sum(p.successful_connections for p in peers)
        success_rate = total_success / total_attempts if total_attempts > 0 else 1.0
        
        # Get node uptime (approximate, based on when node was started)
        node_start_time = getattr(self.p2p_node, 'start_time', time.time())
        uptime = time.time() - node_start_time
        
        stats = {
            "node_count": len(peers),
            "connected_nodes": len(connected_peers),
            "disconnected_nodes": len(peers) - len(connected_peers),
            "total_agents": total_agents,
            "local_agents": local_agents,
            "remote_agents": total_agents - local_agents,
            "average_health_score": avg_health,
            "connection_success_rate": success_rate,
            "total_connection_attempts": total_attempts,
            "successful_connections": total_success,
            "node_uptime_seconds": uptime,
            "node_id": self.p2p_node.node_id,
            "node_address": self.p2p_node.address,
        }
        
        logger.info(f"Network info: {len(connected_peers)}/{len(peers)} nodes connected, {total_agents} total agents")
        
        return {
            "success": True,
            "network_stats": stats,
        }
    
    async def _node_info(self, node_id: str) -> Dict[str, Any]:
        """
        Get information about a specific node
        
        Args:
            node_id: Node ID to get information about
            
        Returns:
            Node metadata (agents, capabilities, status)
        """
        # Check if it's this node
        if node_id == self.p2p_node.node_id:
            return {
                "success": True,
                "node_id": self.p2p_node.node_id,
                "address": self.p2p_node.address,
                "is_local": True,
                "agents": list(self.p2p_node.agents.keys()),
                "agent_count": len(self.p2p_node.agents),
                "peer_count": self.p2p_node.peer_registry.get_peer_count(),
                "status": "online",
            }
        
        # Check peer registry
        peer = self.p2p_node.peer_registry.get_peer(node_id)
        if not peer:
            return {
                "success": False,
                "error": f"Node {node_id[:16]}... not found",
            }
        
        # Get agents on this node from registry
        agents_on_node = self.p2p_node.agent_registry.list_agents(node_id=node_id)
        
        node_info = {
            "node_id": peer.node_id,
            "address": peer.address,
            "is_local": False,
            "connected": peer.connected,
            "last_seen": peer.last_seen,
            "first_seen": peer.first_seen,
            "health_score": peer.health_score,
            "connection_attempts": peer.connection_attempts,
            "successful_connections": peer.successful_connections,
            "failed_connections": peer.failed_connections,
            "agents": [agent.local_agent_id for agent in agents_on_node],
            "agent_count": len(agents_on_node),
            "agent_details": [agent.to_dict() for agent in agents_on_node],
            "tools_count": sum(len(agent.tools) for agent in agents_on_node),
            "resources_count": sum(len(agent.resources) for agent in agents_on_node),
            "prompts_count": sum(len(agent.prompts) for agent in agents_on_node),
            "status": "online" if peer.connected else "offline",
        }
        
        logger.info(f"Retrieved info for node {node_id[:16]}...: {node_info['agent_count']} agents")
        
        return {
            "success": True,
            "node": node_info,
        }
    
    async def _agent_discover(
        self,
        capability: Optional[str] = None,
        name_pattern: Optional[str] = None,
        node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Discover agents by capability or name
        
        Args:
            capability: Capability to search for
            name_pattern: Name pattern to match
            node_id: Filter by node ID
            
        Returns:
            Matching agents
        """
        # Start with all agents
        agents = self.p2p_node.agent_registry.list_agents(node_id=node_id)
        
        matching_agents = []
        
        for agent in agents:
            match = True
            
            # Filter by capability
            if capability:
                # Check tools, resources, prompts
                agent_capabilities = []
                if agent.tools:
                    agent_capabilities.extend([t.get("name") for t in agent.tools])
                if agent.resources:
                    agent_capabilities.extend([r.get("uri") for r in agent.resources])
                if agent.prompts:
                    agent_capabilities.extend([p.get("name") for p in agent.prompts])
                
                # Check if capability matches
                capability_lower = capability.lower()
                if not any(capability_lower in cap.lower() for cap in agent_capabilities):
                    match = False
            
            # Filter by name pattern
            if match and name_pattern:
                # Simple pattern matching (supports * wildcard)
                pattern = name_pattern.lower()
                agent_name = agent.name.lower()
                agent_id = agent.agent_id.lower()
                
                if "*" in pattern:
                    # Wildcard matching
                    pattern_parts = pattern.split("*")
                    if not all(part in agent_name or part in agent_id for part in pattern_parts if part):
                        match = False
                else:
                    # Simple substring match
                    if pattern not in agent_name and pattern not in agent_id:
                        match = False
            
            if match:
                matching_agents.append(agent)
        
        agent_list = [agent.to_dict() for agent in matching_agents]
        
        logger.info(f"Discovered {len(agent_list)} agents (capability: {capability}, name: {name_pattern})")
        
        return {
            "success": True,
            "agents": agent_list,
            "count": len(agent_list),
            "filters": {
                "capability": capability,
                "name_pattern": name_pattern,
                "node_id": node_id,
            }
        }
    
    # Phase 2 Resource Handlers
    
    async def _network_topology_resource(self) -> str:
        """Resource handler for network topology"""
        peers = self.p2p_node.peer_registry.list_peers()
        
        # Build topology graph
        nodes = []
        edges = []
        
        # Add this node
        nodes.append({
            "id": self.p2p_node.node_id,
            "label": "Local Node",
            "type": "local",
            "agents": list(self.p2p_node.agents.keys()),
            "agent_count": len(self.p2p_node.agents),
        })
        
        # Add peers
        for peer in peers:
            # Get agents on this peer
            agents_on_peer = self.p2p_node.agent_registry.list_agents(node_id=peer.node_id)
            
            nodes.append({
                "id": peer.node_id,
                "label": f"Node {peer.node_id[:16]}...",
                "type": "peer",
                "address": peer.address,
                "connected": peer.connected,
                "health_score": peer.health_score,
                "agents": [agent.local_agent_id for agent in agents_on_peer],
                "agent_count": len(agents_on_peer),
            })
            
            # Add edge if connected
            if peer.connected:
                edges.append({
                    "source": self.p2p_node.node_id,
                    "target": peer.node_id,
                    "type": "connected",
                    "health": peer.health_score,
                })
        
        topology = {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "connected_edges": len(edges),
            "timestamp": time.time(),
        }
        
        return json.dumps(topology, indent=2)
    
    async def _network_stats_resource(self) -> str:
        """Resource handler for network statistics"""
        peers = self.p2p_node.peer_registry.list_peers()
        connected_peers = [p for p in peers if p.connected]
        
        # Aggregate statistics
        total_agents = len(self.p2p_node.agent_registry.list_agents())
        
        # Health metrics
        health_scores = [p.health_score for p in peers]
        avg_health = sum(health_scores) / len(health_scores) if health_scores else 1.0
        min_health = min(health_scores) if health_scores else 1.0
        max_health = max(health_scores) if health_scores else 1.0
        
        # Connection metrics
        total_attempts = sum(p.connection_attempts for p in peers)
        total_success = sum(p.successful_connections for p in peers)
        success_rate = total_success / total_attempts if total_attempts > 0 else 1.0
        
        stats = {
            "network": {
                "total_nodes": len(peers) + 1,  # +1 for local node
                "connected_nodes": len(connected_peers),
                "disconnected_nodes": len(peers) - len(connected_peers),
                "total_agents": total_agents,
                "average_agents_per_node": total_agents / (len(peers) + 1) if peers else total_agents,
            },
            "health": {
                "average_health_score": avg_health,
                "min_health_score": min_health,
                "max_health_score": max_health,
                "healthy_nodes": len([p for p in peers if p.health_score > 0.7]),
                "unhealthy_nodes": len([p for p in peers if p.health_score <= 0.7]),
            },
            "connections": {
                "total_attempts": total_attempts,
                "successful": total_success,
                "failed": total_attempts - total_success,
                "success_rate": success_rate,
                "active_connections": len(connected_peers),
            },
            "timestamp": time.time(),
        }
        
        return json.dumps(stats, indent=2)
    
    # Phase 2 Prompt Handlers
    
    async def _network_analysis_prompt(
        self,
        network_data: str,
        focus: Optional[str] = None
    ) -> str:
        """Prompt handler for network analysis"""
        try:
            # Parse network data (could be JSON string or dict)
            if isinstance(network_data, str):
                try:
                    data = json.loads(network_data)
                except json.JSONDecodeError:
                    data = {"raw": network_data}
            else:
                data = network_data
        except Exception as e:
            logger.debug(f"Could not process network_data, treating as raw string. Error: {e}")
            data = {"raw": str(network_data)}
        
        # Get actual network info if not provided
        if "network_stats" not in data:
            network_info_result = await self._network_info()
            if network_info_result.get("success"):
                data["network_stats"] = network_info_result["network_stats"]
        
        prompt = "Network Analysis\n\n"
        prompt += f"Network Data:\n{json.dumps(data, indent=2)}\n\n"
        
        if focus:
            prompt += f"Focus Area: {focus}\n\n"
        
        prompt += "Please analyze this network data and provide:\n"
        prompt += "1. Current network health assessment\n"
        prompt += "2. Identified issues or bottlenecks\n"
        prompt += "3. Optimization recommendations\n"
        prompt += "4. Potential improvements\n"
        
        if focus:
            prompt += f"\nPay special attention to: {focus}\n"
        
        return prompt
    
    async def _peer_recommendation_prompt(
        self,
        task: str,
        current_peers: str
    ) -> str:
        """Prompt handler for peer recommendation"""
        # Parse current peers (could be JSON array or comma-separated)
        try:
            if current_peers.startswith("["):
                peer_list = json.loads(current_peers)
            else:
                peer_list = [p.strip() for p in current_peers.split(",")]
        except Exception as e:
            logger.debug(f"Could not parse current_peers as JSON, treating as single item. Error: {e}")
            peer_list = [current_peers]
        
        # Get all available peers
        all_peers = self.p2p_node.peer_registry.list_peers()
        available_peers = [p for p in all_peers if p.node_id not in peer_list and p.connected]
        
        # Get peer capabilities
        peer_info = []
        for peer in available_peers[:10]:  # Limit to top 10
            agents_on_peer = self.p2p_node.agent_registry.list_agents(node_id=peer.node_id)
            peer_capabilities = set()
            for agent in agents_on_peer:
                if agent.tools:
                    peer_capabilities.update([t.get("name") for t in agent.tools[:5]])
            
            peer_info.append({
                "node_id": peer.node_id,
                "address": peer.address,
                "health_score": peer.health_score,
                "agent_count": len(agents_on_peer),
                "capabilities": list(peer_capabilities)[:5],
            })
        
        prompt = f"Task: {task}\n\n"
        prompt += f"Current Peers ({len(peer_list)}):\n"
        for peer_id in peer_list:
            prompt += f"- {peer_id[:16]}...\n"
        
        prompt += f"\nAvailable Peers ({len(available_peers)}):\n"
        for peer in peer_info:
            prompt += f"- {peer['node_id'][:16]}... (health: {peer['health_score']:.2f}, agents: {peer['agent_count']}, capabilities: {', '.join(peer['capabilities'][:3])})\n"
        
        prompt += "\nPlease recommend the best peer(s) to connect to for this task. "
        prompt += "Consider peer health, available agents, capabilities, and how well they match the task requirements."
        
        return prompt
    
    def remove_participant(self, room_id: str, agent_id: str) -> bool:
        """Remove participant from chat room"""
        if room_id in self.chat_rooms:
            if agent_id in self.chat_rooms[room_id]["participants"]:
                self.chat_rooms[room_id]["participants"].remove(agent_id)
                logger.info(f"Removed {agent_id} from room {room_id}")
                return True
        return False

