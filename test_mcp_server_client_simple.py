#!/usr/bin/env python3
"""Simple test runner for MCP Server/Client (no pytest required)"""

import asyncio
import sys
from mcp.server import MCPServer
from mcp.client import MCPClient
from mcp.tools import MCPTool


async def test_server_tool_registration():
    """Test server tool registration"""
    print("Testing MCP Server Tool Registration...")
    
    server = MCPServer("test-server")
    
    # Register a simple tool
    async def echo(text: str) -> str:
        return text
    
    server.register_function(
        name="echo",
        description="Echo a message",
        handler=echo,
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string"}
            },
            "required": ["text"]
        }
    )
    
    # Check tool is registered
    assert server.has_tool("echo"), "Tool should be registered"
    tools = server.get_tools()
    assert len(tools) == 1, f"Expected 1 tool, got {len(tools)}"
    assert tools[0]["name"] == "echo", "Tool name should be 'echo'"
    print("  ✓ Tool registration")
    
    return True


async def test_server_tools_list():
    """Test tools/list method"""
    print("\nTesting tools/list...")
    
    server = MCPServer("test-server")
    
    async def add(a: int, b: int) -> int:
        return a + b
    
    server.register_function(
        name="add",
        description="Add two numbers",
        handler=add,
        inputSchema={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"}
            },
            "required": ["a", "b"]
        }
    )
    
    # Call tools/list
    response = await server._handle_tools_list()
    assert "tools" in response, "Response should have 'tools' key"
    assert len(response["tools"]) == 1, "Should have 1 tool"
    assert response["tools"][0]["name"] == "add", "Tool name should be 'add'"
    print("  ✓ tools/list method")
    
    return True


async def test_server_tools_call():
    """Test tools/call method"""
    print("\nTesting tools/call...")
    
    server = MCPServer("test-server")
    
    async def multiply(a: int, b: int) -> int:
        return a * b
    
    server.register_function(
        name="multiply",
        description="Multiply two numbers",
        handler=multiply,
        inputSchema={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"}
            },
            "required": ["a", "b"]
        }
    )
    
    # Call tool
    response = await server._handle_tools_call("multiply", {"a": 3, "b": 4})
    assert "content" in response, "Response should have 'content' key"
    assert not response.get("isError", False), "Should not be an error"
    assert "12" in str(response["content"]), "Result should contain '12'"
    print("  ✓ tools/call method")
    
    return True


async def test_server_message_handling():
    """Test full message handling"""
    print("\nTesting Message Handling...")
    
    server = MCPServer("test-server")
    
    async def greet(name: str) -> str:
        return f"Hello, {name}!"
    
    server.register_function(
        name="greet",
        description="Greet someone",
        handler=greet,
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    )
    
    # Send tools/list request
    request = '{"jsonrpc":"2.0","method":"tools/list","id":1}'
    response = await server.handle_message(request)
    
    assert response is not None, "Should have response"
    assert '"result"' in response, "Should have result"
    assert '"tools"' in response, "Should have tools"
    print("  ✓ Full message handling")
    
    # Test tools/call
    request = '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"greet","arguments":{"name":"World"}},"id":2}'
    response = await server.handle_message(request)
    
    assert response is not None, "Should have response"
    assert '"result"' in response, "Should have result"
    assert "Hello" in response, "Should contain greeting"
    print("  ✓ tools/call via message")
    
    return True


async def test_client_creation():
    """Test client creation"""
    print("\nTesting MCP Client Creation...")
    
    client = MCPClient("test-client")
    assert client.name == "test-client", "Client name should match"
    assert not client.is_connected, "Should not be connected initially"
    print("  ✓ Client creation")
    
    return True


async def main():
    """Run all tests"""
    print("Running MCP Server/Client Tests\n")
    print("=" * 50)
    
    try:
        await test_server_tool_registration()
        await test_server_tools_list()
        await test_server_tools_call()
        await test_server_message_handling()
        await test_client_creation()
        
        print("\n" + "=" * 50)
        print("✓ All MCP Server/Client tests passed!")
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



