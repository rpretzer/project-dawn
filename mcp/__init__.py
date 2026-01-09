"""
Model Context Protocol (MCP) Implementation

Official spec: https://modelcontextprotocol.io
"""

__version__ = "0.1.0"

from .protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    JSONRPCHandler,
)

from .transport import (
    WebSocketTransport,
    WebSocketServer,
    ConnectionState,
    TransportType,
    WEBSOCKETS_AVAILABLE,
)

from .tools import (
    MCPTool,
    ToolRegistry,
)

from .server import MCPServer

from .client import MCPClient

__all__ = [
    # Protocol
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
    "JSONRPCHandler",
    # Transport
    "WebSocketTransport",
    "WebSocketServer",
    "ConnectionState",
    "TransportType",
    "WEBSOCKETS_AVAILABLE",
    # Tools
    "MCPTool",
    "ToolRegistry",
    # Server
    "MCPServer",
    # Client
    "MCPClient",
]
