"""Tests for WebSocket transport"""

import asyncio
import socket
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
    server_connected_event = asyncio.Event()
    client_connected_event = asyncio.Event()
    
    async def handle_message(message: str, client_id):
        """Echo message back"""
        received_messages.append((client_id, message))
        return message
    
    async def on_server_connect(client_id):
        server_connected_event.set()
        
    async def on_client_connect():
        client_connected_event.set()

    # Start server with port 0
    server = WebSocketServer(
        message_handler=handle_message,
        on_connect=on_server_connect
    )
    host = "127.0.0.1"
    server_task = asyncio.create_task(server.start(host=host, port=0))
    
    # Wait for server to start and bind port
    await server.wait_started(timeout=2.0)
    # Give a tiny bit of time for internal state to settle
    await asyncio.sleep(0.1)
    
    port = server.bound_port
    assert port is not None, "Server failed to bind to a port"
    
    try:
        # Connect client
        client_received = []
        async def client_handler(message: str):
            client_received.append(message)
            return None
        
        client = WebSocketTransport(
            message_handler=client_handler, 
            on_connect=on_client_connect,
            auto_reconnect=False
        )
        client_task = asyncio.create_task(client.connect(f"ws://{host}:{port}"))
        
        # Wait for both sides to confirm connection
        await asyncio.wait_for(
            asyncio.gather(server_connected_event.wait(), client_connected_event.wait()),
            timeout=2.0
        )
        
        # Send message from client
        test_message = '{"jsonrpc":"2.0","method":"test","params":{},"id":1}'
        await client.send(test_message)
        
        # Wait for message handling (with retry loop instead of fixed sleep)
        for _ in range(10):
            if len(received_messages) >= 1:
                break
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
    
    num_clients = 2
    connections_count = 0
    server_connections_event = asyncio.Event()
    
    async def on_server_connect(client_id):
        nonlocal connections_count
        connections_count += 1
        if connections_count >= num_clients:
            server_connections_event.set()

    server = WebSocketServer(on_connect=on_server_connect)
    host = "127.0.0.1"
    server_task = asyncio.create_task(server.start(host=host, port=0))
    
    # Wait for server to start and bind port
    await server.wait_started(timeout=2.0)
    # Give a tiny bit of time for internal state to settle
    await asyncio.sleep(0.1)
    
    port = server.bound_port
    assert port is not None, "Server failed to bind to a port"
    
    try:
        # Connect multiple clients
        clients = []
        client_received = {0: [], 1: []}
        client_connected_events = [asyncio.Event() for _ in range(num_clients)]
        
        for i in range(num_clients):
            # Capture i in a local scope for the handler
            def make_handlers(idx):
                async def handler(msg):
                    client_received[idx].append(msg)
                async def on_connect():
                    client_connected_events[idx].set()
                return handler, on_connect
            
            msg_handler, conn_handler = make_handlers(i)
            client = WebSocketTransport(
                message_handler=msg_handler,
                on_connect=conn_handler,
                auto_reconnect=False,
            )
            task = asyncio.create_task(client.connect(f"ws://{host}:{port}"))
            clients.append((client, task))
        
        # Wait for all connections to be established on both ends
        await asyncio.wait_for(
            asyncio.gather(
                server_connections_event.wait(),
                *(ev.wait() for ev in client_connected_events)
            ),
            timeout=5.0
        )
        
        # Extra small sleep to ensure internal state is fully settled
        await asyncio.sleep(0.2)
        
        # Broadcast message
        test_message = '{"jsonrpc":"2.0","method":"broadcast","params":{},"id":1}'
        await server.broadcast(test_message)
        
        # Wait for delivery with timeout loop
        for _ in range(20):
            if all(len(client_received[i]) >= 1 for i in range(num_clients)):
                break
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