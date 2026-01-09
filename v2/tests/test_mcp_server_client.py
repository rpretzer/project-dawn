"""Tests for MCP Server and Client"""

import asyncio
import pytest
from mcp.server import MCPServer
from mcp.client import MCPClient
from mcp.tools import MCPTool
from mcp.transport import WEBSOCKETS_AVAILABLE


@pytest.mark.asyncio
async def test_mcp_server_tool_registration():
    """Test MCP server tool registration"""
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
    assert server.has_tool("echo")
    tools = server.get_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "echo"
    print("✓ Tool registration works")


@pytest.mark.asyncio
async def test_mcp_server_tools_list():
    """Test tools/list method"""
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
    assert "tools" in response
    assert len(response["tools"]) == 1
    assert response["tools"][0]["name"] == "add"
    print("✓ tools/list works")


@pytest.mark.asyncio
async def test_mcp_server_tools_call():
    """Test tools/call method"""
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
    assert "content" in response
    assert not response.get("isError", False)
    assert "12" in str(response["content"])
    print("✓ tools/call works")


@pytest.mark.asyncio
async def test_mcp_server_message_handling():
    """Test full message handling"""
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
    
    assert response is not None
    assert '"result"' in response
    assert '"tools"' in response
    print("✓ Message handling works")


@pytest.mark.asyncio
async def test_mcp_client_discover_tools():
    """Test MCP client tool discovery (requires server)"""
    if not WEBSOCKETS_AVAILABLE:
        pytest.skip("websockets library not available")
    
    # This test would require a running server
    # For now, just test that client can be created
    client = MCPClient("test-client")
    assert client.name == "test-client"
    assert not client.is_connected
    print("✓ Client creation works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



