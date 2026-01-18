#!/usr/bin/env python3
"""
Server Manager for CLI

Manages server lifecycle - checks if running, starts if needed.
"""

import os
import sys
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def check_port(host: str, port: int, timeout: float = 0.5) -> bool:
    """Check if a port is open and accepting connections"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def check_server_health(port: int = 9090, timeout: float = 1.0) -> bool:
    """Check if server is running by hitting health endpoint"""
    try:
        import urllib.request
        import urllib.error
        
        url = f"http://localhost:{port}/health"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Project-Dawn-CLI/1.0')
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def is_server_running() -> bool:
    """Check if Project Dawn server is running"""
    # Check health endpoint (most reliable)
    if check_server_health(9090):
        return True
    
    # Fallback: check if ports are in use
    # WebSocket port (8000), HTTP port (8080), Metrics port (9090)
    ports_to_check = [8000, 8080, 9090]
    for port in ports_to_check:
        if check_port('localhost', port):
            return True
    
    return False


def find_server_script() -> Path:
    """Find the server_p2p.py script"""
    project_root = Path(__file__).parent.parent
    server_script = project_root / "server_p2p.py"
    
    if not server_script.exists():
        raise FileNotFoundError(f"Server script not found: {server_script}")
    
    return server_script


def start_server(background: bool = True) -> Optional[subprocess.Popen]:
    """Start the Project Dawn server"""
    try:
        server_script = find_server_script()
        project_root = server_script.parent
        
        # Prepare environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(project_root)
        
        if background:
            # Start in background (detached process)
            if sys.platform == 'win32':
                # Windows
                process = subprocess.Popen(
                    [sys.executable, str(server_script)],
                    cwd=str(project_root),
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                # Unix/Linux
                process = subprocess.Popen(
                    [sys.executable, str(server_script)],
                    cwd=str(project_root),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            
            return process
        else:
            # Start in foreground (for testing)
            process = subprocess.Popen(
                [sys.executable, str(server_script)],
                cwd=str(project_root),
                env=env,
            )
            return process
    
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return None


def ensure_server_running(timeout: float = 10.0, auto_start: bool = True) -> bool:
    """
    Ensure server is running, start if needed
    
    Args:
        timeout: Maximum time to wait for server to become ready
        auto_start: If True, start server if not running
    
    Returns:
        True if server is running, False otherwise
    """
    # Check if already running
    if is_server_running():
        return True
    
    if not auto_start:
        return False
    
    # Start server
    print("Starting Project Dawn server...")
    process = start_server(background=True)
    
    if process is None:
        print("Failed to start server")
        return False
    
    # Wait for server to become ready
    print("Waiting for server to start...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if is_server_running():
            print("Server is running!")
            return True
        time.sleep(0.5)
    
    print(f"Server did not become ready within {timeout} seconds")
    return False


def stop_server() -> bool:
    """Stop the running server (if possible)"""
    # This is a simple implementation - in production you might want
    # to use a PID file or process manager
    try:
        import psutil
        
        # Find process by port
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'server_p2p.py' in ' '.join(cmdline):
                    proc.terminate()
                    proc.wait(timeout=5)
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return False
    except ImportError:
        # psutil not available - can't reliably stop server
        return False
