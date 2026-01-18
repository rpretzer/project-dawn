"""
Retry Policies with Exponential Backoff

Provides retry logic with configurable policies.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Awaitable, Optional, Type, Tuple, Any

from .errors import RetryExhaustedError

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """
    Retry policy configuration
    
    Attributes:
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Exponential backoff base (default: 2.0)
        jitter: Add random jitter to delay (default: True)
        retryable_errors: Tuple of exception types to retry (default: (Exception,))
    """
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_errors: Tuple[Type[Exception], ...] = (Exception,)
    
    def __post_init__(self):
        """Validate retry policy"""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_delay < 0:
            raise ValueError("initial_delay must be >= 0")
        if self.max_delay < self.initial_delay:
            raise ValueError("max_delay must be >= initial_delay")


def exponential_backoff(
    attempt: int,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> float:
    """
    Calculate exponential backoff delay
    
    Args:
        attempt: Attempt number (0-indexed)
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Exponential base
        jitter: Add random jitter
        
    Returns:
        Delay in seconds
    """
    import random
    
    delay = initial_delay * (exponential_base ** attempt)
    delay = min(delay, max_delay)
    
    if jitter:
        # Add ±25% jitter
        jitter_amount = delay * 0.25
        delay = delay + random.uniform(-jitter_amount, jitter_amount)
        delay = max(0, delay)
    
    return delay


async def retry_with_policy(
    func: Callable[[], Awaitable[Any]],
    policy: RetryPolicy,
    operation_name: Optional[str] = None,
) -> Any:
    """
    Retry an async operation with a retry policy
    
    Args:
        func: Async function to retry (no arguments)
        policy: Retry policy
        operation_name: Optional operation name for logging
        
    Returns:
        Result from function
        
    Raises:
        RetryExhaustedError: If all retry attempts are exhausted
    """
    last_error: Optional[Exception] = None
    
    for attempt in range(policy.max_attempts):
        try:
            result = await func()
            if attempt > 0:
                logger.info(
                    f"Operation {'(' + operation_name + ') ' if operation_name else ''}"
                    f"succeeded on attempt {attempt + 1}/{policy.max_attempts}"
                )
            return result
        
        except policy.retryable_errors as e:
            last_error = e
            
            # Don't retry on last attempt
            if attempt >= policy.max_attempts - 1:
                break
            
            # Calculate delay
            delay = exponential_backoff(
                attempt,
                policy.initial_delay,
                policy.max_delay,
                policy.exponential_base,
                policy.jitter,
            )
            
            logger.warning(
                f"Operation {'(' + operation_name + ') ' if operation_name else ''}"
                f"failed on attempt {attempt + 1}/{policy.max_attempts}: {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            
            await asyncio.sleep(delay)
        
        except Exception as e:
            # Non-retryable error - raise immediately
            logger.error(
                f"Operation {'(' + operation_name + ') ' if operation_name else ''}"
                f"failed with non-retryable error: {e}"
            )
            raise
    
    # All retries exhausted
    error_msg = (
        f"Operation {'(' + operation_name + ') ' if operation_name else ''}"
        f"failed after {policy.max_attempts} attempts"
    )
    raise RetryExhaustedError(
        error_msg,
        attempts=policy.max_attempts,
        original_error=last_error,
        details={
            "operation": operation_name,
            "policy": {
                "max_attempts": policy.max_attempts,
                "initial_delay": policy.initial_delay,
                "max_delay": policy.max_delay,
            }
        }
    )


def retry_sync(
    func: Callable[[], Any],
    policy: RetryPolicy,
    operation_name: Optional[str] = None,
) -> Any:
    """
    Retry a sync operation with a retry policy
    
    Args:
        func: Sync function to retry (no arguments)
        policy: Retry policy
        operation_name: Optional operation name for logging
        
    Returns:
        Result from function
        
    Raises:
        RetryExhaustedError: If all retry attempts are exhausted
    """
    
    last_error: Optional[Exception] = None
    
    for attempt in range(policy.max_attempts):
        try:
            result = func()
            if attempt > 0:
                logger.info(
                    f"Operation {'(' + operation_name + ') ' if operation_name else ''}"
                    f"succeeded on attempt {attempt + 1}/{policy.max_attempts}"
                )
            return result
        
        except policy.retryable_errors as e:
            last_error = e
            
            # Don't retry on last attempt
            if attempt >= policy.max_attempts - 1:
                break
            
            # Calculate delay
            delay = exponential_backoff(
                attempt,
                policy.initial_delay,
                policy.max_delay,
                policy.exponential_base,
                policy.jitter,
            )
            
            logger.warning(
                f"Operation {'(' + operation_name + ') ' if operation_name else ''}"
                f"failed on attempt {attempt + 1}/{policy.max_attempts}: {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            
            time.sleep(delay)
        
        except Exception as e:
            # Non-retryable error - raise immediately
            logger.error(
                f"Operation {'(' + operation_name + ') ' if operation_name else ''}"
                f"failed with non-retryable error: {e}"
            )
            raise
    
    # All retries exhausted
    error_msg = (
        f"Operation {'(' + operation_name + ') ' if operation_name else ''}"
        f"failed after {policy.max_attempts} attempts"
    )
    raise RetryExhaustedError(
        error_msg,
        attempts=policy.max_attempts,
        original_error=last_error,
        details={
            "operation": operation_name,
            "policy": {
                "max_attempts": policy.max_attempts,
                "initial_delay": policy.initial_delay,
                "max_delay": policy.max_delay,
            }
        }
    )
