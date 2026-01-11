#!/usr/bin/env python3
"""
Project Dawn V2 - P2P Node Server

Serves the frontend and runs a P2P node (decentralized).
"""

import asyncio
import json
import logging
import os
import socket
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
from data_paths import data_root
from orchestrator import Orchestrator
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


def _port_available(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
        return True
    except OSError:
        return False


def _pick_port(host: str, desired_port: int) -> int:
    if desired_port and _port_available(host, desired_port):
        return desired_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


class WebServer:
    """Simple HTTP server for frontend"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, ws_url: str = ""):
        self.host = host
        self.port = port
        self.ws_url = ws_url
        self.server = None
        self.thread = None
    
    def start(self):
        """Start HTTP server in background thread"""
        config_path = FRONTEND_DIR / "config.json"
        config_path.write_text(
            json.dumps({"wsUrl": self.ws_url, "httpUrl": f"http://{self.host}:{self.port}"}),
            encoding="utf-8",
        )
        self.server = HTTPServer((self.host, self.port), FrontendHandler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"HTTP server started on http://{self.host}:{self.port}")
    
    def stop(self):
        """Stop HTTP server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("HTTP server stopped")


def _load_persistent_identity(root_dir: Path) -> NodeIdentity:
    vault_dir = root_dir / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    identity_path = vault_dir / "node_identity.key"
    if identity_path.exists():
        key_bytes = identity_path.read_bytes()
        if len(key_bytes) == 32:
            return NodeIdentity.from_private_key_bytes(key_bytes)
    identity = NodeIdentity()
    tmp_path = identity_path.with_suffix(".key.tmp")
    tmp_path.write_bytes(identity.serialize_private_key())
    tmp_path.replace(identity_path)
    return identity


async def main():
    """Main entry point"""
    logger.info("Starting Project Dawn V2 (P2P Mode)...")
    host = os.getenv("PROJECT_DAWN_HOST", "127.0.0.1")
    desired_ws_port = int(os.getenv("PROJECT_DAWN_WS_PORT", "8000"))
    desired_http_port = int(os.getenv("PROJECT_DAWN_HTTP_PORT", "8080"))
    ws_port = _pick_port(host, desired_ws_port)
    http_port = _pick_port(host, desired_http_port)
    if ws_port != desired_ws_port:
        logger.warning(f"WebSocket port {desired_ws_port} unavailable, using {ws_port}")
    if http_port != desired_http_port:
        logger.warning(f"HTTP port {desired_http_port} unavailable, using {http_port}")
    
    data_dir = data_root()
    identity = _load_persistent_identity(data_dir)
    logger.info(f"Node ID: {identity.get_node_id()[:16]}...")
    
    # Create P2P node
    node = P2PNode(
        identity=identity,
        address=f"ws://{host}:{ws_port}",
        bootstrap_nodes=None,  # No bootstrap nodes for single-node setup
        enable_encryption=True,
        enable_privacy=True,
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
    web_server = WebServer(host=host, port=http_port, ws_url=f"ws://{host}:{ws_port}")
    web_server.start()
    
    # Start P2P node
    logger.info(f"Starting P2P Node WebSocket server on ws://{host}:{ws_port}")
    logger.info(f"Frontend available at http://{host}:{http_port}")
    orchestrator_task = None
    orchestrator = None

    pgp_key_path = data_dir / "vault" / "public_key.asc"
    if pgp_key_path.exists():
        orchestrator = Orchestrator(
            data_dir=data_dir,
            pgp_public_key_path=pgp_key_path,
            mdns_port=ws_port,
            mdns_service_name="project-dawn-orchestrator",
        )
        orchestrator_task = asyncio.create_task(orchestrator.run())
        logger.info("Orchestrator loop started")
    else:
        logger.warning("PGP public key missing; orchestrator loop not started")
    
    try:
        # Start node (blocks until stopped)
        await node.start(host=host, port=ws_port)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if orchestrator:
            orchestrator.stop()
        if orchestrator_task:
            await orchestrator_task
        web_server.stop()
        await node.stop()
        logger.info("Project Dawn V2 stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
