# Project Dawn - MCP API Reference

This document provides a comprehensive list of all tools, resources, and prompts available in the Project Dawn multi-agent system.

## 🤖 Agent: FirstAgent (`agent1`)

### 🛠️ Tools

#### `memory_store`
Store a memory with content and optional context

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `content` | `string` | Memory content to store | ✅ |
| `context` | `object` | Optional context information |  |

#### `memory_recall`
Recall a memory by ID or search by content

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `memory_id` | `string` | Memory ID to recall |  |
| `search` | `string` | Search term to find memories |  |

#### `memory_list`
List all stored memories

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `limit` | `integer` | Maximum number of memories to return |  |

#### `memory_delete`
Delete a memory by ID

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `memory_id` | `string` | Memory ID to delete | ✅ |

#### `search_text`
Full-text search across files/content

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `query` | `string` | Search query text | ✅ |
| `scope` | `array` | Optional list of content IDs to search within |  |
| `limit` | `integer` | Maximum number of results to return |  |

#### `search_semantic`
Semantic search (vector similarity) to find conceptually similar content

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `query` | `string` | Search query for semantic similarity | ✅ |
| `threshold` | `number` | Minimum similarity threshold (0.0-1.0) |  |
| `limit` | `integer` | Maximum number of results to return |  |

#### `index_content`
Index content for search

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `content` | `string` | Content to index | ✅ |
| `metadata` | `object` | Optional metadata for the content |  |
| `type` | `string` | Content type (e.g., 'document', 'code', 'note') |  |

#### `knowledge_query`
Query indexed knowledge base

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `query` | `string` | Query to search knowledge base | ✅ |
| `filters` | `object` | Optional filters (topic, type, etc.) |  |
| `limit` | `integer` | Maximum number of results to return |  |

#### `web_search`
Search the web (if enabled)

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `query` | `string` | Web search query | ✅ |
| `limit` | `integer` | Maximum number of results to return |  |
| `sources` | `array` | Optional list of sources to search |  |

#### `notification_send`
Send notification to user/agent

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `recipient` | `string` | Recipient ID (user or agent) | ✅ |
| `message` | `string` | Notification message | ✅ |
| `priority` | `string` | Notification priority |  |
| `type` | `string` | Notification type (e.g., 'task_complete', 'alert', 'info') |  |

#### `notification_list`
List notifications

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `recipient` | `string` | Filter by recipient ID |  |
| `status` | `string` | Filter by read status |  |
| `limit` | `integer` | Maximum number of notifications to return |  |

#### `channel_create`
Create communication channel

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `name` | `string` | Channel name | ✅ |
| `type` | `string` | Channel type |  |
| `participants` | `array` | Initial participants (user/agent IDs) |  |

#### `channel_message`
Send message to channel

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `channel_id` | `string` | Channel ID | ✅ |
| `message` | `string` | Message content | ✅ |
| `attachments` | `array` | Optional message attachments |  |

#### `db_query`
Execute database query

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `query` | `string` | Database query (SQL or query string) | ✅ |
| `database` | `string` | Database name (optional, uses default if not specified) |  |
| `params` | `object` | Query parameters |  |

#### `db_schema`
Get database schema

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `database` | `string` | Database name (optional) |  |
| `table` | `string` | Table name (optional, returns all tables if not specified) |  |

#### `data_transform`
Transform data format

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `data` | `any` | Data to transform | ✅ |
| `from_format` | `string` | Source format (json, csv, xml, yaml, etc.) | ✅ |
| `to_format` | `string` | Target format (json, csv, xml, yaml, etc.) | ✅ |

#### `data_analyze`
Analyze data (statistics, patterns)

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `data` | `any` | Data to analyze | ✅ |
| `analysis_type` | `string` | Type of analysis (statistics, patterns, summary, etc.) |  |
| `options` | `object` | Analysis options |  |

#### `data_export`
Export data to file

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `data` | `any` | Data to export | ✅ |
| `format` | `string` | Export format (json, csv, xml, yaml, etc.) | ✅ |
| `path` | `string` | File path to export to | ✅ |

#### `system_status`
Get system status (CPU, memory, disk)

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `metrics` | `array` | Specific metrics to retrieve (cpu, memory, disk, network, etc.) |  |

#### `log_query`
Query system logs

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `level` | `string` | Filter by log level |  |
| `pattern` | `string` | Search pattern in log messages |  |
| `limit` | `integer` | Maximum number of log entries to return |  |

