#!/usr/bin/env python3
"""
Project Dawn V2 - Main Server

Serves the frontend and runs the MCP Host.
"""

import asyncio
import logging
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import MCP components
from host import MCPHost
from agents import FirstAgent

# Frontend directory
FRONTEND_DIR = Path(__file__).parent / "frontend"


class FrontendHandler(SimpleHTTPRequestHandler):
    """HTTP handler for serving frontend"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        logger.debug(f"HTTP: {format % args}")


class WebServer:
    """Simple HTTP server for frontend"""
    
    def __init__(self, port=8080):
        self.port = port
        self.server = None
        self.thread = None
    
    def start(self):
        """Start HTTP server in background thread"""
        self.server = HTTPServer(("localhost", self.port), FrontendHandler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"HTTP server started on http://localhost:{self.port}")
    
    def stop(self):
        """Stop HTTP server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("HTTP server stopped")


async def main():
    """Main entry point"""
    logger.info("Starting Project Dawn V2...")
    
    # Create MCP Host
    host = MCPHost("project-dawn-host")
    
    # Create and register first agent
    agent = FirstAgent("agent1", "FirstAgent")
    await host.register_server("agent1", agent.server)
    logger.info(f"Registered agent: {agent.name} with {len(agent.get_tools())} tools")
    
    # Start HTTP server for frontend
    web_server = WebServer(port=8080)
    web_server.start()
    
    # Start MCP Host WebSocket server
    logger.info("Starting MCP Host WebSocket server on ws://localhost:8000")
    logger.info("Frontend available at http://localhost:8080")
    
    try:
        # Start host (blocks until stopped)
        await host.start(host="localhost", port=8000)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        web_server.stop()
        await host.stop()
        logger.info("Project Dawn V2 stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)



