"""
Sandbox Manager

Provides secure code execution using Docker containers.
"""

import logging
import time
import uuid
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import docker SDK
try:
    import docker
    from docker.errors import ContainerError, ImageNotFound, APIError
    from docker.models.containers import Container
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    logger.warning("Docker SDK not available. Sandboxing will fallback to local execution (INSECURE).")


class SandboxManager:
    """
    Manages secure execution environments using Docker.
    """
    
    def __init__(self, image: str = "python:3.11-slim", memory_limit: str = "128m", cpu_quota: int = 50000):
        """
        Initialize sandbox manager
        
        Args:
            image: Docker image to use for execution
            memory_limit: Memory limit for container (e.g., "128m")
            cpu_quota: CPU quota (50000 = 0.5 CPU)
        """
        self.image = image
        self.memory_limit = memory_limit
        self.cpu_quota = cpu_quota
        self.client = None
        
        if DOCKER_AVAILABLE:
            try:
                self.client = docker.from_env()
                # Check if image exists, pull if not
                try:
                    self.client.images.get(self.image)
                except ImageNotFound:
                    logger.info(f"Pulling Docker image: {self.image}")
                    self.client.images.pull(self.image)
            except Exception as e:
                logger.error(f"Failed to initialize Docker client: {e}")
                self.client = None
    
    def is_available(self) -> bool:
        """Check if sandboxing is available"""
        return DOCKER_AVAILABLE and self.client is not None
    
    def execute_code(
        self,
        code: str,
        language: str,
        timeout: float = 30.0,
        env_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Execute code in a sandbox
        
        Args:
            code: Source code to execute
            language: Programming language ("python", "javascript", "bash")
            timeout: Execution timeout in seconds
            env_vars: Environment variables
            
        Returns:
            Dict with execution results (stdout, stderr, exit_code)
        """
        if not self.is_available():
            logger.warning("Sandbox unavailable, skipping execution or falling back")
            return {
                "success": False,
                "error": "Sandbox unavailable (Docker not installed or running)",
                "stdout": "",
                "stderr": "",
                "exit_code": -1
            }
        
        # Prepare command based on language
        if language == "python":
            cmd = ["python", "-c", code]
            image = self.image  # Default is python
        elif language == "javascript":
            cmd = ["node", "-e", code]
            image = "node:18-slim" # Need node image
        elif language == "bash":
            cmd = ["bash", "-c", code]
            image = "debian:slim" # Lightweight base
        else:
            return {
                "success": False,
                "error": f"Unsupported language: {language}",
                "stdout": "",
                "stderr": "",
                "exit_code": -1
            }
            
        # If language requires a different image, ensure we have it
        if language != "python" and self.client:
            try:
                self.client.images.get(image)
            except ImageNotFound:
                try:
                    logger.info(f"Pulling Docker image: {image}")
                    self.client.images.pull(image)
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to pull image {image}: {e}",
                        "stdout": "",
                        "stderr": "",
                        "exit_code": -1
                    }

        container = None
        start_time = time.time()
        
        try:
            # Run container
            container = self.client.containers.run(
                image,
                cmd,
                detach=True,
                mem_limit=self.memory_limit,
                cpu_quota=self.cpu_quota,
                network_mode="none",  # No network access by default
                environment=env_vars or {},
                # security_opt=["no-new-privileges"], # Security best practice
                working_dir="/app",
            )
            
            # Wait for result with timeout
            try:
                result = container.wait(timeout=timeout)
                exit_code = result.get('StatusCode', 0)
            except Exception: # timeout raises distinct errors in diff docker versions
                # Kill container if timed out
                try:
                    container.kill()
                except:
                    pass
                return {
                    "success": False,
                    "error": f"Execution timed out after {timeout}s",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1
                }
            
            # Get logs
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8', errors='replace')
            stderr = container.logs(stdout=False, stderr=True).decode('utf-8', errors='replace')
            
            return {
                "success": exit_code == 0,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code
            }
            
        except Exception as e:
            logger.error(f"Sandbox execution error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": "",
                "exit_code": -1
            }
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception as e:
                    logger.warning(f"Failed to remove container: {e}")
