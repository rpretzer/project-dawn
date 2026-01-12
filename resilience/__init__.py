"""
Resilience Module

Provides error handling, retry logic, rate limiting, and circuit breakers for Project Dawn.
"""

from .errors import (
    ResilienceError,
    NetworkError,
    RateLimitError,
    CircuitBreakerOpenError,
    RetryExhaustedError,
)
from .retry import RetryPolicy, exponential_backoff, retry_with_policy, retry_sync
from .rate_limit import RateLimiter
from .circuit_breaker import CircuitBreaker, CircuitState

# Alias for convenience (retry_async is more intuitive name)
retry_async = retry_with_policy

__all__ = [
    "ResilienceError",
    "NetworkError",
    "RateLimitError",
    "CircuitBreakerOpenError",
    "RetryExhaustedError",
    "RetryPolicy",
    "exponential_backoff",
    "retry_with_policy",
    "retry_async",  # Alias for retry_with_policy
    "retry_sync",
    "RateLimiter",
    "CircuitBreaker",
    "CircuitState",
]