#### `process_list`
List running processes

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `filter` | `string` | Filter processes by name or pattern |  |

#### `health_check`
Perform health check

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `components` | `array` | Specific components to check (optional, checks all if not specified) |  |

### 📂 Resources

| URI | Name | Description | MIME Type |
|-----|------|-------------|-----------|
| `memory://stats` | Memory Statistics | Current memory statistics for the agent | `application/json` |
| `memory://list` | Memory List | List of all stored memories | `application/json` |
| `search://index` | Search Index Statistics | Search index statistics and health information | `application/json` |
| `knowledge://topics` | Knowledge Topics | Available knowledge topics in the knowledge base | `application/json` |
| `search://history` | Search History | Recent search queries and results | `application/json` |
| `notification://queue` | Notification Queue | Pending notifications queue | `application/json` |
| `channel://list` | Channel List | Available communication channels | `application/json` |
| `db://schemas` | Database Schemas | Available database schemas | `application/json` |
| `data://samples` | Sample Data Sets | Sample data sets for testing and examples | `application/json` |
| `system://metrics` | System Metrics | Real-time system metrics dashboard | `application/json` |
| `log://recent` | Recent Logs | Recent system log entries | `application/json` |

### 📝 Prompts

#### `memory_search`
Search prompt for finding memories

**Arguments:**

- `query` (Required): Search query

#### `memory_summary`
Generate a summary of stored memories

**Arguments:**

- `limit` (Optional): Maximum number of memories to include

#### `search_strategy`
Suggest search strategy for query

**Arguments:**

- `query` (Required): Search query
- `context` (Optional): Optional context for the search

#### `knowledge_synthesis`
Synthesize knowledge from multiple sources

**Arguments:**

- `sources` (Required): List of source identifiers
- `question` (Required): Question to answer

#### `notification_draft`
Draft notification message

**Arguments:**

- `event` (Required): Event that triggered the notification
- `recipient` (Required): Recipient ID
- `context` (Optional): Optional context information

#### `channel_organization`
Suggest channel organization

**Arguments:**

- `topics` (Required): List of topics to organize
- `participants` (Required): List of participants

#### `query_optimization`
Suggest query optimization

**Arguments:**

- `query` (Required): Database query to optimize
- `schema` (Required): Database schema information
- `context` (Optional): Optional context for optimization

#### `diagnostic_analysis`
Analyze system diagnostics

**Arguments:**

- `metrics` (Required): System metrics object
- `logs` (Required): List of log entries
- `symptoms` (Optional): Optional symptoms description

---

## 🤖 Agent: CoordinationAgent (`coordinator`)

### 🛠️ Tools

#### `agent_list`
List all available agents in the network

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `filters` | `object` | Optional filters for agent search |  |

#### `agent_call`
Call another agent's tool or method

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `target` | `string` | Target agent in format 'node_id:agent_id' or 'agent_id' (local) | ✅ |
| `method` | `string` | Tool name or method to call | ✅ |
| `params` | `object` | Parameters for the tool/method |  |

#### `agent_broadcast`
Broadcast message to all agents in a chat room

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `message` | `string` | Message to broadcast | ✅ |
| `room_id` | `string` | Chat room ID (default: 'main') |  |
| `priority` | `string` | Message priority |  |

#### `task_create`
Create a task for agents to work on

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `title` | `string` | Task title | ✅ |
| `description` | `string` | Task description | ✅ |
| `assignee` | `string` | Optional agent ID to assign task to |  |
| `priority` | `integer` | Task priority (1-10, 1 is highest) |  |
| `dependencies` | `array` | List of task IDs this task depends on |  |

#### `task_list`
List all tasks with optional filters

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `status` | `string` | Filter by task status |  |
| `assignee` | `string` | Filter by assignee agent ID |  |
| `limit` | `integer` | Maximum number of tasks to return |  |

#### `network_peers`
List all connected peers/nodes in the network

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `status` | `string` | Filter by connection status |  |
| `node_id` | `string` | Filter by specific node ID |  |

#### `network_info`
Get network statistics and health

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|

#### `node_info`
Get information about a specific node

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `node_id` | `string` | Node ID to get information about | ✅ |

#### `agent_discover`
Discover agents by capability or name

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `capability` | `string` | Capability to search for (tool/resource/prompt name) |  |
| `name_pattern` | `string` | Name pattern to match (supports wildcards) |  |
| `node_id` | `string` | Filter by node ID |  |

