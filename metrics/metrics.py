"""
Prometheus Metrics Collection

Provides metrics collection for Project Dawn using Prometheus.
"""

import logging
import time
from typing import Optional, Dict, Any

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("prometheus_client not available. Metrics collection disabled.")

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Metrics collector for Project Dawn
    
    Collects Prometheus metrics for peers, messages, connections, and errors.
    """

    def __init__(self):
        """Initialize metrics collector"""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus metrics unavailable - install prometheus-client")
            self.enabled = False
            return
        
        self.enabled = True
        
        # Peer metrics
        self.peer_count = Gauge('p2p_peers_total', 'Total number of connected peers')
        self.peer_connections_total = Counter(
            'p2p_connections_total',
            'Total connection attempts',
            ['status']  # success, failure
        )
        
        # Message metrics
        self.messages_total = Counter(
            'p2p_messages_total',
            'Total messages processed',
            ['type', 'status']  # type: request/response/notification, status: success/error
        )
        self.message_latency = Histogram(
            'p2p_message_latency_seconds',
            'Message processing latency',
            ['type']
        )
        self.message_size = Histogram(
            'p2p_message_size_bytes',
            'Message size in bytes',
            ['type']
        )
        
        # Error metrics
        self.errors_total = Counter(
            'p2p_errors_total',
            'Total errors',
            ['error_type', 'component']  # error_type: NetworkError, RateLimitError, etc.
        )
        
        # Agent metrics
        self.agent_operations_total = Counter(
            'p2p_agent_operations_total',
            'Total agent operations',
            ['agent_id', 'operation', 'status']
        )
        self.agent_operation_latency = Histogram(
            'p2p_agent_operation_latency_seconds',
            'Agent operation latency',
            ['agent_id', 'operation']
        )
        
        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            'p2p_circuit_breaker_state',
            'Circuit breaker state (0=closed, 1=open, 2=half_open)',
            ['peer_id']
        )
        self.circuit_breaker_failures = Counter(
            'p2p_circuit_breaker_failures_total',
            'Circuit breaker failures',
            ['peer_id']
        )
        
        # Rate limiting metrics
        self.rate_limit_rejections = Counter(
            'p2p_rate_limit_rejections_total',
            'Rate limit rejections',
            ['peer_id', 'resource']
        )
        
        logger.info("MetricsCollector initialized")
    
    def record_peer_connection(self, status: str = "success") -> None:
        """Record peer connection attempt"""
        if not self.enabled:
            return
        self.peer_connections_total.labels(status=status).inc()
    
    def update_peer_count(self, count: int) -> None:
        """Update peer count"""
        if not self.enabled:
            return
        self.peer_count.set(count)
    
    def record_message(
        self,
        message_type: str,
        status: str = "success",
        latency: Optional[float] = None,
        size: Optional[int] = None,
    ) -> None:
        """Record message processing"""
        if not self.enabled:
            return
        self.messages_total.labels(type=message_type, status=status).inc()
        
        if latency is not None:
            self.message_latency.labels(type=message_type).observe(latency)
        
        if size is not None:
            self.message_size.labels(type=message_type).observe(size)
    
    def record_error(self, error_type: str, component: str = "unknown") -> None:
        """Record error"""
        if not self.enabled:
            return
        self.errors_total.labels(error_type=error_type, component=component).inc()
    
    def record_agent_operation(
        self,
        agent_id: str,
        operation: str,
        status: str = "success",
        latency: Optional[float] = None,
    ) -> None:
        """Record agent operation"""
        if not self.enabled:
            return
        self.agent_operations_total.labels(
            agent_id=agent_id,
            operation=operation,
            status=status
        ).inc()
        
        if latency is not None:
            self.agent_operation_latency.labels(
                agent_id=agent_id,
                operation=operation
            ).observe(latency)
    
    def update_circuit_breaker_state(self, peer_id: str, state: int) -> None:
        """
        Update circuit breaker state
        
        Args:
            peer_id: Peer ID
            state: 0=closed, 1=open, 2=half_open
        """
        if not self.enabled:
            return
        self.circuit_breaker_state.labels(peer_id=peer_id).set(state)
    
    def record_circuit_breaker_failure(self, peer_id: str) -> None:
        """Record circuit breaker failure"""
        if not self.enabled:
            return
        self.circuit_breaker_failures.labels(peer_id=peer_id).inc()
    
    def record_rate_limit_rejection(self, peer_id: str, resource: str = "message") -> None:
        """Record rate limit rejection"""
        if not self.enabled:
            return
        self.rate_limit_rejections.labels(peer_id=peer_id, resource=resource).inc()
    
    def get_metrics(self) -> bytes:
        """Get Prometheus metrics in text format"""
        if not self.enabled:
            return b"# Metrics collection disabled\n"
        return generate_latest()
    
    def get_content_type(self) -> str:
        """Get Prometheus metrics content type"""
        return CONTENT_TYPE_LATEST


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def register_metrics() -> MetricsCollector:
    """
    Register and return global metrics collector
    
    Returns:
        MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_metrics_collector() -> Optional[MetricsCollector]:
    """Get global metrics collector"""
    return _metrics_collector
