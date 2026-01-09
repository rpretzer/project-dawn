"""
First Agent Implementation

Simple agent with basic memory tools for testing.
"""

import asyncio
import logging
import json
import time
import uuid
import platform
import os
from typing import Any, Dict, List, Optional
from collections import defaultdict
from .base_agent import BaseAgent
from mcp.resources import MCPResource
from mcp.prompts import MCPPrompt, MCPPromptArgument

logger = logging.getLogger(__name__)

# Try to import psutil for system monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class FirstAgent(BaseAgent):
    """
    First Agent
    
    Simple agent with memory tools for testing the MCP system.
    """
    
    def __init__(self, agent_id: str, name: Optional[str] = None):
        """Initialize first agent"""
        super().__init__(agent_id, name or "FirstAgent")
        
        # Simple in-memory storage for testing
        self.memory: Dict[str, Any] = {}
        
        # Phase 4: Search & Knowledge storage
        # Search index: content_id -> indexed content
        self.search_index: Dict[str, Dict[str, Any]] = {}
        # Knowledge base: topic -> list of knowledge entries
        self.knowledge_base: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # Search history: list of recent queries
        self.search_history: List[Dict[str, Any]] = []
        # Semantic similarity index (simplified - using keyword matching)
        self.semantic_index: Dict[str, List[str]] = defaultdict(list)  # keyword -> content_ids
        
        # Phase 5: Communication & Notifications storage
        # Notifications: notification_id -> notification data
        self.notifications: Dict[str, Dict[str, Any]] = {}
        # Notification queue: list of pending notification IDs
        self.notification_queue: List[str] = []
        # Channels: channel_id -> channel data
        self.channels: Dict[str, Dict[str, Any]] = {}
        # Channel messages: channel_id -> list of messages
        self.channel_messages: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Phase 6: Data & Database Operations storage
        # Database schemas: database_name -> schema info
        self.db_schemas: Dict[str, Dict[str, Any]] = {}
        # Sample data sets: dataset_name -> sample data
        self.sample_data: Dict[str, Any] = {}
        # In-memory databases for testing: database_name -> tables
        self.in_memory_dbs: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        
        # Phase 7: System & Monitoring storage
        # System logs: list of log entries
        self.system_logs: List[Dict[str, Any]] = []
        # System metrics history: timestamp -> metrics
        self.metrics_history: List[Dict[str, Any]] = []
        
        # Register tools
        self._register_tools()
        
        # Register resources
        self._register_resources()
        
        # Register prompts
        self._register_prompts()
    
    def _register_tools(self):
        """Register agent tools"""
        
        # memory_store tool
        self.register_tool(
            tool_name="memory_store",
            description="Store a memory with content and optional context",
            handler=self._memory_store,
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Memory content to store"
                    },
                    "context": {
                        "type": "object",
                        "description": "Optional context information",
                        "properties": {}
                    }
                },
                "required": ["content"]
            }
        )
        
        # memory_recall tool
        self.register_tool(
            tool_name="memory_recall",
            description="Recall a memory by ID or search by content",
            handler=self._memory_recall,
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "Memory ID to recall"
                    },
                    "search": {
                        "type": "string",
                        "description": "Search term to find memories"
                    }
                }
            }
        )
        
        # memory_list tool
        self.register_tool(
            tool_name="memory_list",
            description="List all stored memories",
            handler=self._memory_list,
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of memories to return",
                        "default": 100
                    }
                }
            }
        )
        
        # memory_delete tool
        self.register_tool(
            tool_name="memory_delete",
            description="Delete a memory by ID",
            handler=self._memory_delete,
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "Memory ID to delete"
                    }
                },
                "required": ["memory_id"]
            }
        )
        
        # Phase 4: Search & Knowledge tools
        
        # search_text tool
        self.register_tool(
            tool_name="search_text",
            description="Full-text search across files/content",
            handler=self._search_text,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "scope": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of content IDs to search within"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        )
        
        # search_semantic tool
        self.register_tool(
            tool_name="search_semantic",
            description="Semantic search (vector similarity) to find conceptually similar content",
            handler=self._search_semantic,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for semantic similarity"
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Minimum similarity threshold (0.0-1.0)",
                        "default": 0.5
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        )
        
        # index_content tool
        self.register_tool(
            tool_name="index_content",
            description="Index content for search",
            handler=self._index_content,
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to index"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata for the content"
                    },
                    "type": {
                        "type": "string",
                        "description": "Content type (e.g., 'document', 'code', 'note')"
                    }
                },
                "required": ["content"]
            }
        )
        
        # knowledge_query tool
        self.register_tool(
            tool_name="knowledge_query",
            description="Query indexed knowledge base",
            handler=self._knowledge_query,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query to search knowledge base"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional filters (topic, type, etc.)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        )
        
        # web_search tool
        self.register_tool(
            tool_name="web_search",
            description="Search the web (if enabled)",
            handler=self._web_search,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Web search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of sources to search"
                    }
                },
                "required": ["query"]
            }
        )
        
        # Phase 5: Communication & Notifications tools
        
        # notification_send tool
        self.register_tool(
            tool_name="notification_send",
            description="Send notification to user/agent",
            handler=self._notification_send,
            inputSchema={
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "Recipient ID (user or agent)"
                    },
                    "message": {
                        "type": "string",
                        "description": "Notification message"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "urgent"],
                        "description": "Notification priority",
                        "default": "normal"
                    },
                    "type": {
                        "type": "string",
                        "description": "Notification type (e.g., 'task_complete', 'alert', 'info')"
                    }
                },
                "required": ["recipient", "message"]
            }
        )
        
        # notification_list tool
        self.register_tool(
            tool_name="notification_list",
            description="List notifications",
            handler=self._notification_list,
            inputSchema={
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "Filter by recipient ID"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["read", "unread"],
                        "description": "Filter by read status"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of notifications to return",
                        "default": 50
                    }
                }
            }
        )
        
        # channel_create tool
        self.register_tool(
            tool_name="channel_create",
            description="Create communication channel",
            handler=self._channel_create,
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Channel name"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["public", "private"],
                        "description": "Channel type",
                        "default": "public"
                    },
                    "participants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Initial participants (user/agent IDs)"
                    }
                },
                "required": ["name"]
            }
        )
        
        # channel_message tool
        self.register_tool(
            tool_name="channel_message",
            description="Send message to channel",
            handler=self._channel_message,
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID"
                    },
                    "message": {
                        "type": "string",
                        "description": "Message content"
                    },
                    "attachments": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Optional message attachments"
                    }
                },
                "required": ["channel_id", "message"]
            }
        )
        
        # Phase 6: Data & Database Operations tools
        
        # db_query tool
        self.register_tool(
            tool_name="db_query",
            description="Execute database query",
            handler=self._db_query,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Database query (SQL or query string)"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name (optional, uses default if not specified)"
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters"
                    }
                },
                "required": ["query"]
            }
        )
        
        # db_schema tool
        self.register_tool(
            tool_name="db_schema",
            description="Get database schema",
            handler=self._db_schema,
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Database name (optional)"
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name (optional, returns all tables if not specified)"
                    }
                }
            }
        )
        
        # data_transform tool
        self.register_tool(
            tool_name="data_transform",
            description="Transform data format",
            handler=self._data_transform,
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {
                        "description": "Data to transform"
                    },
                    "from_format": {
                        "type": "string",
                        "description": "Source format (json, csv, xml, yaml, etc.)"
                    },
                    "to_format": {
                        "type": "string",
                        "description": "Target format (json, csv, xml, yaml, etc.)"
                    }
                },
                "required": ["data", "from_format", "to_format"]
            }
        )
        
        # data_analyze tool
        self.register_tool(
            tool_name="data_analyze",
            description="Analyze data (statistics, patterns)",
            handler=self._data_analyze,
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {
                        "description": "Data to analyze"
                    },
                    "analysis_type": {
                        "type": "string",
                        "description": "Type of analysis (statistics, patterns, summary, etc.)",
                        "default": "statistics"
                    },
                    "options": {
                        "type": "object",
                        "description": "Analysis options"
                    }
                },
                "required": ["data"]
            }
        )
        
        # data_export tool
        self.register_tool(
            tool_name="data_export",
            description="Export data to file",
            handler=self._data_export,
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {
                        "description": "Data to export"
                    },
                    "format": {
                        "type": "string",
                        "description": "Export format (json, csv, xml, yaml, etc.)"
                    },
                    "path": {
                        "type": "string",
                        "description": "File path to export to"
                    }
                },
                "required": ["data", "format", "path"]
            }
        )
        
        # Phase 7: System & Monitoring tools
        
        # system_status tool
        self.register_tool(
            tool_name="system_status",
            description="Get system status (CPU, memory, disk)",
            handler=self._system_status,
            inputSchema={
                "type": "object",
                "properties": {
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific metrics to retrieve (cpu, memory, disk, network, etc.)"
                    }
                }
            }
        )
        
        # log_query tool
        self.register_tool(
            tool_name="log_query",
            description="Query system logs",
            handler=self._log_query,
            inputSchema={
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        "description": "Filter by log level"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern in log messages"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of log entries to return",
                        "default": 100
                    }
                }
            }
        )
        
        # process_list tool
        self.register_tool(
            tool_name="process_list",
            description="List running processes",
            handler=self._process_list,
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Filter processes by name or pattern"
                    }
                }
            }
        )
        
        # health_check tool
        self.register_tool(
            tool_name="health_check",
            description="Perform health check",
            handler=self._health_check,
            inputSchema={
                "type": "object",
                "properties": {
                    "components": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific components to check (optional, checks all if not specified)"
                    }
                }
            }
        )
        
        logger.info(f"Agent '{self.name}' registered {len(self.get_tools())} tools")
    
    def _register_resources(self):
        """Register agent resources"""
        
        # Memory stats resource
        self.server.register_resource(
            resource=MCPResource(
                uri="memory://stats",
                name="Memory Statistics",
                description="Current memory statistics for the agent",
                mimeType="application/json",
            ),
            handler=self._memory_stats_resource,
        )
        
        # Memory list resource
        self.server.register_resource(
            resource=MCPResource(
                uri="memory://list",
                name="Memory List",
                description="List of all stored memories",
                mimeType="application/json",
            ),
            handler=self._memory_list_resource,
        )
        
        # Phase 4: Search & Knowledge resources
        
        # search://index resource
        self.server.register_resource(
            resource=MCPResource(
                uri="search://index",
                name="Search Index Statistics",
                description="Search index statistics and health information",
                mimeType="application/json",
            ),
            handler=self._search_index_resource,
        )
        
        # knowledge://topics resource
        self.server.register_resource(
            resource=MCPResource(
                uri="knowledge://topics",
                name="Knowledge Topics",
                description="Available knowledge topics in the knowledge base",
                mimeType="application/json",
            ),
            handler=self._knowledge_topics_resource,
        )
        
        # search://history resource
        self.server.register_resource(
            resource=MCPResource(
                uri="search://history",
                name="Search History",
                description="Recent search queries and results",
                mimeType="application/json",
            ),
            handler=self._search_history_resource,
        )
        
        # Phase 5: Communication & Notifications resources
        
        # notification://queue resource
        self.server.register_resource(
            resource=MCPResource(
                uri="notification://queue",
                name="Notification Queue",
                description="Pending notifications queue",
                mimeType="application/json",
            ),
            handler=self._notification_queue_resource,
        )
        
        # channel://list resource
        self.server.register_resource(
            resource=MCPResource(
                uri="channel://list",
                name="Channel List",
                description="Available communication channels",
                mimeType="application/json",
            ),
            handler=self._channel_list_resource,
        )
        
        # Phase 6: Data & Database Operations resources
        
        # db://schemas resource
        self.server.register_resource(
            resource=MCPResource(
                uri="db://schemas",
                name="Database Schemas",
                description="Available database schemas",
                mimeType="application/json",
            ),
            handler=self._db_schemas_resource,
        )
        
        # data://samples resource
        self.server.register_resource(
            resource=MCPResource(
                uri="data://samples",
                name="Sample Data Sets",
                description="Sample data sets for testing and examples",
                mimeType="application/json",
            ),
            handler=self._data_samples_resource,
        )
        
        # Phase 7: System & Monitoring resources
        
        # system://metrics resource
        self.server.register_resource(
            resource=MCPResource(
                uri="system://metrics",
                name="System Metrics",
                description="Real-time system metrics dashboard",
                mimeType="application/json",
            ),
            handler=self._system_metrics_resource,
        )
        
        # log://recent resource
        self.server.register_resource(
            resource=MCPResource(
                uri="log://recent",
                name="Recent Logs",
                description="Recent system log entries",
                mimeType="application/json",
            ),
            handler=self._log_recent_resource,
        )
        
        logger.info(f"Agent '{self.name}' registered {len(self.server.get_resources())} resources")
    
    def _register_prompts(self):
        """Register agent prompts"""
        
        # Memory search prompt
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="memory_search",
                description="Search prompt for finding memories",
                arguments=[
                    MCPPromptArgument(
                        name="query",
                        description="Search query",
                        required=True,
                    )
                ],
                template="Search for memories matching: {{query}}",
            ),
            handler=self._memory_search_prompt,
        )
        
        # Memory summary prompt
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="memory_summary",
                description="Generate a summary of stored memories",
                arguments=[
                    MCPPromptArgument(
                        name="limit",
                        description="Maximum number of memories to include",
                        required=False,
                    )
                ],
                template="Summarize the following {{limit}} memories:",
            ),
            handler=self._memory_summary_prompt,
        )
        
        # Phase 4: Search & Knowledge prompts
        
        # search_strategy prompt
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="search_strategy",
                description="Suggest search strategy for query",
                arguments=[
                    MCPPromptArgument(
                        name="query",
                        description="Search query",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="context",
                        description="Optional context for the search",
                        required=False,
                    )
                ],
                template="Suggest search strategy for: {{query}}. Context: {{context}}",
            ),
            handler=self._search_strategy_prompt,
        )
        
        # knowledge_synthesis prompt
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="knowledge_synthesis",
                description="Synthesize knowledge from multiple sources",
                arguments=[
                    MCPPromptArgument(
                        name="sources",
                        description="List of source identifiers",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="question",
                        description="Question to answer",
                        required=True,
                    )
                ],
                template="Synthesize knowledge from {{sources}} to answer: {{question}}",
            ),
            handler=self._knowledge_synthesis_prompt,
        )
        
        # Phase 5: Communication & Notifications prompts
        
        # notification_draft prompt
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="notification_draft",
                description="Draft notification message",
                arguments=[
                    MCPPromptArgument(
                        name="event",
                        description="Event that triggered the notification",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="recipient",
                        description="Recipient ID",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="context",
                        description="Optional context information",
                        required=False,
                    )
                ],
                template="Draft notification for {{event}} to {{recipient}}. Context: {{context}}",
            ),
            handler=self._notification_draft_prompt,
        )
        
        # channel_organization prompt
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="channel_organization",
                description="Suggest channel organization",
                arguments=[
                    MCPPromptArgument(
                        name="topics",
                        description="List of topics to organize",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="participants",
                        description="List of participants",
                        required=True,
                    )
                ],
                template="Suggest channel organization for topics: {{topics}}, participants: {{participants}}",
            ),
            handler=self._channel_organization_prompt,
        )
        
        # Phase 6: Data & Database Operations prompts
        
        # query_optimization prompt
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="query_optimization",
                description="Suggest query optimization",
                arguments=[
                    MCPPromptArgument(
                        name="query",
                        description="Database query to optimize",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="schema",
                        description="Database schema information",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="context",
                        description="Optional context for optimization",
                        required=False,
                    )
                ],
                template="Optimize this query: {{query}}. Schema: {{schema}}",
            ),
            handler=self._query_optimization_prompt,
        )
        
        # Phase 7: System & Monitoring prompts
        
        # diagnostic_analysis prompt
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="diagnostic_analysis",
                description="Analyze system diagnostics",
                arguments=[
                    MCPPromptArgument(
                        name="metrics",
                        description="System metrics object",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="logs",
                        description="List of log entries",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="symptoms",
                        description="Optional symptoms description",
                        required=False,
                    )
                ],
                template="Analyze system diagnostics. Metrics: {{metrics}}, Logs: {{logs}}, Symptoms: {{symptoms}}",
            ),
            handler=self._diagnostic_analysis_prompt,
        )
        
        logger.info(f"Agent '{self.name}' registered {len(self.server.get_prompts())} prompts")
    
    async def _memory_stats_resource(self) -> str:
        """Resource handler for memory statistics"""
        import json
        stats = {
            "total_memories": len(self.memory),
            "memory_ids": list(self.memory.keys()),
        }
        return json.dumps(stats, indent=2)
    
    async def _memory_list_resource(self) -> str:
        """Resource handler for memory list"""
        import json
        return json.dumps(list(self.memory.values()), indent=2)
    
    async def _memory_search_prompt(self, query: str) -> str:
        """Prompt handler for memory search"""
        results = []
        query_lower = query.lower()
        for memory in self.memory.values():
            if query_lower in memory["content"].lower():
                results.append(memory["content"])
        
        if results:
            return f"Found {len(results)} memories matching '{query}':\n" + "\n".join(f"- {r}" for r in results[:10])
        else:
            return f"No memories found matching '{query}'"
    
    async def _memory_summary_prompt(self, limit: int = 10) -> str:
        """Prompt handler for memory summary"""
        memories = list(self.memory.values())[:limit]
        if memories:
            summary = f"Summary of {len(memories)} memories:\n"
            for memory in memories:
                summary += f"- {memory['content'][:50]}...\n"
            return summary
        else:
            return "No memories stored."
    
    async def _memory_store(self, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Store a memory
        
        Args:
            content: Memory content
            context: Optional context
            
        Returns:
            Memory ID and confirmation
        """
        import uuid
        import time
        
        memory_id = str(uuid.uuid4())
        memory = {
            "id": memory_id,
            "content": content,
            "context": context or {},
            "timestamp": time.time(),
        }
        
        self.memory[memory_id] = memory
        logger.info(f"Agent '{self.name}' stored memory: {memory_id}")
        
        return {
            "memory_id": memory_id,
            "success": True,
            "message": f"Memory stored with ID: {memory_id}",
        }
    
    async def _memory_recall(self, memory_id: Optional[str] = None, search: Optional[str] = None) -> Dict[str, Any]:
        """
        Recall a memory
        
        Args:
            memory_id: Memory ID to recall
            search: Search term to find memories
            
        Returns:
            Memory data or search results
        """
        if memory_id:
            # Recall specific memory
            if memory_id in self.memory:
                memory = self.memory[memory_id]
                logger.info(f"Agent '{self.name}' recalled memory: {memory_id}")
                return {
                    "success": True,
                    "memory": memory,
                }
            else:
                return {
                    "success": False,
                    "error": f"Memory '{memory_id}' not found",
                }
        
        elif search:
            # Search memories
            results = []
            search_lower = search.lower()
            for memory_id, memory in self.memory.items():
                if search_lower in memory["content"].lower():
                    results.append(memory)
            
            logger.info(f"Agent '{self.name}' found {len(results)} memories matching '{search}'")
            return {
                "success": True,
                "results": results,
                "count": len(results),
            }
        
        else:
            return {
                "success": False,
                "error": "Either memory_id or search must be provided",
            }
    
    async def _memory_list(self, limit: int = 100) -> Dict[str, Any]:
        """
        List all memories
        
        Args:
            limit: Maximum number of memories to return
            
        Returns:
            List of memories
        """
        memories = list(self.memory.values())
        memories = memories[:limit]
        
        logger.info(f"Agent '{self.name}' listing {len(memories)} memories")
        return {
            "success": True,
            "memories": memories,
            "count": len(memories),
            "total": len(self.memory),
        }
    
    async def _memory_delete(self, memory_id: str) -> Dict[str, Any]:
        """
        Delete a memory
        
        Args:
            memory_id: Memory ID to delete
            
        Returns:
            Deletion confirmation
        """
        if memory_id in self.memory:
            del self.memory[memory_id]
            logger.info(f"Agent '{self.name}' deleted memory: {memory_id}")
            return {
                "success": True,
                "message": f"Memory '{memory_id}' deleted",
            }
        else:
            return {
                "success": False,
                "error": f"Memory '{memory_id}' not found",
            }
    
    # Phase 4: Search & Knowledge tool handlers
    
    async def _search_text(self, query: str, scope: Optional[List[str]] = None, limit: int = 10) -> Dict[str, Any]:
        """
        Full-text search across indexed content
        
        Args:
            query: Search query text
            scope: Optional list of content IDs to search within
            limit: Maximum number of results
            
        Returns:
            Search results with snippets
        """
        query_lower = query.lower()
        query_words = query_lower.split()
        results = []
        
        # Record search in history
        self.search_history.append({
            "query": query,
            "type": "text",
            "timestamp": time.time(),
            "scope": scope,
        })
        # Keep only last 100 searches
        if len(self.search_history) > 100:
            self.search_history = self.search_history[-100:]
        
        # Search through indexed content
        search_space = self.search_index
        if scope:
            search_space = {cid: self.search_index[cid] for cid in scope if cid in self.search_index}
        
        for content_id, indexed in search_space.items():
            content_lower = indexed["content"].lower()
            # Simple keyword matching
            matches = sum(1 for word in query_words if word in content_lower)
            if matches > 0:
                # Create snippet
                snippet_start = max(0, content_lower.find(query_words[0]) - 50)
                snippet_end = min(len(indexed["content"]), snippet_start + 150)
                snippet = indexed["content"][snippet_start:snippet_end]
                if snippet_start > 0:
                    snippet = "..." + snippet
                if snippet_end < len(indexed["content"]):
                    snippet = snippet + "..."
                
                results.append({
                    "content_id": content_id,
                    "snippet": snippet,
                    "relevance": matches / len(query_words),
                    "metadata": indexed.get("metadata", {}),
                })
        
        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        results = results[:limit]
        
        logger.info(f"Agent '{self.name}' found {len(results)} results for text search: '{query}'")
        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
        }
    
    async def _search_semantic(self, query: str, threshold: float = 0.5, limit: int = 10) -> Dict[str, Any]:
        """
        Semantic search using simplified keyword-based similarity
        
        Args:
            query: Search query
            threshold: Minimum similarity threshold
            limit: Maximum number of results
            
        Returns:
            Similar content ranked by relevance
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        results = []
        
        # Record search in history
        self.search_history.append({
            "query": query,
            "type": "semantic",
            "timestamp": time.time(),
            "threshold": threshold,
        })
        if len(self.search_history) > 100:
            self.search_history = self.search_history[-100:]
        
        # Calculate similarity for each indexed content
        for content_id, indexed in self.search_index.items():
            content_lower = indexed["content"].lower()
            content_words = set(content_lower.split())
            
            # Simple Jaccard similarity (intersection over union)
            intersection = len(query_words & content_words)
            union = len(query_words | content_words)
            similarity = intersection / union if union > 0 else 0.0
            
            if similarity >= threshold:
                # Create snippet
                snippet_start = max(0, len(indexed["content"]) // 2 - 75)
                snippet_end = min(len(indexed["content"]), snippet_start + 150)
                snippet = indexed["content"][snippet_start:snippet_end]
                if snippet_start > 0:
                    snippet = "..." + snippet
                if snippet_end < len(indexed["content"]):
                    snippet = snippet + "..."
                
                results.append({
                    "content_id": content_id,
                    "snippet": snippet,
                    "similarity": similarity,
                    "metadata": indexed.get("metadata", {}),
                })
        
        # Sort by similarity
        results.sort(key=lambda x: x["similarity"], reverse=True)
        results = results[:limit]
        
        logger.info(f"Agent '{self.name}' found {len(results)} results for semantic search: '{query}'")
        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
        }
    
    async def _index_content(self, content: str, metadata: Optional[Dict[str, Any]] = None, type: Optional[str] = None) -> Dict[str, Any]:
        """
        Index content for search
        
        Args:
            content: Content to index
            metadata: Optional metadata (if 'topic' is present, also adds to knowledge base)
            type: Content type
            
        Returns:
            Index ID and confirmation
        """
        content_id = str(uuid.uuid4())
        metadata = metadata or {}
        
        indexed = {
            "content": content,
            "metadata": metadata,
            "type": type or "general",
            "indexed_at": time.time(),
        }
        
        self.search_index[content_id] = indexed
        
        # Index keywords for semantic search
        content_lower = content.lower()
        keywords = set(content_lower.split())
        for keyword in keywords:
            if len(keyword) > 2:  # Only index words longer than 2 chars
                self.semantic_index[keyword].append(content_id)
        
        # If metadata includes a topic, also add to knowledge base
        if "topic" in metadata:
            topic = metadata["topic"]
            knowledge_entry = {
                "content": content,
                "content_id": content_id,
                "type": type or "general",
                "metadata": metadata,
                "indexed_at": time.time(),
            }
            self.knowledge_base[topic].append(knowledge_entry)
            logger.debug(f"Agent '{self.name}' added content to knowledge base topic: {topic}")
        
        logger.info(f"Agent '{self.name}' indexed content: {content_id}")
        return {
            "index_id": content_id,
            "success": True,
            "message": f"Content indexed with ID: {content_id}",
        }
    
    async def _knowledge_query(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 10) -> Dict[str, Any]:
        """
        Query indexed knowledge base
        
        Args:
            query: Query to search knowledge base
            filters: Optional filters (topic, type, etc.)
            limit: Maximum number of results
            
        Returns:
            Relevant knowledge entries
        """
        query_lower = query.lower()
        results = []
        
        # Record search in history
        self.search_history.append({
            "query": query,
            "type": "knowledge",
            "timestamp": time.time(),
            "filters": filters,
        })
        if len(self.search_history) > 100:
            self.search_history = self.search_history[-100:]
        
        # Search through knowledge base
        for topic, entries in self.knowledge_base.items():
            # Apply topic filter if specified
            if filters and "topic" in filters:
                if topic != filters["topic"]:
                    continue
            
            for entry in entries:
                # Apply type filter if specified
                if filters and "type" in filters:
                    if entry.get("type") != filters["type"]:
                        continue
                
                # Search in entry content
                entry_text = json.dumps(entry).lower()
                if query_lower in entry_text:
                    results.append({
                        "topic": topic,
                        "entry": entry,
                        "relevance": 1.0,  # Simplified
                    })
        
        # Also search indexed content
        text_results = await self._search_text(query, limit=limit)
        for result in text_results.get("results", []):
            content_id = result["content_id"]
            indexed = self.search_index.get(content_id, {})
            if indexed:
                results.append({
                    "topic": indexed.get("metadata", {}).get("topic", "general"),
                    "entry": {
                        "content": indexed["content"],
                        "metadata": indexed.get("metadata", {}),
                        "type": indexed.get("type", "general"),
                    },
                    "relevance": result.get("relevance", 0.5),
                })
        
        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        results = results[:limit]
        
        logger.info(f"Agent '{self.name}' found {len(results)} knowledge entries for: '{query}'")
        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
        }
    
    async def _web_search(self, query: str, limit: int = 10, sources: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Search the web (simulated - returns message that web search is not enabled)
        
        Args:
            query: Web search query
            limit: Maximum number of results
            sources: Optional list of sources
            
        Returns:
            Web search results (or message that it's not enabled)
        """
        # Record search in history
        self.search_history.append({
            "query": query,
            "type": "web",
            "timestamp": time.time(),
            "sources": sources,
        })
        if len(self.search_history) > 100:
            self.search_history = self.search_history[-100:]
        
        logger.info(f"Agent '{self.name}' web search requested: '{query}'")
        return {
            "success": False,
            "query": query,
            "message": "Web search is not enabled. To enable web search, configure a web search provider.",
            "results": [],
            "count": 0,
        }
    
    # Phase 4: Search & Knowledge resource handlers
    
    async def _search_index_resource(self) -> str:
        """Resource handler for search index statistics"""
        stats = {
            "total_indexed": len(self.search_index),
            "index_size": sum(len(v["content"]) for v in self.search_index.values()),
            "semantic_index_size": sum(len(ids) for ids in self.semantic_index.values()),
            "index_types": {},
        }
        
        # Count by type
        for indexed in self.search_index.values():
            content_type = indexed.get("type", "general")
            stats["index_types"][content_type] = stats["index_types"].get(content_type, 0) + 1
        
        return json.dumps(stats, indent=2)
    
    async def _knowledge_topics_resource(self) -> str:
        """Resource handler for knowledge topics"""
        topics = {
            "topics": list(self.knowledge_base.keys()),
            "topic_counts": {topic: len(entries) for topic, entries in self.knowledge_base.items()},
            "total_entries": sum(len(entries) for entries in self.knowledge_base.values()),
        }
        return json.dumps(topics, indent=2)
    
    async def _search_history_resource(self) -> str:
        """Resource handler for search history"""
        # Return last 50 searches
        recent_history = self.search_history[-50:] if len(self.search_history) > 50 else self.search_history
        return json.dumps({
            "total_searches": len(self.search_history),
            "recent_searches": recent_history,
        }, indent=2)
    
    # Phase 4: Search & Knowledge prompt handlers
    
    async def _search_strategy_prompt(self, query: str, context: Optional[str] = None) -> str:
        """Prompt handler for search strategy"""
        strategy_parts = [
            f"Search Strategy for: '{query}'",
            "",
            "1. **Query Analysis**:",
            f"   - Query: {query}",
            f"   - Context: {context or 'None provided'}",
            "",
            "2. **Recommended Search Approaches**:",
        ]
        
        # Suggest search type based on query
        query_lower = query.lower()
        if any(word in query_lower for word in ["how", "what", "why", "explain", "describe"]):
            strategy_parts.append("   - Use semantic search for conceptual understanding")
            strategy_parts.append("   - Query knowledge base for structured information")
        else:
            strategy_parts.append("   - Use text search for exact matches")
            strategy_parts.append("   - Use semantic search for related concepts")
        
        strategy_parts.extend([
            "",
            "3. **Search Tips**:",
            "   - Break complex queries into simpler parts",
            "   - Use specific keywords for better results",
            "   - Combine text and semantic search for comprehensive results",
        ])
        
        return "\n".join(strategy_parts)
    
    async def _knowledge_synthesis_prompt(self, sources: str, question: str) -> str:
        """Prompt handler for knowledge synthesis"""
        # Parse sources (could be JSON string or comma-separated)
        try:
            if isinstance(sources, str):
                source_list = json.loads(sources) if sources.startswith("[") else sources.split(",")
            else:
                source_list = sources
        except:
            source_list = [sources] if isinstance(sources, str) else sources
        
        synthesis_parts = [
            f"Knowledge Synthesis",
            "",
            f"**Question**: {question}",
            "",
            f"**Sources**: {', '.join(str(s) for s in source_list)}",
            "",
            "**Synthesis**:",
        ]
        
        # Gather information from sources
        synthesized_info = []
        for source in source_list:
            source_str = str(source).strip()
            # Try to find in knowledge base
            for topic, entries in self.knowledge_base.items():
                if source_str in topic or any(source_str in json.dumps(e) for e in entries):
                    synthesized_info.append(f"- From topic '{topic}': {len(entries)} entries")
                    break
            # Try to find in indexed content
            for content_id, indexed in self.search_index.items():
                if source_str in content_id or source_str in indexed["content"]:
                    synthesized_info.append(f"- From indexed content: {indexed['content'][:100]}...")
                    break
        
        if synthesized_info:
            synthesis_parts.extend(synthesized_info)
            synthesis_parts.append("")
            synthesis_parts.append("**Answer**: Based on the synthesized information from the sources above, here is a comprehensive answer to the question.")
        else:
            synthesis_parts.append("No matching sources found. Please verify the source identifiers.")
        
        return "\n".join(synthesis_parts)
    
    # Phase 5: Communication & Notifications tool handlers
    
    async def _notification_send(
        self,
        recipient: str,
        message: str,
        priority: str = "normal",
        type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send notification to user/agent
        
        Args:
            recipient: Recipient ID
            message: Notification message
            priority: Notification priority (low, normal, high, urgent)
            type: Notification type
            
        Returns:
            Notification ID and confirmation
        """
        notification_id = str(uuid.uuid4())
        
        notification = {
            "id": notification_id,
            "recipient": recipient,
            "message": message,
            "priority": priority,
            "type": type or "info",
            "status": "unread",
            "created_at": time.time(),
            "sender": self.agent_id,
        }
        
        self.notifications[notification_id] = notification
        self.notification_queue.append(notification_id)
        
        logger.info(f"Agent '{self.name}' sent notification to '{recipient}': {notification_id}")
        return {
            "notification_id": notification_id,
            "success": True,
            "message": f"Notification sent to {recipient}",
        }
    
    async def _notification_list(
        self,
        recipient: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        List notifications
        
        Args:
            recipient: Filter by recipient ID
            status: Filter by read status (read, unread)
            limit: Maximum number of notifications
            
        Returns:
            List of notifications
        """
        notifications = list(self.notifications.values())
        
        # Apply filters
        if recipient:
            notifications = [n for n in notifications if n["recipient"] == recipient]
        
        if status:
            notifications = [n for n in notifications if n["status"] == status]
        
        # Sort by creation time (newest first)
        notifications.sort(key=lambda x: x["created_at"], reverse=True)
        notifications = notifications[:limit]
        
        logger.info(f"Agent '{self.name}' listing {len(notifications)} notifications")
        return {
            "success": True,
            "notifications": notifications,
            "count": len(notifications),
            "total": len(self.notifications),
        }
    
    async def _channel_create(
        self,
        name: str,
        type: str = "public",
        participants: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create communication channel
        
        Args:
            name: Channel name
            type: Channel type (public, private)
            participants: Initial participants
            
        Returns:
            Channel ID and confirmation
        """
        channel_id = str(uuid.uuid4())
        
        channel = {
            "id": channel_id,
            "name": name,
            "type": type,
            "participants": participants or [],
            "created_at": time.time(),
            "created_by": self.agent_id,
            "message_count": 0,
        }
        
        self.channels[channel_id] = channel
        self.channel_messages[channel_id] = []
        
        logger.info(f"Agent '{self.name}' created channel '{name}': {channel_id}")
        return {
            "channel_id": channel_id,
            "success": True,
            "message": f"Channel '{name}' created",
        }
    
    async def _channel_message(
        self,
        channel_id: str,
        message: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Send message to channel
        
        Args:
            channel_id: Channel ID
            message: Message content
            attachments: Optional message attachments
            
        Returns:
            Message ID and confirmation
        """
        if channel_id not in self.channels:
            return {
                "success": False,
                "error": f"Channel '{channel_id}' not found",
            }
        
        message_id = str(uuid.uuid4())
        
        channel_message = {
            "id": message_id,
            "channel_id": channel_id,
            "message": message,
            "attachments": attachments or [],
            "sender": self.agent_id,
            "sender_name": self.name,
            "created_at": time.time(),
        }
        
        self.channel_messages[channel_id].append(channel_message)
        self.channels[channel_id]["message_count"] += 1
        
        logger.info(f"Agent '{self.name}' sent message to channel '{channel_id}': {message_id}")
        return {
            "message_id": message_id,
            "success": True,
            "message": f"Message sent to channel",
        }
    
    # Phase 5: Communication & Notifications resource handlers
    
    async def _notification_queue_resource(self) -> str:
        """Resource handler for notification queue"""
        pending = []
        for notification_id in self.notification_queue:
            if notification_id in self.notifications:
                notification = self.notifications[notification_id]
                if notification["status"] == "unread":
                    pending.append(notification)
        
        queue_data = {
            "pending_count": len(pending),
            "total_in_queue": len(self.notification_queue),
            "pending_notifications": pending[:50],  # Last 50 pending
        }
        return json.dumps(queue_data, indent=2)
    
    async def _channel_list_resource(self) -> str:
        """Resource handler for channel list"""
        channels_list = []
        for channel_id, channel in self.channels.items():
            channel_info = {
                "id": channel_id,
                "name": channel["name"],
                "type": channel["type"],
                "participants": channel["participants"],
                "message_count": channel["message_count"],
                "created_at": channel["created_at"],
            }
            channels_list.append(channel_info)
        
        # Sort by message count (most active first)
        channels_list.sort(key=lambda x: x["message_count"], reverse=True)
        
        return json.dumps({
            "total_channels": len(self.channels),
            "channels": channels_list,
        }, indent=2)
    
    # Phase 5: Communication & Notifications prompt handlers
    
    async def _notification_draft_prompt(
        self,
        event: str,
        recipient: str,
        context: Optional[str] = None
    ) -> str:
        """Prompt handler for notification drafting"""
        draft_parts = [
            f"Notification Draft",
            "",
            f"**Event**: {event}",
            f"**Recipient**: {recipient}",
            f"**Context**: {context or 'None provided'}",
            "",
            "**Drafted Notification**:",
            "",
        ]
        
        # Generate appropriate notification based on event type
        event_lower = event.lower()
        
        if "complete" in event_lower or "finished" in event_lower:
            draft_parts.append(f"✅ Task completed successfully!")
            draft_parts.append("")
            draft_parts.append(f"Your task has been completed. {context or 'Please review the results.'}")
        elif "error" in event_lower or "failed" in event_lower:
            draft_parts.append(f"⚠️ Action encountered an issue")
            draft_parts.append("")
            draft_parts.append(f"An error occurred: {context or 'Please check the details.'}")
        elif "alert" in event_lower or "warning" in event_lower:
            draft_parts.append(f"🔔 Alert: {event}")
            draft_parts.append("")
            draft_parts.append(f"{context or 'Please review this alert.'}")
        else:
            draft_parts.append(f"ℹ️ {event}")
            draft_parts.append("")
            draft_parts.append(f"{context or 'Notification details.'}")
        
        draft_parts.extend([
            "",
            "**Tips for effective notifications**:",
            "- Keep messages concise and clear",
            "- Include relevant context",
            "- Use appropriate priority levels",
            "- Provide actionable information when possible",
        ])
        
        return "\n".join(draft_parts)
    
    async def _channel_organization_prompt(
        self,
        topics: str,
        participants: str
    ) -> str:
        """Prompt handler for channel organization"""
        # Parse topics and participants (could be JSON strings or comma-separated)
        try:
            if isinstance(topics, str):
                topics_list = json.loads(topics) if topics.startswith("[") else [t.strip() for t in topics.split(",")]
            else:
                topics_list = topics
        except:
            topics_list = [topics] if isinstance(topics, str) else topics
        
        try:
            if isinstance(participants, str):
                participants_list = json.loads(participants) if participants.startswith("[") else [p.strip() for p in participants.split(",")]
            else:
                participants_list = participants
        except:
            participants_list = [participants] if isinstance(participants, str) else participants
        
        organization_parts = [
            f"Channel Organization Suggestions",
            "",
            f"**Topics**: {', '.join(str(t) for t in topics_list)}",
            f"**Participants**: {', '.join(str(p) for p in participants_list)}",
            "",
            "**Recommended Channel Structure**:",
            "",
        ]
        
        # Suggest channels based on topics
        if len(topics_list) == 1:
            organization_parts.append(f"1. **Single Channel Approach**:")
            organization_parts.append(f"   - Create one channel: '{topics_list[0]}'")
            organization_parts.append(f"   - Type: Public (if all participants should have access)")
            organization_parts.append(f"   - Participants: {', '.join(str(p) for p in participants_list)}")
        else:
            organization_parts.append(f"1. **Multi-Channel Approach**:")
            for i, topic in enumerate(topics_list, 1):
                organization_parts.append(f"   - Channel {i}: '{topic}'")
                organization_parts.append(f"     Type: Public")
                organization_parts.append(f"     Participants: {', '.join(str(p) for p in participants_list)}")
        
        organization_parts.extend([
            "",
            "**Best Practices**:",
            "- Use descriptive channel names",
            "- Keep related topics together",
            "- Consider private channels for sensitive discussions",
            "- Regularly archive inactive channels",
            "- Use consistent naming conventions",
        ])
        
        return "\n".join(organization_parts)
    
    # Phase 6: Data & Database Operations tool handlers
    
    async def _db_query(
        self,
        query: str,
        database: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute database query
        
        Args:
            query: Database query (SQL or query string)
            database: Database name (optional)
            params: Query parameters
            
        Returns:
            Query results
        """
        db_name = database or "default"
        params = params or {}
        
        # Initialize database if it doesn't exist
        if db_name not in self.in_memory_dbs:
            self.in_memory_dbs[db_name] = defaultdict(list)
        
        # Simple query execution for in-memory database
        # This is a simplified implementation - in production would use actual SQL
        query_lower = query.lower().strip()
        results = []
        
        if query_lower.startswith("select"):
            # Simple SELECT query parsing
            # Extract table name (simplified)
            if "from" in query_lower:
                parts = query_lower.split("from")
                if len(parts) > 1:
                    table_name = parts[1].split()[0].strip()
                    if table_name in self.in_memory_dbs[db_name]:
                        results = self.in_memory_dbs[db_name][table_name][:]
                        # Apply WHERE clause if present (simplified)
                        if "where" in query_lower:
                            # Very basic WHERE filtering
                            where_part = query_lower.split("where")[1] if "where" in query_lower else ""
                            # This is a simplified implementation
                            pass
        elif query_lower.startswith("insert"):
            # Simple INSERT query
            if "into" in query_lower:
                parts = query_lower.split("into")
                if len(parts) > 1:
                    table_name = parts[1].split()[0].strip()
                    # Create a simple record
                    record = {"id": str(uuid.uuid4()), "data": params}
                    self.in_memory_dbs[db_name][table_name].append(record)
                    results = [{"inserted": True, "id": record["id"]}]
        elif query_lower.startswith("create table"):
            # Simple CREATE TABLE
            if "table" in query_lower:
                parts = query_lower.split("table")
                if len(parts) > 1:
                    table_name = parts[1].split()[0].strip()
                    self.in_memory_dbs[db_name][table_name] = []
                    results = [{"created": True, "table": table_name}]
        
        logger.info(f"Agent '{self.name}' executed query on database '{db_name}'")
        return {
            "success": True,
            "query": query,
            "database": db_name,
            "results": results,
            "count": len(results),
        }
    
    async def _db_schema(
        self,
        database: Optional[str] = None,
        table: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get database schema
        
        Args:
            database: Database name (optional)
            table: Table name (optional)
            
        Returns:
            Schema information
        """
        db_name = database or "default"
        
        if db_name not in self.db_schemas:
            # Generate schema from in-memory database
            schema = {
                "database": db_name,
                "tables": {}
            }
            
            if db_name in self.in_memory_dbs:
                for table_name, rows in self.in_memory_dbs[db_name].items():
                    table_schema = {
                        "name": table_name,
                        "columns": [],
                        "row_count": len(rows)
                    }
                    # Infer columns from first row if available
                    if rows:
                        first_row = rows[0]
                        if isinstance(first_row, dict):
                            table_schema["columns"] = list(first_row.keys())
                    schema["tables"][table_name] = table_schema
            
            self.db_schemas[db_name] = schema
        
        schema_info = self.db_schemas[db_name]
        
        # Filter by table if specified
        if table:
            if table in schema_info.get("tables", {}):
                return {
                    "success": True,
                    "database": db_name,
                    "table": table,
                    "schema": schema_info["tables"][table],
                }
            else:
                return {
                    "success": False,
                    "error": f"Table '{table}' not found in database '{db_name}'",
                }
        
        logger.info(f"Agent '{self.name}' retrieved schema for database '{db_name}'")
        return {
            "success": True,
            "database": db_name,
            "schema": schema_info,
        }
    
    async def _data_transform(
        self,
        data: Any,
        from_format: str,
        to_format: str
    ) -> Dict[str, Any]:
        """
        Transform data format
        
        Args:
            data: Data to transform
            from_format: Source format
            to_format: Target format
            
        Returns:
            Transformed data
        """
        from_format_lower = from_format.lower()
        to_format_lower = to_format.lower()
        
        # Parse input data
        parsed_data = None
        
        if from_format_lower == "json":
            if isinstance(data, str):
                parsed_data = json.loads(data)
            else:
                parsed_data = data
        elif from_format_lower == "csv":
            # Simple CSV parsing
            if isinstance(data, str):
                lines = data.strip().split("\n")
                if lines:
                    headers = lines[0].split(",")
                    parsed_data = []
                    for line in lines[1:]:
                        values = line.split(",")
                        parsed_data.append(dict(zip(headers, values)))
        else:
            parsed_data = data
        
        # Transform to target format
        result_data = None
        
        if to_format_lower == "json":
            result_data = json.dumps(parsed_data, indent=2) if not isinstance(parsed_data, str) else parsed_data
        elif to_format_lower == "csv":
            if isinstance(parsed_data, list) and parsed_data:
                headers = list(parsed_data[0].keys())
                csv_lines = [",".join(headers)]
                for row in parsed_data:
                    csv_lines.append(",".join(str(row.get(h, "")) for h in headers))
                result_data = "\n".join(csv_lines)
            else:
                result_data = str(parsed_data)
        else:
            result_data = str(parsed_data)
        
        logger.info(f"Agent '{self.name}' transformed data from {from_format} to {to_format}")
        return {
            "success": True,
            "from_format": from_format,
            "to_format": to_format,
            "data": result_data,
        }
    
    async def _data_analyze(
        self,
        data: Any,
        analysis_type: str = "statistics",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze data (statistics, patterns)
        
        Args:
            data: Data to analyze
            analysis_type: Type of analysis
            options: Analysis options
            
        Returns:
            Analysis results
        """
        options = options or {}
        
        # Parse data if it's a string
        if isinstance(data, str):
            try:
                parsed_data = json.loads(data)
            except:
                parsed_data = data
        else:
            parsed_data = data
        
        analysis_results = {
            "analysis_type": analysis_type,
            "data_type": type(parsed_data).__name__,
        }
        
        if analysis_type == "statistics":
            if isinstance(parsed_data, list):
                analysis_results["count"] = len(parsed_data)
                if parsed_data:
                    if isinstance(parsed_data[0], dict):
                        # Analyze dictionary list
                        all_keys = set()
                        for item in parsed_data:
                            all_keys.update(item.keys())
                        analysis_results["keys"] = list(all_keys)
                        analysis_results["sample"] = parsed_data[0] if parsed_data else None
            elif isinstance(parsed_data, dict):
                analysis_results["keys"] = list(parsed_data.keys())
                analysis_results["count"] = len(parsed_data)
        elif analysis_type == "summary":
            if isinstance(parsed_data, list):
                analysis_results["summary"] = f"List with {len(parsed_data)} items"
            elif isinstance(parsed_data, dict):
                analysis_results["summary"] = f"Dictionary with {len(parsed_data)} keys"
            else:
                analysis_results["summary"] = str(parsed_data)[:100]
        
        logger.info(f"Agent '{self.name}' analyzed data with type '{analysis_type}'")
        return {
            "success": True,
            "analysis": analysis_results,
        }
    
    async def _data_export(
        self,
        data: Any,
        format: str,
        path: str
    ) -> Dict[str, Any]:
        """
        Export data to file
        
        Args:
            data: Data to export
            format: Export format
            path: File path
            
        Returns:
            Export confirmation
        """
        # In a real implementation, this would write to a file
        # For now, we'll simulate it and return the data
        format_lower = format.lower()
        
        # Transform data to target format
        export_data = None
        
        if format_lower == "json":
            if isinstance(data, str):
                try:
                    parsed = json.loads(data)
                    export_data = json.dumps(parsed, indent=2)
                except:
                    export_data = data
            else:
                export_data = json.dumps(data, indent=2)
        elif format_lower == "csv":
            if isinstance(data, list) and data:
                if isinstance(data[0], dict):
                    headers = list(data[0].keys())
                    csv_lines = [",".join(headers)]
                    for row in data:
                        csv_lines.append(",".join(str(row.get(h, "")) for h in headers))
                    export_data = "\n".join(csv_lines)
        else:
            export_data = str(data)
        
        # In production, would write to file at path
        # For now, we'll just return success
        logger.info(f"Agent '{self.name}' exported data to {path} in {format} format")
        return {
            "success": True,
            "path": path,
            "format": format,
            "size": len(str(export_data)) if export_data else 0,
            "message": f"Data exported to {path}",
        }
    
    # Phase 6: Data & Database Operations resource handlers
    
    async def _db_schemas_resource(self) -> str:
        """Resource handler for database schemas"""
        schemas_list = []
        for db_name, schema in self.db_schemas.items():
            schemas_list.append({
                "database": db_name,
                "tables": list(schema.get("tables", {}).keys()),
                "table_count": len(schema.get("tables", {})),
            })
        
        # Also include in-memory databases that don't have schemas yet
        for db_name in self.in_memory_dbs:
            if db_name not in self.db_schemas:
                schemas_list.append({
                    "database": db_name,
                    "tables": list(self.in_memory_dbs[db_name].keys()),
                    "table_count": len(self.in_memory_dbs[db_name]),
                })
        
        return json.dumps({
            "total_databases": len(set(list(self.db_schemas.keys()) + list(self.in_memory_dbs.keys()))),
            "databases": schemas_list,
        }, indent=2)
    
    async def _data_samples_resource(self) -> str:
        """Resource handler for sample data sets"""
        # Initialize some sample data if empty
        if not self.sample_data:
            self.sample_data = {
                "users": [
                    {"id": 1, "name": "Alice", "email": "alice@example.com", "active": True},
                    {"id": 2, "name": "Bob", "email": "bob@example.com", "active": True},
                    {"id": 3, "name": "Charlie", "email": "charlie@example.com", "active": False},
                ],
                "products": [
                    {"id": 1, "name": "Widget A", "price": 10.99, "stock": 100},
                    {"id": 2, "name": "Widget B", "price": 15.99, "stock": 50},
                ],
            }
        
        return json.dumps({
            "sample_datasets": list(self.sample_data.keys()),
            "data": self.sample_data,
        }, indent=2)
    
    # Phase 6: Data & Database Operations prompt handlers
    
    async def _query_optimization_prompt(
        self,
        query: str,
        schema: str,
        context: Optional[str] = None
    ) -> str:
        """Prompt handler for query optimization"""
        # Parse schema if it's a string
        try:
            if isinstance(schema, str):
                schema_obj = json.loads(schema)
            else:
                schema_obj = schema
        except:
            schema_obj = {"schema": schema}
        
        optimization_parts = [
            f"Query Optimization Analysis",
            "",
            f"**Original Query**:",
            f"```sql",
            query,
            "```",
            "",
            f"**Schema Information**:",
            json.dumps(schema_obj, indent=2),
            "",
        ]
        
        if context:
            optimization_parts.extend([
                f"**Context**: {context}",
                "",
            ])
        
        optimization_parts.extend([
            "**Optimization Suggestions**:",
            "",
        ])
        
        query_lower = query.lower()
        
        # Basic optimization suggestions
        suggestions = []
        
        if "select *" in query_lower:
            suggestions.append("1. **Avoid SELECT ***: Specify only needed columns to reduce data transfer")
        
        if "where" not in query_lower and "select" in query_lower:
            suggestions.append("2. **Add WHERE clause**: Filter results early to reduce processing")
        
        if "order by" in query_lower:
            suggestions.append("3. **Index on ORDER BY columns**: Ensure indexes exist on columns used in ORDER BY")
        
        if "join" in query_lower:
            suggestions.append("4. **Join optimization**: Ensure join columns are indexed")
        
        if "like" in query_lower and "%" in query:
            if query.find("%") == 0 or query.rfind("%") == len(query) - 1:
                suggestions.append("5. **LIKE pattern**: Leading wildcards prevent index usage")
        
        if not suggestions:
            suggestions.append("1. **Review execution plan**: Use EXPLAIN to understand query execution")
            suggestions.append("2. **Check indexes**: Ensure appropriate indexes exist")
            suggestions.append("3. **Consider caching**: Cache frequently accessed data")
        
        optimization_parts.extend(suggestions)
        optimization_parts.extend([
            "",
            "**Best Practices**:",
            "- Use indexes on frequently queried columns",
            "- Limit result sets with LIMIT when possible",
            "- Avoid N+1 queries - use JOINs or batch queries",
            "- Monitor query performance and adjust as needed",
        ])
        
        return "\n".join(optimization_parts)
    
    # Phase 7: System & Monitoring tool handlers
    
    async def _system_status(
        self,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get system status (CPU, memory, disk)
        
        Args:
            metrics: Specific metrics to retrieve (optional)
            
        Returns:
            System metrics
        """
        metrics = metrics or ["cpu", "memory", "disk", "network"]
        metrics_lower = [m.lower() for m in metrics]
        
        status = {
            "timestamp": time.time(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
        }
        
        if PSUTIL_AVAILABLE:
            if "cpu" in metrics_lower or "all" in metrics_lower:
                status["cpu"] = {
                    "percent": psutil.cpu_percent(interval=0.1),
                    "count": psutil.cpu_count(),
                    "per_cpu": psutil.cpu_percent(interval=0.1, percpu=True),
                }
            
            if "memory" in metrics_lower or "all" in metrics_lower:
                mem = psutil.virtual_memory()
                status["memory"] = {
                    "total": mem.total,
                    "available": mem.available,
                    "used": mem.used,
                    "percent": mem.percent,
                }
            
            if "disk" in metrics_lower or "all" in metrics_lower:
                disk = psutil.disk_usage('/')
                status["disk"] = {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100,
                }
            
            if "network" in metrics_lower or "all" in metrics_lower:
                net_io = psutil.net_io_counters()
                status["network"] = {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv,
                }
        else:
            # Simulated metrics when psutil is not available
            status["cpu"] = {"percent": 25.0, "count": 4, "note": "simulated"}
            status["memory"] = {"total": 8589934592, "used": 2147483648, "percent": 25.0, "note": "simulated"}
            status["disk"] = {"total": 107374182400, "used": 26843545600, "percent": 25.0, "note": "simulated"}
            status["network"] = {"bytes_sent": 0, "bytes_recv": 0, "note": "simulated"}
        
        # Store metrics in history
        self.metrics_history.append(status)
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]
        
        logger.info(f"Agent '{self.name}' retrieved system status")
        return {
            "success": True,
            "metrics": status,
        }
    
    async def _log_query(
        self,
        level: Optional[str] = None,
        pattern: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Query system logs
        
        Args:
            level: Filter by log level
            pattern: Search pattern in log messages
            limit: Maximum number of log entries
            
        Returns:
            Log entries
        """
        # Add current log entry
        log_entry = {
            "timestamp": time.time(),
            "level": "INFO",
            "message": f"Agent '{self.name}' log query executed",
            "source": "agent",
        }
        self.system_logs.append(log_entry)
        
        # Filter logs
        filtered_logs = list(self.system_logs)
        
        if level:
            level_upper = level.upper()
            filtered_logs = [log for log in filtered_logs if log.get("level", "").upper() == level_upper]
        
        if pattern:
            pattern_lower = pattern.lower()
            filtered_logs = [log for log in filtered_logs if pattern_lower in str(log.get("message", "")).lower()]
        
        # Sort by timestamp (newest first) and limit
        filtered_logs.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        filtered_logs = filtered_logs[:limit]
        
        # Keep only last 1000 logs
        if len(self.system_logs) > 1000:
            self.system_logs = self.system_logs[-1000:]
        
        logger.info(f"Agent '{self.name}' queried {len(filtered_logs)} log entries")
        return {
            "success": True,
            "logs": filtered_logs,
            "count": len(filtered_logs),
            "total": len(self.system_logs),
        }
    
    async def _process_list(
        self,
        filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List running processes
        
        Args:
            filter: Filter processes by name or pattern
            
        Returns:
            Process list
        """
        processes = []
        
        if PSUTIL_AVAILABLE:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    proc_info = proc.info
                    if filter:
                        if filter.lower() not in proc_info.get('name', '').lower():
                            continue
                    processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        else:
            # Simulated process list
            processes = [
                {"pid": 1, "name": "python", "cpu_percent": 5.0, "memory_percent": 10.0, "status": "running"},
                {"pid": 2, "name": "agent", "cpu_percent": 2.0, "memory_percent": 5.0, "status": "running"},
            ]
            if filter:
                processes = [p for p in processes if filter.lower() in p.get('name', '').lower()]
        
        logger.info(f"Agent '{self.name}' listed {len(processes)} processes")
        return {
            "success": True,
            "processes": processes,
            "count": len(processes),
        }
    
    async def _health_check(
        self,
        components: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Perform health check
        
        Args:
            components: Specific components to check (optional)
            
        Returns:
            Health status
        """
        components = components or ["system", "memory", "disk", "agent"]
        components_lower = [c.lower() for c in components]
        
        health_status = {
            "timestamp": time.time(),
            "overall": "healthy",
            "components": {},
        }
        
        # Check system
        if "system" in components_lower or "all" in components_lower:
            try:
                if PSUTIL_AVAILABLE:
                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    health_status["components"]["system"] = {
                        "status": "healthy" if cpu_percent < 80 else "degraded",
                        "cpu_percent": cpu_percent,
                    }
                else:
                    health_status["components"]["system"] = {
                        "status": "healthy",
                        "note": "simulated",
                    }
            except Exception as e:
                health_status["components"]["system"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
        
        # Check memory
        if "memory" in components_lower or "all" in components_lower:
            try:
                if PSUTIL_AVAILABLE:
                    mem = psutil.virtual_memory()
                    health_status["components"]["memory"] = {
                        "status": "healthy" if mem.percent < 85 else "degraded",
                        "percent": mem.percent,
                    }
                else:
                    health_status["components"]["memory"] = {
                        "status": "healthy",
                        "note": "simulated",
                    }
            except Exception as e:
                health_status["components"]["memory"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
        
        # Check disk
        if "disk" in components_lower or "all" in components_lower:
            try:
                if PSUTIL_AVAILABLE:
                    disk = psutil.disk_usage('/')
                    disk_percent = (disk.used / disk.total) * 100
                    health_status["components"]["disk"] = {
                        "status": "healthy" if disk_percent < 90 else "degraded",
                        "percent": disk_percent,
                    }
                else:
                    health_status["components"]["disk"] = {
                        "status": "healthy",
                        "note": "simulated",
                    }
            except Exception as e:
                health_status["components"]["disk"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
        
        # Check agent
        if "agent" in components_lower or "all" in components_lower:
            health_status["components"]["agent"] = {
                "status": "healthy",
                "agent_id": self.agent_id,
                "name": self.name,
                "tools_count": len(self.get_tools()),
            }
        
        # Determine overall status
        component_statuses = [comp.get("status", "unknown") for comp in health_status["components"].values()]
        if "unhealthy" in component_statuses:
            health_status["overall"] = "unhealthy"
        elif "degraded" in component_statuses:
            health_status["overall"] = "degraded"
        else:
            health_status["overall"] = "healthy"
        
        logger.info(f"Agent '{self.name}' health check: {health_status['overall']}")
        return {
            "success": True,
            "health": health_status,
        }
    
    # Phase 7: System & Monitoring resource handlers
    
    async def _system_metrics_resource(self) -> str:
        """Resource handler for system metrics"""
        # Get current metrics
        metrics_result = await self._system_status()
        current_metrics = metrics_result.get("metrics", {})
        
        # Get recent metrics history
        recent_metrics = self.metrics_history[-10:] if len(self.metrics_history) > 10 else self.metrics_history
        
        metrics_data = {
            "current": current_metrics,
            "recent_history": recent_metrics,
            "history_count": len(self.metrics_history),
        }
        
        return json.dumps(metrics_data, indent=2)
    
    async def _log_recent_resource(self) -> str:
        """Resource handler for recent log entries"""
        # Get last 50 log entries
        recent_logs = self.system_logs[-50:] if len(self.system_logs) > 50 else self.system_logs
        
        return json.dumps({
            "total_logs": len(self.system_logs),
            "recent_logs": recent_logs,
        }, indent=2)
    
    # Phase 7: System & Monitoring prompt handlers
    
    async def _diagnostic_analysis_prompt(
        self,
        metrics: str,
        logs: str,
        symptoms: Optional[str] = None
    ) -> str:
        """Prompt handler for diagnostic analysis"""
        # Parse metrics and logs if they're strings
        try:
            if isinstance(metrics, str):
                metrics_obj = json.loads(metrics)
            else:
                metrics_obj = metrics
        except:
            metrics_obj = {"metrics": metrics}
        
        try:
            if isinstance(logs, str):
                logs_list = json.loads(logs) if logs.startswith("[") else [logs]
            else:
                logs_list = logs if isinstance(logs, list) else [logs]
        except:
            logs_list = [logs] if isinstance(logs, str) else logs
        
        analysis_parts = [
            f"System Diagnostic Analysis",
            "",
            f"**Symptoms**: {symptoms or 'None provided'}",
            "",
            f"**System Metrics**:",
            json.dumps(metrics_obj, indent=2),
            "",
            f"**Recent Logs** ({len(logs_list)} entries):",
        ]
        
        # Add log entries
        for i, log_entry in enumerate(logs_list[:10], 1):  # Show first 10
            if isinstance(log_entry, dict):
                log_msg = log_entry.get("message", str(log_entry))
                log_level = log_entry.get("level", "INFO")
                analysis_parts.append(f"  {i}. [{log_level}] {log_msg}")
            else:
                analysis_parts.append(f"  {i}. {log_entry}")
        
        if len(logs_list) > 10:
            analysis_parts.append(f"  ... and {len(logs_list) - 10} more entries")
        
        analysis_parts.extend([
            "",
            "**Analysis**:",
            "",
        ])
        
        # Analyze metrics
        if isinstance(metrics_obj, dict):
            if "cpu" in metrics_obj:
                cpu_percent = metrics_obj["cpu"].get("percent", 0)
                if cpu_percent > 80:
                    analysis_parts.append("⚠️ **High CPU Usage**: CPU usage is above 80%, which may indicate performance issues.")
                elif cpu_percent > 50:
                    analysis_parts.append("ℹ️ **Moderate CPU Usage**: CPU usage is moderate.")
                else:
                    analysis_parts.append("✅ **Normal CPU Usage**: CPU usage is within normal range.")
            
            if "memory" in metrics_obj:
                mem_percent = metrics_obj["memory"].get("percent", 0)
                if mem_percent > 85:
                    analysis_parts.append("⚠️ **High Memory Usage**: Memory usage is above 85%, may need attention.")
                elif mem_percent > 70:
                    analysis_parts.append("ℹ️ **Moderate Memory Usage**: Memory usage is moderate.")
                else:
                    analysis_parts.append("✅ **Normal Memory Usage**: Memory usage is within normal range.")
            
            if "disk" in metrics_obj:
                disk_percent = metrics_obj["disk"].get("percent", 0)
                if disk_percent > 90:
                    analysis_parts.append("⚠️ **High Disk Usage**: Disk usage is above 90%, consider cleanup.")
                elif disk_percent > 75:
                    analysis_parts.append("ℹ️ **Moderate Disk Usage**: Disk usage is moderate.")
                else:
                    analysis_parts.append("✅ **Normal Disk Usage**: Disk usage is within normal range.")
        
        # Analyze logs
        error_logs = [log for log in logs_list if isinstance(log, dict) and log.get("level", "").upper() == "ERROR"]
        warning_logs = [log for log in logs_list if isinstance(log, dict) and log.get("level", "").upper() == "WARNING"]
        
        if error_logs:
            analysis_parts.append(f"")
            analysis_parts.append(f"⚠️ **Errors Found**: {len(error_logs)} error log entries detected. Review these for issues.")
        
        if warning_logs:
            analysis_parts.append(f"")
            analysis_parts.append(f"ℹ️ **Warnings Found**: {len(warning_logs)} warning log entries. Monitor these for potential issues.")
        
        if not error_logs and not warning_logs:
            analysis_parts.append("")
            analysis_parts.append("✅ **No Critical Issues**: No errors or warnings in recent logs.")
        
        analysis_parts.extend([
            "",
            "**Recommendations**:",
            "- Monitor metrics trends over time",
            "- Review error logs for patterns",
            "- Check system resources if performance degrades",
            "- Consider scaling if resource usage is consistently high",
        ])
        
        return "\n".join(analysis_parts)
    
    def get_state(self) -> Dict[str, Any]:
        """Get agent state"""
        state = super().get_state()
        state["memory_count"] = len(self.memory)
        state["search_index_count"] = len(self.search_index)
        state["knowledge_base_topics"] = len(self.knowledge_base)
        state["search_history_count"] = len(self.search_history)
        state["notifications_count"] = len(self.notifications)
        state["channels_count"] = len(self.channels)
        state["databases_count"] = len(self.in_memory_dbs)
        state["system_logs_count"] = len(self.system_logs)
        state["metrics_history_count"] = len(self.metrics_history)
        return state

