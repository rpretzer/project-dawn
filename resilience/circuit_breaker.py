"""
Circuit Breaker Pattern

Provides circuit breaker for peer connections to prevent cascading failures.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Awaitable, Optional, Any

from .errors import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """
    Circuit breaker configuration
    
    Attributes:
        failure_threshold: Number of failures before opening circuit
        success_threshold: Number of successes to close from half-open (default: 1)
        timeout: Time in seconds before attempting half-open (default: 60.0)
        expected_exception: Exception type that should open circuit (default: Exception)
    """
    failure_threshold: int = 5
    success_threshold: int = 1
    timeout: float = 60.0
    expected_exception: type[Exception] = Exception


class CircuitBreaker:
    """
    Circuit breaker for peer connections
    
    Prevents cascading failures by opening circuit when failures exceed threshold.
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        """
        Initialize circuit breaker
        
        Args:
            name: Circuit breaker name (typically peer/node ID)
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.opened_at: Optional[float] = None
        logger.debug(f"CircuitBreaker '{name}' initialized (state: {self.state.value})")
    
    def _should_attempt_half_open(self) -> bool:
        """Check if circuit should transition to half-open"""
        if self.state != CircuitState.OPEN:
            return False
        if self.opened_at is None:
            return False
        elapsed = time.time() - self.opened_at
        return elapsed >= self.config.timeout
    
    def _record_success(self) -> None:
        """Record successful operation"""
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0
                self.opened_at = None
                logger.info(f"CircuitBreaker '{self.name}' closed (recovered)")
        elif self.state == CircuitState.CLOSED:
            # Reset success count on continuous success
            self.success_count = 0
    
    def _record_failure(self) -> None:
        """Record failed operation"""
        self.success_count = 0
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = time.time()
                logger.warning(
                    f"CircuitBreaker '{self.name}' opened "
                    f"({self.failure_count} failures >= {self.config.failure_threshold})"
                )
        elif self.state == CircuitState.HALF_OPEN:
            # Failure in half-open -> back to open
            self.state = CircuitState.OPEN
            self.failure_count = self.config.failure_threshold
            self.opened_at = time.time()
            logger.warning(f"CircuitBreaker '{self.name}' reopened (failure in half-open)")
    
    def call(self, func: Callable[[], Awaitable[Any]]) -> Any:
        """
        Execute function with circuit breaker protection (async)
        
        Args:
            func: Async function to execute (no arguments)
            
        Returns:
            Result from function
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        # Check if circuit should transition to half-open
        if self._should_attempt_half_open():
            self.state = CircuitState.HALF_OPEN
            self.failure_count = 0
            self.success_count = 0
            logger.info(f"CircuitBreaker '{self.name}' half-open (testing recovery)")
        
        # Check circuit state
        if self.state == CircuitState.OPEN:
            retry_after = self.config.timeout - (time.time() - (self.opened_at or 0))
            retry_after = max(0, retry_after)
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open",
                retry_after=retry_after,
                details={
                    "name": self.name,
                    "failure_count": self.failure_count,
                    "opened_at": self.opened_at,
                }
            )
        
        # Execute function
        async def _execute() -> Any:
            try:
                result = await func()
                self._record_success()
                return result
            except self.config.expected_exception:
                self._record_failure()
                raise
            except Exception as e:
                # Unexpected exception - don't record as failure
                logger.warning(
                    f"CircuitBreaker '{self.name}' unexpected exception: {e}"
                )
                raise
        
        return _execute()
    
    async def call_async(self, func: Callable[[], Awaitable[Any]]) -> Any:
        """
        Execute async function with circuit breaker protection
        
        Args:
            func: Async function to execute (no arguments)
            
        Returns:
            Result from function
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        # Check if circuit should transition to half-open
        if self._should_attempt_half_open():
            self.state = CircuitState.HALF_OPEN
            self.failure_count = 0
            self.success_count = 0
            logger.info(f"CircuitBreaker '{self.name}' half-open (testing recovery)")
        
        # Check circuit state
        if self.state == CircuitState.OPEN:
            retry_after = self.config.timeout - (time.time() - (self.opened_at or 0))
            retry_after = max(0, retry_after)
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open",
                retry_after=retry_after,
                details={
                    "name": self.name,
                    "failure_count": self.failure_count,
                    "opened_at": self.opened_at,
                }
            )
        
        # Execute function
        try:
            result = await func()
            self._record_success()
            return result
        except self.config.expected_exception:
            self._record_failure()
            raise
        except Exception as e:
            # Unexpected exception - don't record as failure
            logger.warning(
                f"CircuitBreaker '{self.name}' unexpected exception: {e}"
            )
            raise
    
    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        return self.state
    
    def reset(self) -> None:
        """Reset circuit breaker to closed state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.opened_at = None
        logger.info(f"CircuitBreaker '{self.name}' reset to closed")
