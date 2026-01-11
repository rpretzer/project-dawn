"""
Rate Limiting

Provides rate limiting per peer/node to prevent resource exhaustion.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Optional

from .errors import RateLimitError

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """
    Rate limit configuration
    
    Attributes:
        max_requests: Maximum number of requests per time window
        time_window: Time window in seconds
        burst_size: Maximum burst size (allows short bursts above rate limit)
    """
    max_requests: int = 100
    time_window: float = 60.0  # 1 minute
    burst_size: int = 10


class RateLimiter:
    """
    Rate limiter for per-peer/node rate limiting
    
    Uses token bucket algorithm with sliding window.
    """
    
    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter
        
        Args:
            default_config: Default rate limit configuration
        """
        self.default_config = default_config or RateLimitConfig()
        self.limiters: Dict[str, Dict[str, any]] = defaultdict(dict)
        logger.debug("RateLimiter initialized")
    
    def set_limit(
        self,
        identifier: str,
        config: RateLimitConfig,
    ) -> None:
        """
        Set rate limit for an identifier (peer/node ID)
        
        Args:
            identifier: Identifier (peer/node ID)
            config: Rate limit configuration
        """
        self.limiters[identifier] = {
            "config": config,
            "requests": [],
            "tokens": float(config.max_requests),
            "last_refill": time.time(),
        }
        logger.debug(f"Set rate limit for {identifier}: {config.max_requests}/{config.time_window}s")
    
    def get_limit(self, identifier: str) -> RateLimitConfig:
        """
        Get rate limit configuration for identifier
        
        Args:
            identifier: Identifier (peer/node ID)
            
        Returns:
            Rate limit configuration
        """
        if identifier in self.limiters:
            return self.limiters[identifier]["config"]
        return self.default_config
    
    def check_rate_limit(
        self,
        identifier: str,
        tokens: int = 1,
    ) -> Tuple[bool, Optional[float]]:
        """
        Check if request is within rate limit
        
        Args:
            identifier: Identifier (peer/node ID)
            tokens: Number of tokens to consume (default: 1)
            
        Returns:
            Tuple of (allowed, retry_after). retry_after is None if allowed.
        """
        # Get or create limiter for identifier
        if identifier not in self.limiters:
            self.set_limit(identifier, self.default_config)
        
        limiter = self.limiters[identifier]
        config = limiter["config"]
        now = time.time()
        
        # Refill tokens based on time elapsed
        time_since_refill = now - limiter["last_refill"]
        tokens_per_second = config.max_requests / config.time_window
        tokens_to_add = time_since_refill * tokens_per_second
        
        limiter["tokens"] = min(
            config.max_requests + config.burst_size,
            limiter["tokens"] + tokens_to_add
        )
        limiter["last_refill"] = now
        
        # Remove old requests outside time window
        cutoff_time = now - config.time_window
        limiter["requests"] = [
            req_time for req_time in limiter["requests"]
            if req_time > cutoff_time
        ]
        
        # Check if within rate limit
        if len(limiter["requests"]) >= config.max_requests:
            # Calculate retry after
            oldest_request = min(limiter["requests"])
            retry_after = config.time_window - (now - oldest_request)
            return False, retry_after
        
        # Check token bucket
        if limiter["tokens"] < tokens:
            # Calculate retry after (when enough tokens will be available)
            tokens_needed = tokens - limiter["tokens"]
            retry_after = tokens_needed / tokens_per_second
            return False, retry_after
        
        # Allow request
        limiter["requests"].append(now)
        limiter["tokens"] -= tokens
        
        return True, None
    
    def allow(
        self,
        identifier: str,
        tokens: int = 1,
    ) -> None:
        """
        Check rate limit and raise exception if exceeded
        
        Args:
            identifier: Identifier (peer/node ID)
            tokens: Number of tokens to consume (default: 1)
            
        Raises:
            RateLimitError: If rate limit is exceeded
        """
        allowed, retry_after = self.check_rate_limit(identifier, tokens)
        
        if not allowed:
            config = self.get_limit(identifier)
            error_msg = (
                f"Rate limit exceeded for {identifier}: "
                f"{config.max_requests} requests per {config.time_window}s"
            )
            raise RateLimitError(
                error_msg,
                retry_after=retry_after,
                details={
                    "identifier": identifier,
                    "max_requests": config.max_requests,
                    "time_window": config.time_window,
                }
            )
    
    def reset(self, identifier: Optional[str] = None) -> None:
        """
        Reset rate limiter for identifier (or all)
        
        Args:
            identifier: Identifier to reset (None = all)
        """
        if identifier:
            if identifier in self.limiters:
                del self.limiters[identifier]
                logger.debug(f"Reset rate limit for {identifier}")
        else:
            self.limiters.clear()
            logger.debug("Reset all rate limits")
