#!/usr/bin/env python3
"""
Project Dawn V2 - P2P Node Server

Serves the frontend and runs a P2P node (decentralized).
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

# Import P2P components
from crypto import NodeIdentity
from p2p import P2PNode
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
    logger.info("Starting Project Dawn V2 (P2P Mode)...")
    
    # Create node identity
    identity = NodeIdentity()
    logger.info(f"Node ID: {identity.get_node_id()[:16]}...")
    
    # Create P2P node
    node = P2PNode(
        identity=identity,
        address="ws://localhost:8000",
        bootstrap_nodes=None,  # No bootstrap nodes for single-node setup
        enable_encryption=False,  # Disabled for frontend compatibility
        enable_privacy=False,  # Privacy features disabled by default (optional)
    )
    
    # Create and register first agent
    agent = FirstAgent("agent1", "FirstAgent")
    node.register_agent("agent1", agent.server)
    logger.info(f"Registered agent: {agent.name} with {len(agent.get_tools())} tools")
    
    # Create and register coordination agent (Phase 1 & 2 tools, resources, prompts)
    from agents.coordination_agent import CoordinationAgent
    coord_agent = CoordinationAgent("coordinator", node, "CoordinationAgent")
    node.register_agent("coordinator", coord_agent.server, agent_instance=coord_agent)
    logger.info(f"Registered coordination agent: {coord_agent.name} with {len(coord_agent.get_tools())} tools, {len(coord_agent.server.get_resources())} resources, {len(coord_agent.server.get_prompts())} prompts")
    
    # Create and register code agent (Phase 3 tools, resources, prompts)
    from agents.code_agent import CodeAgent
    code_agent = CodeAgent("code", workspace_path=Path(__file__).parent.parent, name="CodeAgent")
    node.register_agent("code", code_agent.server, agent_instance=code_agent)
    logger.info(f"Registered code agent: {code_agent.name} with {len(code_agent.get_tools())} tools, {len(code_agent.server.get_resources())} resources, {len(code_agent.server.get_prompts())} prompts")
    
    # Start HTTP server for frontend
    web_server = WebServer(port=8080)
    web_server.start()
    
    # Start P2P node
    logger.info("Starting P2P Node WebSocket server on ws://localhost:8000")
    logger.info("Frontend available at http://localhost:8080")
    
    try:
        # Start node (blocks until stopped)
        await node.start(host="localhost", port=8000)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        web_server.stop()
        await node.stop()
        logger.info("Project Dawn V2 stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)

