"""
Health Check

Provides health check endpoints and monitoring.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Health check result"""
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    timestamp: float


class HealthChecker:
    """
    Health checker for system components
    
    Provides health check endpoints and monitoring.
    """
    
    def __init__(self):
        """Initialize health checker"""
        self.checks: Dict[str, Callable[[], Awaitable[HealthCheckResult]]] = {}
        self.start_time = time.time()
        logger.debug("HealthChecker initialized")
    
    def register_check(
        self,
        name: str,
        check_func: Callable[[], Awaitable[HealthCheckResult]],
    ) -> None:
        """
        Register a health check
        
        Args:
            name: Check name
            check_func: Async function that returns HealthCheckResult
        """
        self.checks[name] = check_func
        logger.debug(f"Registered health check: {name}")
    
    def register_sync_check(
        self,
        name: str,
        check_func: Callable[[], HealthCheckResult],
    ) -> None:
        """
        Register a synchronous health check
        
        Args:
            name: Check name
            check_func: Sync function that returns HealthCheckResult
        """
        async def async_wrapper() -> HealthCheckResult:
            return check_func()
        
        self.checks[name] = async_wrapper
        logger.debug(f"Registered sync health check: {name}")
    
    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """
        Run all health checks
        
        Returns:
            Dictionary of check name -> result
        """
        results = {}
        
        for name, check_func in self.checks.items():
            try:
                result = await check_func()
                results[name] = result
            except Exception as e:
                logger.error(f"Health check '{name}' failed: {e}", exc_info=True)
                results[name] = HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {e}",
                    details={"error": str(e)},
                    timestamp=time.time(),
                )
        
        return results
    
    async def get_overall_health(self) -> HealthCheckResult:
        """
        Get overall health status
        
        Returns:
            Overall health check result
        """
        checks = await self.check_all()
        
        if not checks:
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="No health checks registered",
                details={},
                timestamp=time.time(),
            )
        
        # Determine overall status
        statuses = [result.status for result in checks.values()]
        
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
            message = "All checks healthy"
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
            message = "Some checks unhealthy"
        else:
            overall_status = HealthStatus.DEGRADED
            message = "Some checks degraded"
        
        # Aggregate details
        details = {
            "uptime": time.time() - self.start_time,
            "checks": {name: result.status.value for name, result in checks.items()},
            "check_details": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "details": result.details,
                }
                for name, result in checks.items()
            },
        }
        
        return HealthCheckResult(
            status=overall_status,
            message=message,
            details=details,
            timestamp=time.time(),
        )
    
    def create_simple_check(
        self,
        name: str,
        check_func: Callable[[], bool],
        message: Optional[str] = None,
    ) -> None:
        """
        Create a simple boolean health check
        
        Args:
            name: Check name
            check_func: Function that returns True if healthy
            message: Optional message
        """
        def sync_check() -> HealthCheckResult:
            try:
                is_healthy = check_func()
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
                    message=message or ("Healthy" if is_healthy else "Unhealthy"),
                    details={},
                    timestamp=time.time(),
                )
            except Exception as e:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {e}",
                    details={"error": str(e)},
                    timestamp=time.time(),
                )
        
        self.register_sync_check(name, sync_check)
