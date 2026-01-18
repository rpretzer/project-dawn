"""
Metrics Module

Provides Prometheus metrics collection and alerting for Project Dawn.
"""

from .metrics import MetricsCollector, register_metrics, get_metrics_collector
from .alerts import AlertManager, AlertThreshold

__all__ = [
    "MetricsCollector",
    "register_metrics",
    "get_metrics_collector",
    "AlertManager",
    "AlertThreshold",
]
