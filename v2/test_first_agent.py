#!/usr/bin/env python3
"""Test first agent implementation"""

import asyncio
import sys
import json
from agents import FirstAgent
from host import MCPHost, EventType
from mcp.client import MCPClient


async def test_first_agent_creation():
    """Test creating first agent"""
    print("Testing First Agent Creation...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Check agent has tools (4 memory + 5 Phase 4 + 4 Phase 5 + 5 Phase 6 + 4 Phase 7 = 22 total)
    tools = agent.get_tools()
    assert len(tools) == 22, f"Expected 22 tools, got {len(tools)}"
    
    tool_names = [t["name"] for t in tools]
    assert "memory_store" in tool_names, "Should have memory_store tool"
    assert "memory_recall" in tool_names, "Should have memory_recall tool"
    assert "memory_list" in tool_names, "Should have memory_list tool"
    assert "memory_delete" in tool_names, "Should have memory_delete tool"
    
    # Phase 4 tools
    assert "search_text" in tool_names, "Should have search_text tool"
    assert "search_semantic" in tool_names, "Should have search_semantic tool"
    assert "index_content" in tool_names, "Should have index_content tool"
    assert "knowledge_query" in tool_names, "Should have knowledge_query tool"
    assert "web_search" in tool_names, "Should have web_search tool"
    
    # Phase 5 tools
    assert "notification_send" in tool_names, "Should have notification_send tool"
    assert "notification_list" in tool_names, "Should have notification_list tool"
    assert "channel_create" in tool_names, "Should have channel_create tool"
    assert "channel_message" in tool_names, "Should have channel_message tool"
    
    # Phase 6 tools
    assert "db_query" in tool_names, "Should have db_query tool"
    assert "db_schema" in tool_names, "Should have db_schema tool"
    assert "data_transform" in tool_names, "Should have data_transform tool"
    assert "data_analyze" in tool_names, "Should have data_analyze tool"
    assert "data_export" in tool_names, "Should have data_export tool"
    
    # Phase 7 tools
    assert "system_status" in tool_names, "Should have system_status tool"
    assert "log_query" in tool_names, "Should have log_query tool"
    assert "process_list" in tool_names, "Should have process_list tool"
    assert "health_check" in tool_names, "Should have health_check tool"
    
    print("  ✓ Agent created with 22 tools (4 memory + 5 Phase 4 + 4 Phase 5 + 5 Phase 6 + 4 Phase 7)")
    
    return True


async def test_first_agent_memory_tools():
    """Test agent memory tools directly"""
    print("\nTesting Agent Memory Tools...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Test memory_store
    result = await agent._memory_store("Hello, world!", {"source": "test"})
    assert result["success"], "memory_store should succeed"
    memory_id = result["memory_id"]
    print(f"  ✓ memory_store works (ID: {memory_id})")
    
    # Test memory_recall
    result = await agent._memory_recall(memory_id=memory_id)
    assert result["success"], "memory_recall should succeed"
    assert result["memory"]["content"] == "Hello, world!", "Content should match"
    print("  ✓ memory_recall works")
    
    # Test memory_list
    result = await agent._memory_list()
    assert result["success"], "memory_list should succeed"
    assert result["count"] == 1, "Should have 1 memory"
    print("  ✓ memory_list works")
    
    # Test memory_delete
    result = await agent._memory_delete(memory_id)
    assert result["success"], "memory_delete should succeed"
    
    # Verify deleted
    result = await agent._memory_recall(memory_id=memory_id)
    assert not result["success"], "Memory should be deleted"
    print("  ✓ memory_delete works")
    
    return True


async def test_agent_with_host():
    """Test agent registration with host"""
    print("\nTesting Agent with Host...")
    
    # Create agent
    agent = FirstAgent("agent1", "TestAgent")
    
    # Create host
    host = MCPHost("test-host")
    
    # Register agent's server with host
    await host.register_server("agent1", agent.server)
    
    # Verify server is registered
    assert "agent1" in host.list_servers(), "Agent server should be registered"
    print("  ✓ Agent registered with host")
    
    # Check tools are available through host
    server = host.get_server("agent1")
    tools = server.get_tools()
    assert len(tools) == 22, "Should have 22 tools (4 memory + 5 Phase 4 + 4 Phase 5 + 5 Phase 6 + 4 Phase 7)"
    print(f"  ✓ Host has access to agent's {len(tools)} tools")
    
    # Test tool call through server
    # This simulates what would happen when a client calls a tool
    result = await server._handle_tools_call(
        "memory_store",
        {"content": "Test memory", "context": {}}
    )
    
    assert "content" in result, "Should have content in response"
    assert not result.get("isError", False), "Should not be an error"
    print("  ✓ Tool call through host works")
    
    # Unregister
    await host.unregister_server("agent1")
    assert "agent1" not in host.list_servers(), "Agent should be unregistered"
    print("  ✓ Agent unregistration works")
    
    return True


async def test_agent_state():
    """Test agent state"""
    print("\nTesting Agent State...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Get initial state
    state = agent.get_state()
    assert state["agent_id"] == "agent1", "Agent ID should match"
    assert state["name"] == "TestAgent", "Name should match"
    assert state["memory_count"] == 0, "Initial memory count should be 0"
    
    # Store a memory
    await agent._memory_store("Test")
    
    # Get state again
    state = agent.get_state()
    assert state["memory_count"] == 1, "Memory count should be 1"
    print("  ✓ Agent state tracking works")
    
    return True


async def test_phase4_search_tools():
    """Test Phase 4 search and knowledge tools"""
    print("\nTesting Phase 4 Search & Knowledge Tools...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Test index_content
    result = await agent._index_content(
        "Python is a programming language. It is used for web development and data science.",
        metadata={"topic": "programming", "author": "test"},
        type="document"
    )
    assert result["success"], "index_content should succeed"
    index_id = result["index_id"]
    print(f"  ✓ index_content works (ID: {index_id})")
    
    # Test search_text
    result = await agent._search_text("Python programming", limit=5)
    assert result["success"], "search_text should succeed"
    assert result["count"] > 0, "Should find indexed content"
    print(f"  ✓ search_text works (found {result['count']} results)")
    
    # Test search_semantic (use query with more word overlap for better similarity)
    result = await agent._search_semantic("Python programming development", threshold=0.1, limit=5)
    assert result["success"], "search_semantic should succeed"
    assert result["count"] > 0, "Should find semantically similar content"
    print(f"  ✓ search_semantic works (found {result['count']} results)")
    
    # Test knowledge_query
    result = await agent._knowledge_query("programming", filters={"topic": "programming"}, limit=5)
    assert result["success"], "knowledge_query should succeed"
    print(f"  ✓ knowledge_query works (found {result['count']} results)")
    
    # Test web_search (should return not enabled message)
    result = await agent._web_search("Python tutorials", limit=5)
    assert not result["success"], "web_search should return not enabled"
    assert "not enabled" in result["message"].lower(), "Should indicate web search not enabled"
    print("  ✓ web_search works (returns not enabled message)")
    
    return True


async def test_phase4_resources():
    """Test Phase 4 resources"""
    print("\nTesting Phase 4 Resources...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Index some content first
    await agent._index_content("Test content 1", metadata={"topic": "test"}, type="document")
    await agent._index_content("Test content 2", metadata={"topic": "test"}, type="document")
    
    # Test search://index resource
    result_str = await agent._search_index_resource()
    result = json.loads(result_str)
    assert "total_indexed" in result, "Should have total_indexed"
    assert "index_size" in result, "Should have index_size"
    print("  ✓ search://index resource works")
    
    # Test knowledge://topics resource
    result_str = await agent._knowledge_topics_resource()
    result = json.loads(result_str)
    assert "topics" in result, "Should have topics"
    assert "test" in result["topics"], "Should have 'test' topic"
    print("  ✓ knowledge://topics resource works")
    
    # Test search://history resource
    await agent._search_text("test query")
    result_str = await agent._search_history_resource()
    result = json.loads(result_str)
    assert "total_searches" in result, "Should have total_searches"
    assert "recent_searches" in result, "Should have recent_searches"
    assert result["total_searches"] > 0, "Should have search history"
    print("  ✓ search://history resource works")
    
    return True


async def test_phase4_prompts():
    """Test Phase 4 prompts"""
    print("\nTesting Phase 4 Prompts...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Test search_strategy prompt
    result = await agent._search_strategy_prompt("How to use Python?", "Learning programming")
    assert "Search Strategy" in result, "Should contain strategy"
    assert "Python" in result, "Should contain query"
    print("  ✓ search_strategy prompt works")
    
    # Test knowledge_synthesis prompt
    result = await agent._knowledge_synthesis_prompt(
        '["test-topic-1", "test-topic-2"]',
        "What is the best approach?"
    )
    assert "Knowledge Synthesis" in result, "Should contain synthesis"
    assert "best approach" in result, "Should contain question"
    print("  ✓ knowledge_synthesis prompt works")
    
    return True


async def test_phase4_state():
    """Test agent state includes Phase 4 data"""
    print("\nTesting Phase 4 State...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Get initial state
    state = agent.get_state()
    assert "search_index_count" in state, "Should have search_index_count"
    assert "knowledge_base_topics" in state, "Should have knowledge_base_topics"
    assert "search_history_count" in state, "Should have search_history_count"
    
    # Add some data
    await agent._index_content("Test", metadata={"topic": "test"})
    await agent._search_text("test")
    
    # Get state again
    state = agent.get_state()
    assert state["search_index_count"] > 0, "Should have indexed content"
    assert state["knowledge_base_topics"] > 0, "Should have knowledge topics"
    assert state["search_history_count"] > 0, "Should have search history"
    print("  ✓ Phase 4 state tracking works")
    
    return True


async def test_phase5_communication_tools():
    """Test Phase 5 communication and notification tools"""
    print("\nTesting Phase 5 Communication & Notifications Tools...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Test notification_send
    result = await agent._notification_send(
        recipient="user1",
        message="Task completed successfully",
        priority="high",
        type="task_complete"
    )
    assert result["success"], "notification_send should succeed"
    notification_id = result["notification_id"]
    print(f"  ✓ notification_send works (ID: {notification_id})")
    
    # Test notification_list
    result = await agent._notification_list(recipient="user1", status="unread", limit=10)
    assert result["success"], "notification_list should succeed"
    assert result["count"] > 0, "Should find notifications"
    print(f"  ✓ notification_list works (found {result['count']} notifications)")
    
    # Test channel_create
    result = await agent._channel_create(
        name="project-discussion",
        type="public",
        participants=["user1", "user2"]
    )
    assert result["success"], "channel_create should succeed"
    channel_id = result["channel_id"]
    print(f"  ✓ channel_create works (ID: {channel_id})")
    
    # Test channel_message
    result = await agent._channel_message(
        channel_id=channel_id,
        message="Hello, everyone!",
        attachments=[{"type": "file", "name": "document.pdf"}]
    )
    assert result["success"], "channel_message should succeed"
    message_id = result["message_id"]
    print(f"  ✓ channel_message works (ID: {message_id})")
    
    return True


async def test_phase5_resources():
    """Test Phase 5 resources"""
    print("\nTesting Phase 5 Resources...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Create some notifications and channels first
    await agent._notification_send("user1", "Test notification 1", priority="normal")
    await agent._notification_send("user2", "Test notification 2", priority="high")
    await agent._channel_create("test-channel-1", "public", ["user1"])
    await agent._channel_create("test-channel-2", "private", ["user2"])
    
    # Test notification://queue resource
    result_str = await agent._notification_queue_resource()
    result = json.loads(result_str)
    assert "pending_count" in result, "Should have pending_count"
    assert "pending_notifications" in result, "Should have pending_notifications"
    print("  ✓ notification://queue resource works")
    
    # Test channel://list resource
    result_str = await agent._channel_list_resource()
    result = json.loads(result_str)
    assert "total_channels" in result, "Should have total_channels"
    assert "channels" in result, "Should have channels"
    assert result["total_channels"] > 0, "Should have channels"
    print("  ✓ channel://list resource works")
    
    return True


async def test_phase5_prompts():
    """Test Phase 5 prompts"""
    print("\nTesting Phase 5 Prompts...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Test notification_draft prompt
    result = await agent._notification_draft_prompt(
        event="Task completed",
        recipient="user1",
        context="The build process finished successfully"
    )
    assert "Notification Draft" in result, "Should contain draft"
    assert "Task completed" in result, "Should contain event"
    print("  ✓ notification_draft prompt works")
    
    # Test channel_organization prompt
    result = await agent._channel_organization_prompt(
        topics='["development", "testing", "deployment"]',
        participants='["user1", "user2", "user3"]'
    )
    assert "Channel Organization" in result, "Should contain organization"
    assert "development" in result, "Should contain topics"
    print("  ✓ channel_organization prompt works")
    
    return True


async def test_phase5_state():
    """Test agent state includes Phase 5 data"""
    print("\nTesting Phase 5 State...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Get initial state
    state = agent.get_state()
    assert "notifications_count" in state, "Should have notifications_count"
    assert "channels_count" in state, "Should have channels_count"
    
    # Add some data
    await agent._notification_send("user1", "Test")
    await agent._channel_create("test-channel")
    
    # Get state again
    state = agent.get_state()
    assert state["notifications_count"] > 0, "Should have notifications"
    assert state["channels_count"] > 0, "Should have channels"
    print("  ✓ Phase 5 state tracking works")
    
    return True


async def test_phase6_data_tools():
    """Test Phase 6 data and database tools"""
    print("\nTesting Phase 6 Data & Database Tools...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Test db_query - create table
    result = await agent._db_query("CREATE TABLE users", database="test_db")
    assert result["success"], "db_query CREATE TABLE should succeed"
    print("  ✓ db_query CREATE TABLE works")
    
    # Test db_query - insert
    result = await agent._db_query(
        "INSERT INTO users",
        database="test_db",
        params={"name": "Test User", "email": "test@example.com"}
    )
    assert result["success"], "db_query INSERT should succeed"
    print("  ✓ db_query INSERT works")
    
    # Test db_query - select
    result = await agent._db_query("SELECT * FROM users", database="test_db")
    assert result["success"], "db_query SELECT should succeed"
    print("  ✓ db_query SELECT works")
    
    # Test db_schema
    result = await agent._db_schema(database="test_db", table="users")
    assert result["success"], "db_schema should succeed"
    print("  ✓ db_schema works")
    
    # Test data_transform
    test_data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    result = await agent._data_transform(
        json.dumps(test_data),
        from_format="json",
        to_format="csv"
    )
    assert result["success"], "data_transform should succeed"
    assert "csv" in result["data"].lower() or "," in result["data"], "Should produce CSV"
    print("  ✓ data_transform works")
    
    # Test data_analyze
    result = await agent._data_analyze(test_data, analysis_type="statistics")
    assert result["success"], "data_analyze should succeed"
    assert "analysis" in result, "Should have analysis results"
    print("  ✓ data_analyze works")
    
    # Test data_export
    result = await agent._data_export(test_data, format="json", path="/tmp/test_export.json")
    assert result["success"], "data_export should succeed"
    print("  ✓ data_export works")
    
    return True


async def test_phase6_resources():
    """Test Phase 6 resources"""
    print("\nTesting Phase 6 Resources...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Create some database structure first
    await agent._db_query("CREATE TABLE test_table", database="test_db")
    
    # Test db://schemas resource
    result_str = await agent._db_schemas_resource()
    result = json.loads(result_str)
    assert "total_databases" in result, "Should have total_databases"
    assert "databases" in result, "Should have databases"
    print("  ✓ db://schemas resource works")
    
    # Test data://samples resource
    result_str = await agent._data_samples_resource()
    result = json.loads(result_str)
    assert "sample_datasets" in result, "Should have sample_datasets"
    assert "data" in result, "Should have data"
    print("  ✓ data://samples resource works")
    
    return True


async def test_phase6_prompts():
    """Test Phase 6 prompts"""
    print("\nTesting Phase 6 Prompts...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Test query_optimization prompt
    schema = {
        "tables": {
            "users": {
                "columns": ["id", "name", "email"],
                "indexes": ["id"]
            }
        }
    }
    result = await agent._query_optimization_prompt(
        query="SELECT * FROM users WHERE name LIKE '%test%'",
        schema=json.dumps(schema),
        context="High traffic query"
    )
    assert "Query Optimization" in result, "Should contain optimization"
    assert "SELECT *" in result, "Should contain query"
    print("  ✓ query_optimization prompt works")
    
    return True


async def test_phase6_state():
    """Test agent state includes Phase 6 data"""
    print("\nTesting Phase 6 State...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Get initial state
    state = agent.get_state()
    assert "databases_count" in state, "Should have databases_count"
    
    # Add some data
    await agent._db_query("CREATE TABLE test", database="test_db")
    
    # Get state again
    state = agent.get_state()
    assert state["databases_count"] > 0, "Should have databases"
    print("  ✓ Phase 6 state tracking works")
    
    return True


async def test_phase7_system_tools():
    """Test Phase 7 system and monitoring tools"""
    print("\nTesting Phase 7 System & Monitoring Tools...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Test system_status
    result = await agent._system_status(metrics=["cpu", "memory"])
    assert result["success"], "system_status should succeed"
    assert "metrics" in result, "Should have metrics"
    print("  ✓ system_status works")
    
    # Test log_query
    result = await agent._log_query(level="INFO", limit=10)
    assert result["success"], "log_query should succeed"
    assert "logs" in result, "Should have logs"
    print("  ✓ log_query works")
    
    # Test process_list
    result = await agent._process_list(filter="python")
    assert result["success"], "process_list should succeed"
    assert "processes" in result, "Should have processes"
    print("  ✓ process_list works")
    
    # Test health_check
    result = await agent._health_check(components=["system", "agent"])
    assert result["success"], "health_check should succeed"
    assert "health" in result, "Should have health status"
    assert result["health"]["overall"] in ["healthy", "degraded", "unhealthy"], "Should have valid status"
    print("  ✓ health_check works")
    
    return True


async def test_phase7_resources():
    """Test Phase 7 resources"""
    print("\nTesting Phase 7 Resources...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Generate some metrics and logs first
    await agent._system_status()
    await agent._log_query()
    
    # Test system://metrics resource
    result_str = await agent._system_metrics_resource()
    result = json.loads(result_str)
    assert "current" in result, "Should have current metrics"
    assert "recent_history" in result, "Should have recent history"
    print("  ✓ system://metrics resource works")
    
    # Test log://recent resource
    result_str = await agent._log_recent_resource()
    result = json.loads(result_str)
    assert "total_logs" in result, "Should have total_logs"
    assert "recent_logs" in result, "Should have recent_logs"
    print("  ✓ log://recent resource works")
    
    return True


async def test_phase7_prompts():
    """Test Phase 7 prompts"""
    print("\nTesting Phase 7 Prompts...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Test diagnostic_analysis prompt
    metrics = {"cpu": {"percent": 75.0}, "memory": {"percent": 60.0}}
    logs = [
        {"level": "INFO", "message": "System running normally"},
        {"level": "ERROR", "message": "Connection failed"}
    ]
    result = await agent._diagnostic_analysis_prompt(
        metrics=json.dumps(metrics),
        logs=json.dumps(logs),
        symptoms="High CPU usage reported"
    )
    assert "System Diagnostic" in result, "Should contain diagnostic"
    assert "High CPU Usage" in result or "CPU" in result, "Should analyze CPU"
    print("  ✓ diagnostic_analysis prompt works")
    
    return True


async def test_phase7_state():
    """Test agent state includes Phase 7 data"""
    print("\nTesting Phase 7 State...")
    
    agent = FirstAgent("agent1", "TestAgent")
    
    # Get initial state
    state = agent.get_state()
    assert "system_logs_count" in state, "Should have system_logs_count"
    assert "metrics_history_count" in state, "Should have metrics_history_count"
    
    # Add some data
    await agent._system_status()
    await agent._log_query()
    
    # Get state again
    state = agent.get_state()
    assert state["system_logs_count"] > 0, "Should have system logs"
    assert state["metrics_history_count"] > 0, "Should have metrics history"
    print("  ✓ Phase 7 state tracking works")
    
    return True


async def main():
    """Run all tests"""
    print("Running First Agent Tests\n")
    print("=" * 50)
    
    try:
        await test_first_agent_creation()
        await test_first_agent_memory_tools()
        await test_agent_with_host()
        await test_agent_state()
        
        # Phase 4 tests
        await test_phase4_search_tools()
        await test_phase4_resources()
        await test_phase4_prompts()
        await test_phase4_state()
        
        # Phase 5 tests
        await test_phase5_communication_tools()
        await test_phase5_resources()
        await test_phase5_prompts()
        await test_phase5_state()
        
        # Phase 6 tests
        await test_phase6_data_tools()
        await test_phase6_resources()
        await test_phase6_prompts()
        await test_phase6_state()
        
        # Phase 7 tests
        await test_phase7_system_tools()
        await test_phase7_resources()
        await test_phase7_prompts()
        await test_phase7_state()
        
        print("\n" + "=" * 50)
        print("✓ All First Agent tests passed (including Phases 4, 5, 6 & 7)!")
        return 0
    
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))



