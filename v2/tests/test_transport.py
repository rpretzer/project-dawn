"""Tests for WebSocket transport"""

import asyncio
import pytest
from mcp.transport import (
    WebSocketTransport,
    WebSocketServer,
    ConnectionState,
    WEBSOCKETS_AVAILABLE,
)


@pytest.mark.asyncio
async def test_websocket_server_client():
    """Test WebSocket server and client communication"""
    if not WEBSOCKETS_AVAILABLE:
        pytest.skip("websockets library not available")
    
    received_messages = []
    
    async def handle_message(message: str, client_id):
        """Echo message back"""
        received_messages.append((client_id, message))
        return message
    
    # Start server
    server = WebSocketServer(message_handler=handle_message)
    server_task = asyncio.create_task(server.start(host="localhost", port=8765))
    
    # Wait for server to start
    await asyncio.sleep(0.1)
    
    try:
        # Connect client
        client_received = []
        
        async def client_handler(message: str):
            client_received.append(message)
            return None
        
        client = WebSocketTransport(message_handler=client_handler)
        client_task = asyncio.create_task(client.connect("ws://localhost:8765"))
        
        # Wait for connection
        await asyncio.sleep(0.1)
        
        # Send message from client
        test_message = '{"jsonrpc":"2.0","method":"test","params":{},"id":1}'
        await client.send(test_message)
        
        # Wait for message handling
        await asyncio.sleep(0.1)
        
        # Check that server received message
        assert len(received_messages) == 1
        assert received_messages[0][1] == test_message
        
        # Disconnect
        await client.disconnect()
        client_task.cancel()
        
    finally:
        await server.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_websocket_connection_state():
    """Test connection state management"""
    if not WEBSOCKETS_AVAILABLE:
        pytest.skip("websockets library not available")
    
    client = WebSocketTransport()
    
    # Initially disconnected
    assert client.state == ConnectionState.DISCONNECTED
    assert not client.is_connected
    
    # Try to send without connection should raise
    try:
        await client.send("test")
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass


@pytest.mark.asyncio
async def test_websocket_broadcast():
    """Test broadcasting to multiple clients"""
    if not WEBSOCKETS_AVAILABLE:
        pytest.skip("websockets library not available")
    
    server = WebSocketServer()
    server_task = asyncio.create_task(server.start(host="localhost", port=8766))
    await asyncio.sleep(0.1)
    
    try:
        # Connect multiple clients
        clients = []
        client_received = {0: [], 1: []}
        
        for i in range(2):
            async def make_handler(idx):
                async def handler(msg):
                    client_received[idx].append(msg)
                    return None
                return handler
            
            client = WebSocketTransport(message_handler=await make_handler(i))
            task = asyncio.create_task(client.connect(f"ws://localhost:8766"))
            clients.append((client, task))
            await asyncio.sleep(0.1)
        
        # Wait for connections
        await asyncio.sleep(0.2)
        
        # Broadcast message
        test_message = '{"jsonrpc":"2.0","method":"broadcast","params":{},"id":1}'
        await server.broadcast(test_message)
        
        # Wait for delivery
        await asyncio.sleep(0.1)
        
        # Check that all clients received message
        assert len(client_received[0]) == 1
        assert len(client_received[1]) == 1
        
        # Disconnect
        for client, task in clients:
            await client.disconnect()
            task.cancel()
        
    finally:
        await server.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass



