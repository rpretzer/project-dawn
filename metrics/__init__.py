"""
Metrics Module

Provides Prometheus metrics collection for Project Dawn.
"""

from .metrics import MetricsCollector, register_metrics, get_metrics_collector

__all__ = [
    "MetricsCollector",
    "register_metrics",
    "get_metrics_collector",
]
