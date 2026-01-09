"""Tests for MCP Host"""

import asyncio
import pytest
from host import MCPHost, EventBus, Event, EventType
from mcp.server import MCPServer
from mcp.client import MCPClient
from mcp.transport import WEBSOCKETS_AVAILABLE


@pytest.mark.asyncio
async def test_event_bus():
    """Test event bus"""
    print("Testing Event Bus...")
    
    bus = EventBus()
    received_events = []
    
    async def handler(event: Event):
        received_events.append(event)
    
    # Subscribe to connection events
    bus.subscribe(EventType.CONNECTION, handler)
    
    # Publish event
    event = await bus.publish_event(
        EventType.CONNECTION,
        source="test",
        data={"key": "value"},
    )
    
    # Wait for handlers
    await asyncio.sleep(0.1)
    
    assert len(received_events) == 1
    assert received_events[0].type == EventType.CONNECTION
    assert received_events[0].data["key"] == "value"
    print("  ✓ Event bus pub/sub works")


@pytest.mark.asyncio
async def test_event_bus_all_subscribers():
    """Test subscribing to all events"""
    print("\nTesting Event Bus (all subscribers)...")
    
    bus = EventBus()
    received_events = []
    
    async def handler(event: Event):
        received_events.append(event)
    
    # Subscribe to all events
    bus.subscribe_all(handler)
    
    # Publish different event types
    await bus.publish_event(EventType.CONNECTION, "test", {"a": 1})
    await bus.publish_event(EventType.DISCONNECTION, "test", {"b": 2})
    
    # Wait for handlers
    await asyncio.sleep(0.1)
    
    assert len(received_events) == 2
    print("  ✓ All-event subscription works")


@pytest.mark.asyncio
async def test_host_server_registration():
    """Test host server registration"""
    if not WEBSOCKETS_AVAILABLE:
        pytest.skip("websockets library not available")
    
    print("\nTesting MCP Host Server Registration...")
    
    host = MCPHost("test-host")
    
    # Create and register server
    server = MCPServer("test-server")
    
    async def echo(text: str) -> str:
        return text
    
    server.register_function(
        name="echo",
        description="Echo message",
        handler=echo,
        inputSchema={"type": "object", "properties": {"text": {"type": "string"}}}
    )
    
    await host.register_server("server1", server)
    
    # Check server is registered
    assert "server1" in host.list_servers()
    assert host.get_server("server1") == server
    print("  ✓ Server registration works")
    
    # Unregister
    await host.unregister_server("server1")
    assert "server1" not in host.list_servers()
    print("  ✓ Server unregistration works")


@pytest.mark.asyncio
async def test_host_event_bus():
    """Test host event bus integration"""
    if not WEBSOCKETS_AVAILABLE:
        pytest.skip("websockets library not available")
    
    print("\nTesting MCP Host Event Bus...")
    
    host = MCPHost("test-host")
    received_events = []
    
    async def handler(event: Event):
        received_events.append(event)
    
    # Subscribe to state changes
    host.event_bus.subscribe(EventType.STATE_CHANGED, handler)
    
    # Register server (should trigger event)
    server = MCPServer("test-server")
    await host.register_server("server1", server)
    
    # Wait for event
    await asyncio.sleep(0.1)
    
    assert len(received_events) > 0
    state_events = [e for e in received_events if e.type == EventType.STATE_CHANGED]
    assert len(state_events) > 0
    print("  ✓ Host event bus integration works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



