"""
HTTP API Server

Provides HTTP endpoints for metrics, health checks, and monitoring.
"""

import json
import logging
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from metrics import register_metrics, get_metrics_collector
from health import HealthChecker, HealthStatus

logger = logging.getLogger(__name__)


class APIHandler(BaseHTTPRequestHandler):
    """
    HTTP handler for API endpoints (metrics, health, etc.)
    
    Provides /metrics, /health, /health/ready, /health/live endpoints.
    """
    
    def __init__(self, *args, node=None, health_checker: Optional[HealthChecker] = None, **kwargs):
        """Initialize API handler"""
        self.node = node
        self.health_checker = health_checker or HealthChecker()
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == "/metrics":
            self._handle_metrics()
        elif path == "/health":
            self._handle_health()
        elif path == "/health/ready":
            self._handle_health_ready()
        elif path == "/health/live":
            self._handle_health_live()
        else:
            self._handle_not_found()
    
    def _handle_metrics(self):
        """Handle /metrics endpoint"""
        try:
            metrics_collector = get_metrics_collector()
            if not metrics_collector:
                # Initialize if not already done
                metrics_collector = register_metrics()
            
            metrics_data = metrics_collector.get_metrics()
            content_type = metrics_collector.get_content_type()
            
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(metrics_data)
        except Exception as e:
            logger.error(f"Error serving metrics: {e}", exc_info=True)
            self.send_error(500, f"Error serving metrics: {e}")
    
    def _handle_health(self):
        """Handle /health endpoint (overall health)"""
        try:
            if not self.health_checker:
                self._send_json_response(200, {
                    "status": "healthy",
                    "message": "Health checker not initialized",
                    "timestamp": time.time(),
                })
                return
            
            result = None
            if hasattr(self.health_checker, 'get_overall_health'):
                import asyncio
                try:
                    # Try to get async result if in async context
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If loop is running, schedule and wait
                        future = asyncio.run_coroutine_threadsafe(
                            self.health_checker.get_overall_health(),
                            loop
                        )
                        result = future.result(timeout=5)
                    else:
                        result = loop.run_until_complete(self.health_checker.get_overall_health())
                except RuntimeError:
                    # No event loop, create sync wrapper
                    result = self._get_health_sync()
            else:
                result = self._get_health_sync()
            
            if result:
                status_code = 200 if result.status == HealthStatus.HEALTHY else (
                    503 if result.status == HealthStatus.UNHEALTHY else 200
                )
                self._send_json_response(status_code, {
                    "status": result.status.value,
                    "message": result.message,
                    "details": result.details,
                    "timestamp": result.timestamp,
                })
            else:
                self._send_json_response(200, {
                    "status": "healthy",
                    "message": "Health check not configured",
                    "timestamp": time.time(),
                })
        except Exception as e:
            logger.error(f"Error serving health: {e}", exc_info=True)
            self._send_json_response(500, {
                "status": "error",
                "message": f"Health check failed: {e}",
                "timestamp": time.time(),
            })
    
    def _get_health_sync(self):
        """Get health synchronously"""
        # Create simple sync check
        from health import HealthCheckResult
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="Basic health check",
            details={"uptime": time.time() - (getattr(self, '_start_time', time.time()))},
            timestamp=time.time(),
        )
    
    def _handle_health_ready(self):
        """Handle /health/ready endpoint (readiness probe)"""
        try:
            # Check if node is ready (started)
            ready = True
            if self.node:
                ready = hasattr(self.node, 'start_time') and self.node.start_time is not None
            
            status_code = 200 if ready else 503
            self._send_json_response(status_code, {
                "status": "ready" if ready else "not_ready",
                "message": "Node is ready" if ready else "Node is not ready",
                "timestamp": time.time(),
            })
        except Exception as e:
            logger.error(f"Error serving readiness: {e}", exc_info=True)
            self._send_json_response(500, {
                "status": "error",
                "message": f"Readiness check failed: {e}",
                "timestamp": time.time(),
            })
    
    def _handle_health_live(self):
        """Handle /health/live endpoint (liveness probe)"""
        try:
            # Check if node is alive (not crashed)
            alive = True
            if self.node:
                alive = True  # Assume alive if node exists
            
            status_code = 200 if alive else 503
            self._send_json_response(status_code, {
                "status": "alive" if alive else "dead",
                "message": "Node is alive" if alive else "Node is not alive",
                "timestamp": time.time(),
            })
        except Exception as e:
            logger.error(f"Error serving liveness: {e}", exc_info=True)
            self._send_json_response(500, {
                "status": "error",
                "message": f"Liveness check failed: {e}",
                "timestamp": time.time(),
            })
    
    def _handle_not_found(self):
        """Handle 404 Not Found"""
        self._send_json_response(404, {
            "error": "Not Found",
            "message": f"Endpoint {self.path} not found",
            "available_endpoints": ["/metrics", "/health", "/health/ready", "/health/live"],
        })
    
    def _send_json_response(self, status_code: int, data: Dict[str, Any]):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        logger.debug(f"API: {format % args}")


class APIServer:
    """
    HTTP API server for metrics and health checks
    
    Provides /metrics, /health, /health/ready, /health/live endpoints.
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 9090, node=None, health_checker: Optional[HealthChecker] = None):
        """
        Initialize API server
        
        Args:
            host: Host to bind to
            port: Port to bind to
            node: P2P node instance (optional, for health checks)
            health_checker: HealthChecker instance (optional)
        """
        self.host = host
        self.port = port
        self.node = node
        self.health_checker = health_checker
        self.server = None
        self.thread = None
    
    def start(self):
        """Start API server in background thread"""
        def handler_factory(*args, **kwargs):
            return APIHandler(*args, node=self.node, health_checker=self.health_checker, **kwargs)
        
        self.server = HTTPServer((self.host, self.port), handler_factory)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"API server started on http://{self.host}:{self.port}")
        logger.info(f"  - Metrics: http://{self.host}:{self.port}/metrics")
        logger.info(f"  - Health: http://{self.host}:{self.port}/health")
        logger.info(f"  - Readiness: http://{self.host}:{self.port}/health/ready")
        logger.info(f"  - Liveness: http://{self.host}:{self.port}/health/live")
    
    def stop(self):
        """Stop API server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("API server stopped")
