"""
Alerting System

Monitors metrics and triggers alerts based on thresholds.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class AlertThreshold:
    """Threshold for an alert"""
    name: str
    metric_name: str
    operator: str  # 'gt', 'lt', 'eq'
    value: float
    duration: float = 0.0  # Must be in this state for X seconds
    severity: str = "warning"  # warning, critical

@dataclass
class AlertState:
    """Current state of an alert"""
    active: bool = False
    first_detected: Optional[float] = None
    last_triggered: Optional[float] = None

class AlertManager:
    """
    Alert manager for Project Dawn
    
    Monitors metrics from the MetricsCollector and triggers alerts.
    """
    
    def __init__(self, metrics_collector: Any):
        """
        Initialize alert manager
        
        Args:
            metrics_collector: MetricsCollector instance
        """
        self.metrics = metrics_collector
        self.thresholds: List[AlertThreshold] = []
        self.states: Dict[str, AlertState] = {}
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self.on_alert: List[Callable[[AlertThreshold, float], None]] = []
        
        # Add default thresholds
        self._add_default_thresholds()
        
        logger.info("AlertManager initialized")
    
    def _add_default_thresholds(self):
        """Add default alerting thresholds"""
        # Alert if peer count is zero
        self.add_threshold(AlertThreshold(
            name="No Peers Connected",
            metric_name="p2p_peers_total",
            operator="lt",
            value=1.0,
            duration=30.0,
            severity="warning"
        ))
        
        # Alert if high error rate
        self.add_threshold(AlertThreshold(
            name="High Error Rate",
            metric_name="p2p_errors_total",
            operator="gt",
            value=10.0,  # More than 10 total errors
            severity="warning"
        ))

    def add_threshold(self, threshold: AlertThreshold):
        """Add an alert threshold"""
        self.thresholds.append(threshold)
        self.states[threshold.name] = AlertState()
    
    def start(self, interval: float = 10.0):
        """Start the alert monitoring loop"""
        if self.running:
            return
        
        self.running = True
        self._task = asyncio.create_task(self._run_loop(interval))
        logger.info(f"AlertManager started (interval: {interval}s)")
    
    def stop(self):
        """Stop the alert monitoring loop"""
        self.running = False
        if self._task:
            self._task.cancel()
        logger.info("AlertManager stopped")
    
    async def _run_loop(self, interval: float):
        """Monitoring loop"""
        while self.running:
            try:
                await self.check_alerts()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in alert check loop: {e}", exc_info=True)
                await asyncio.sleep(interval)
    
    async def check_alerts(self):
        """Check all thresholds against current metrics"""
        if not self.metrics or not self.metrics.enabled:
            return

        for threshold in self.thresholds:
            value = self._get_metric_value(threshold.metric_name)
            if value is None:
                continue
            
            is_failing = False
            if threshold.operator == "gt":
                is_failing = value > threshold.value
            elif threshold.operator == "lt":
                is_failing = value < threshold.value
            elif threshold.operator == "eq":
                is_failing = value == threshold.value
            
            state = self.states[threshold.name]
            now = time.time()
            
            if is_failing:
                if not state.first_detected:
                    state.first_detected = now
                
                # Check duration requirement
                elapsed = now - state.first_detected
                if elapsed >= threshold.duration:
                    if not state.active:
                        self._trigger_alert(threshold, value)
                        state.active = True
                        state.last_triggered = now
            else:
                if state.active:
                    self._resolve_alert(threshold, value)
                    state.active = False
                state.first_detected = None

    def _get_metric_value(self, metric_name: str) -> Optional[float]:
        """Extract value from Prometheus metric (simplified for local use)"""
        try:
            # This is a bit of a hack to access raw values from prometheus_client metrics
            # In a real system, we'd query the Prometheus API, but for local alerts
            # we can look at the metric objects directly.
            if metric_name == "p2p_peers_total":
                return self.metrics.peer_count._value.get()
            elif metric_name == "p2p_errors_total":
                # Counters are harder because they are labeled. We'll sum all labels.
                # This is an approximation.
                return sum(c._value.get() for c in self.metrics.errors_total._metrics.values())
        except Exception as e:
            logger.debug(f"Could not get value for metric {metric_name}: {e}")
        return None

    def _trigger_alert(self, threshold: AlertThreshold, value: float):
        """Trigger an alert"""
        msg = f"ALERT [{threshold.severity.upper()}]: {threshold.name} (Metric: {threshold.metric_name}, Value: {value})"
        if threshold.severity == "critical":
            logger.critical(msg)
        else:
            logger.warning(msg)
        
        # Call custom handlers
        for handler in self.on_alert:
            try:
                handler(threshold, value)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")

    def _resolve_alert(self, threshold: AlertThreshold, value: float):
        """Resolve an alert"""
        logger.info(f"RESOLVED: {threshold.name} (Metric: {threshold.metric_name}, Value: {value})")
