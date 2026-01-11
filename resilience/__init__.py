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
from .retry import RetryPolicy, exponential_backoff, retry_with_policy
from .rate_limit import RateLimiter
from .circuit_breaker import CircuitBreaker, CircuitState

__all__ = [
    "ResilienceError",
    "NetworkError",
    "RateLimitError",
    "CircuitBreakerOpenError",
    "RetryExhaustedError",
    "RetryPolicy",
    "exponential_backoff",
    "retry_with_policy",
    "RateLimiter",
    "CircuitBreaker",
    "CircuitState",
]