### 📂 Resources

| URI | Name | Description | MIME Type |
|-----|------|-------------|-----------|
| `agent://registry` | Agent Registry | Network-wide agent registry with all agents and their capabilities | `application/json` |
| `room://active` | Active Chat Rooms | List of active chat rooms and their participants | `application/json` |
| `task://queue` | Task Queue | Current task queue with status and assignments | `application/json` |
| `network://topology` | Network Topology | Network topology graph showing nodes and connections | `application/json` |
| `network://stats` | Network Statistics | Network-wide statistics and health metrics | `application/json` |

### 📝 Prompts

#### `agent_coordination`
Coordinate multiple agents to accomplish a task

**Arguments:**

- `task` (Required): Task description
- `available_agents` (Required): List of available agent IDs
- `context` (Optional): Optional context information

#### `task_decomposition`
Decompose a complex task into subtasks

**Arguments:**

- `task` (Required): Task to decompose
- `complexity` (Optional): Task complexity level

#### `agent_selection`
Select the best agent(s) for a task

**Arguments:**

- `task` (Required): Task description
- `agent_list` (Required): List of available agent IDs
- `criteria` (Optional): Selection criteria

#### `network_analysis`
Analyze network state and suggest optimizations

**Arguments:**

- `network_data` (Required): Network data to analyze (JSON object)
- `focus` (Optional): Focus area for analysis (optional)

#### `peer_recommendation`
Recommend peers for collaboration based on task

**Arguments:**

- `task` (Required): Task description
- `current_peers` (Required): List of current peer node IDs

---

## 🤖 Agent: CodeAgent (`code`)

### 🛠️ Tools

#### `file_read`
Read file contents

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `path` | `string` | File path (relative to workspace) | ✅ |
| `encoding` | `string` | File encoding |  |

#### `file_write`
Write file contents

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `path` | `string` | File path (relative to workspace) | ✅ |
| `content` | `string` | File content to write | ✅ |
| `encoding` | `string` | File encoding |  |

#### `file_list`
List directory contents

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `path` | `string` | Directory path (relative to workspace) |  |
| `recursive` | `boolean` | List recursively |  |
| `pattern` | `string` | File pattern filter (e.g., '*.py') |  |

#### `file_search`
Search files by content or name

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `query` | `string` | Search query | ✅ |
| `path` | `string` | Base path to search (relative to workspace) |  |
| `type` | `string` | Search type |  |

#### `code_analyze`
Analyze code structure and dependencies

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `path` | `string` | File or directory path to analyze | ✅ |
| `language` | `string` | Programming language (auto-detected if not specified) |  |
| `depth` | `integer` | Analysis depth (1-3) |  |

#### `code_execute`
Execute code in sandboxed environment

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `code` | `string` | Code to execute | ✅ |
| `language` | `string` | Programming language | ✅ |
| `timeout` | `number` | Execution timeout in seconds |  |

#### `code_format`
Format code according to style guide

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `code` | `string` | Code to format | ✅ |
| `language` | `string` | Programming language | ✅ |
| `style` | `string` | Style guide (e.g., 'pep8', 'black', 'prettier') |  |

#### `code_test`
Run tests for code

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `path` | `string` | File or directory path to test | ✅ |
| `test_pattern` | `string` | Test file pattern (e.g., 'test_*.py') |  |
| `framework` | `string` | Test framework (auto-detected if not specified) |  |

### 📂 Resources

| URI | Name | Description | MIME Type |
|-----|------|-------------|-----------|
| `file://tree` | File System Tree | File system tree structure of the workspace | `application/json` |
| `code://dependencies` | Code Dependencies | Code dependencies graph | `application/json` |
| `code://metrics` | Code Metrics | Code quality metrics | `application/json` |
| `file://history` | File History | File change history | `application/json` |

### 📝 Prompts

#### `code_review`
Generate code review

**Arguments:**

- `code` (Required): Code to review
- `language` (Required): Programming language
- `focus` (Optional): Focus area for review (optional)

#### `code_explanation`
Explain code functionality

**Arguments:**

- `code` (Required): Code to explain
- `language` (Required): Programming language
- `detail_level` (Optional): Detail level: simple or detailed

#### `refactoring_suggestion`
Suggest code refactoring

**Arguments:**

- `code` (Required): Code to refactor
- `language` (Required): Programming language
- `goals` (Optional): Refactoring goals (JSON array)

---

