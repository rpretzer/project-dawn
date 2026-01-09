"""
MCP Transport Layer

WebSocket transport implementation for MCP protocol.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Callable, Awaitable
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import websockets, gracefully handle if not available
try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    from websockets.client import WebSocketClientProtocol
    try:
        from websockets.asyncio.server import ServerConnection
        WEBSOCKETS_NEW_API = True
    except ImportError:
        WEBSOCKETS_NEW_API = False
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WEBSOCKETS_NEW_API = False
    logger.warning("websockets library not available. WebSocket transport disabled.")


class TransportType(Enum):
    """Transport types"""
    WEBSOCKET = "websocket"
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class ConnectionState(Enum):
    """Connection state"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


class WebSocketTransport:
    """
    WebSocket transport for MCP protocol
    
    Handles WebSocket connections and message routing.
    """
    
    def __init__(
        self,
        message_handler: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
        on_connect: Optional[Callable[[], Awaitable[None]]] = None,
        on_disconnect: Optional[Callable[[], Awaitable[None]]] = None,
        on_error: Optional[Callable[[Exception], Awaitable[None]]] = None,
    ):
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("websockets library not available")
        
        self.message_handler = message_handler
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_error = on_error
        
        self.state = ConnectionState.DISCONNECTED
        self.websocket: Optional[WebSocketServerProtocol] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._reconnect_delay = 5.0  # seconds
        self._max_reconnect_attempts = 5
        self._reconnect_attempts = 0
    
    @property
    def is_connected(self) -> bool:
        """Check if connected"""
        return self.state == ConnectionState.CONNECTED and self.websocket is not None
    
    async def connect(self, uri: str, **kwargs) -> None:
        """
        Connect to WebSocket server (client mode)
        
        Args:
            uri: WebSocket URI (e.g., ws://localhost:8000)
            **kwargs: Additional connection arguments
        """
        if self.state == ConnectionState.CONNECTED:
            logger.warning("Already connected")
            return
        
        self.state = ConnectionState.CONNECTING
        logger.info(f"Connecting to {uri}...")
        
        try:
            async with websockets.connect(uri, **kwargs) as ws:
                self.websocket = ws
                self.state = ConnectionState.CONNECTED
                self._reconnect_attempts = 0
                logger.info(f"Connected to {uri}")
                
                if self.on_connect:
                    await self.on_connect()
                
                # Start receiving messages
                await self._receive_loop()
        
        except asyncio.CancelledError:
            logger.info("Connection cancelled")
            self.state = ConnectionState.DISCONNECTED
        
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.state = ConnectionState.ERROR
            
            if self.on_error:
                await self.on_error(e)
            
            # Attempt reconnection if handler is set
            if self.message_handler and self._reconnect_attempts < self._max_reconnect_attempts:
                await self._reconnect(uri, **kwargs)
            else:
                self.state = ConnectionState.DISCONNECTED
                if self.on_disconnect:
                    await self.on_disconnect()
    
    async def _reconnect(self, uri: str, **kwargs) -> None:
        """Attempt to reconnect"""
        self._reconnect_attempts += 1
        delay = self._reconnect_delay * self._reconnect_attempts
        logger.info(f"Reconnecting in {delay} seconds (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})...")
        await asyncio.sleep(delay)
        await self.connect(uri, **kwargs)
    
    async def _receive_loop(self) -> None:
        """Receive messages from WebSocket"""
        try:
            async for message in self.websocket:
                if isinstance(message, str):
                    await self._handle_message(message)
                elif isinstance(message, bytes):
                    # Try to decode as UTF-8
                    try:
                        text_message = message.decode('utf-8')
                        await self._handle_message(text_message)
                    except UnicodeDecodeError:
                        logger.error(f"Failed to decode message: {message}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.state = ConnectionState.DISCONNECTED
            if self.on_disconnect:
                await self.on_disconnect()
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
            self.state = ConnectionState.ERROR
            if self.on_error:
                await self.on_error(e)
    
    async def _handle_message(self, message: str) -> None:
        """Handle incoming message"""
        if self.message_handler:
            try:
                response = await self.message_handler(message)
                if response:
                    await self.send(response)
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)
                if self.on_error:
                    await self.on_error(e)
    
    async def send(self, message: str) -> None:
        """
        Send message through WebSocket
        
        Args:
            message: JSON-RPC message as string
        """
        if not self.is_connected:
            raise RuntimeError("Not connected")
        
        try:
            await self.websocket.send(message)
            logger.debug(f"Sent message: {message[:100]}...")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection closed while sending")
            self.state = ConnectionState.DISCONNECTED
            if self.on_disconnect:
                await self.on_disconnect()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            if self.on_error:
                await self.on_error(e)
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket"""
        if self.state == ConnectionState.DISCONNECTED:
            return
        
        self.state = ConnectionState.DISCONNECTING
        logger.info("Disconnecting...")
        
        # Cancel receive task
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        # Close WebSocket
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        
        self.state = ConnectionState.DISCONNECTED
        self.websocket = None
        
        if self.on_disconnect:
            await self.on_disconnect()
    
    async def serve(
        self,
        host: str = "localhost",
        port: int = 8000,
        **kwargs
    ) -> None:
        """
        Start WebSocket server (single client mode)
        
        Args:
            host: Server host
            port: Server port
            **kwargs: Additional server arguments
        """
        logger.info(f"Starting WebSocket server on {host}:{port}")
        
        async def handle_client(websocket: WebSocketServerProtocol, path: str):
            """Handle client connection"""
            logger.info(f"Client connected from {websocket.remote_address}")
            self.websocket = websocket
            self.state = ConnectionState.CONNECTED
            
            if self.on_connect:
                await self.on_connect()
            
            try:
                async for message in websocket:
                    if isinstance(message, str):
                        await self._handle_message(message)
                    elif isinstance(message, bytes):
                        try:
                            text_message = message.decode('utf-8')
                            await self._handle_message(text_message)
                        except UnicodeDecodeError:
                            logger.error(f"Failed to decode message: {message}")
            
            except websockets.exceptions.ConnectionClosed:
                logger.info("Client disconnected")
            except Exception as e:
                logger.error(f"Error handling client: {e}", exc_info=True)
                if self.on_error:
                    await self.on_error(e)
            finally:
                self.state = ConnectionState.DISCONNECTED
                self.websocket = None
                if self.on_disconnect:
                    await self.on_disconnect()
        
        async with websockets.serve(handle_client, host, port, **kwargs):
            logger.info(f"WebSocket server running on ws://{host}:{port}")
            # Keep server running
            await asyncio.Future()  # Run forever


class WebSocketServer:
    """
    WebSocket server for MCP protocol
    
    Manages multiple client connections.
    """
    
    def __init__(
        self,
        message_handler: Optional[Callable[[str, Any], Awaitable[Optional[str]]]] = None,
        on_connect: Optional[Callable[[Any], Awaitable[None]]] = None,
        on_disconnect: Optional[Callable[[Any], Awaitable[None]]] = None,
    ):
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("websockets library not available")
        
        self.message_handler = message_handler
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        
        self.clients: Dict[Any, WebSocketServerProtocol] = {}
        self.server = None
    
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle client connection"""
        client_id = id(websocket)
        self.clients[client_id] = websocket
        logger.info(f"Client {client_id} connected from {websocket.remote_address}")
        
        if self.on_connect:
            await self.on_connect(client_id)
        
        try:
            async for message in websocket:
                if isinstance(message, str):
                    if self.message_handler:
                        response = await self.message_handler(message, client_id)
                        if response:
                            await websocket.send(response)
                elif isinstance(message, bytes):
                    try:
                        text_message = message.decode('utf-8')
                        if self.message_handler:
                            response = await self.message_handler(text_message, client_id)
                            if response:
                                await websocket.send(response)
                    except UnicodeDecodeError:
                        logger.error(f"Failed to decode message: {message}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}", exc_info=True)
        finally:
            if client_id in self.clients:
                del self.clients[client_id]
            if self.on_disconnect:
                await self.on_disconnect(client_id)
    
    async def broadcast(self, message: str) -> None:
        """Broadcast message to all connected clients"""
        disconnected = []
        for client_id, websocket in self.clients.items():
            try:
                await websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(client_id)
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
        
        # Remove disconnected clients
        for client_id in disconnected:
            if client_id in self.clients:
                del self.clients[client_id]
    
    async def send_to_client(self, client_id: Any, message: str) -> None:
        """Send message to specific client"""
        if client_id not in self.clients:
            logger.warning(f"Client {client_id} not found")
            return
        
        try:
            await self.clients[client_id].send(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"Client {client_id} disconnected")
            del self.clients[client_id]
        except Exception as e:
            logger.error(f"Error sending to client {client_id}: {e}")
    
    async def start(
        self,
        host: str = "localhost",
        port: int = 8000,
        **kwargs
    ) -> None:
        """
        Start WebSocket server
        
        Args:
            host: Server host
            port: Server port
            **kwargs: Additional server arguments
        """
        logger.info(f"Starting WebSocket server on {host}:{port}")
        
        if WEBSOCKETS_NEW_API:
            # New API (websockets 15.0+): handler receives ServerConnection
            # ServerConnection is compatible with WebSocketServerProtocol
            async def handler(connection):
                """Handler wrapper for new API"""
                # ServerConnection is compatible with WebSocketServerProtocol
                # Path is not directly available in new API, use default
                websocket = connection
                path = '/'  # Path not available in new API
                await self.handle_client(websocket, path)
        else:
            # Old API: handler receives (websocket, path)
            async def handler(websocket: WebSocketServerProtocol, path: str = "/"):
                """Handler wrapper for old API"""
                await self.handle_client(websocket, path)
        
        async with websockets.serve(handler, host, port, **kwargs):
            logger.info(f"WebSocket server running on ws://{host}:{port}")
            # Keep server running
            await asyncio.Future()  # Run forever
    
    async def stop(self) -> None:
        """Stop WebSocket server"""
        # Close all client connections
        for client_id, websocket in list(self.clients.items()):
            try:
                await websocket.close()
            except Exception:
                pass
        
        self.clients.clear()
        logger.info("WebSocket server stopped")

