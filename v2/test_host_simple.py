#!/usr/bin/env python3
"""Simple test runner for MCP Host (no pytest required)"""

import asyncio
import sys
from host import MCPHost, EventBus, Event, EventType
from mcp.server import MCPServer
from mcp.transport import WEBSOCKETS_AVAILABLE


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
    
    assert len(received_events) == 1, f"Expected 1 event, got {len(received_events)}"
    assert received_events[0].type == EventType.CONNECTION, "Event type should be CONNECTION"
    assert received_events[0].data["key"] == "value", "Event data should match"
    print("  ✓ Event bus pub/sub works")
    
    return True


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
    
    assert len(received_events) == 2, f"Expected 2 events, got {len(received_events)}"
    print("  ✓ All-event subscription works")
    
    return True


async def test_host_server_registration():
    """Test host server registration"""
    if not WEBSOCKETS_AVAILABLE:
        print("  ⚠ websockets library not available - skipping")
        return True
    
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
    assert "server1" in host.list_servers(), "Server should be in list"
    assert host.get_server("server1") == server, "Should return same server"
    print("  ✓ Server registration works")
    
    # Unregister
    await host.unregister_server("server1")
    assert "server1" not in host.list_servers(), "Server should be removed"
    print("  ✓ Server unregistration works")
    
    return True


async def test_host_event_bus():
    """Test host event bus integration"""
    if not WEBSOCKETS_AVAILABLE:
        print("  ⚠ websockets library not available - skipping")
        return True
    
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
    
    assert len(received_events) > 0, "Should have received events"
    state_events = [e for e in received_events if e.type == EventType.STATE_CHANGED]
    assert len(state_events) > 0, "Should have state change events"
    print("  ✓ Host event bus integration works")
    
    # Get events from log
    events = host.event_bus.get_events(EventType.STATE_CHANGED)
    assert len(events) > 0, "Should have events in log"
    print("  ✓ Event log works")
    
    return True


async def main():
    """Run all tests"""
    print("Running MCP Host Tests\n")
    print("=" * 50)
    
    try:
        await test_event_bus()
        await test_event_bus_all_subscribers()
        await test_host_server_registration()
        await test_host_event_bus()
        
        print("\n" + "=" * 50)
        print("✓ All MCP Host tests passed!")
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



