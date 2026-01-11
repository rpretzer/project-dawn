"""
Structured Error Handling

Provides error codes and structured exceptions for resilience operations.
"""

from enum import Enum
from typing import Optional, Dict, Any


class ErrorCode(Enum):
    """Error codes for structured error handling"""
    # Network errors (1xxx)
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_CONNECTION_FAILED = "NETWORK_CONNECTION_FAILED"
    NETWORK_UNREACHABLE = "NETWORK_UNREACHABLE"
    
    # Rate limiting (2xxx)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    RATE_LIMIT_QUOTA_EXHAUSTED = "RATE_LIMIT_QUOTA_EXHAUSTED"
    
    # Circuit breaker (3xxx)
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    CIRCUIT_BREAKER_HALF_OPEN = "CIRCUIT_BREAKER_HALF_OPEN"
    
    # Retry (4xxx)
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    RETRY_FAILED = "RETRY_FAILED"
    
    # General (9xxx)
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    OPERATION_FAILED = "OPERATION_FAILED"


class ResilienceError(Exception):
    """
    Base exception for resilience operations
    
    Provides structured error information with error codes.
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize resilience error
        
        Args:
            message: Error message
            error_code: Error code
            details: Additional error details
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
        }
    
    def __str__(self) -> str:
        base = f"{self.error_code.value}: {self.message}"
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{base} ({details_str})"
        return base


class NetworkError(ResilienceError):
    """Network-related errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.NETWORK_CONNECTION_FAILED,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, error_code, details, original_error)


class RateLimitError(ResilienceError):
    """Rate limiting errors"""
    
    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        details = details or {}
        if retry_after is not None:
            details["retry_after"] = retry_after
        super().__init__(
            message,
            ErrorCode.RATE_LIMIT_EXCEEDED,
            details,
            original_error
        )


class CircuitBreakerOpenError(ResilienceError):
    """Circuit breaker is open"""
    
    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if retry_after is not None:
            details["retry_after"] = retry_after
        super().__init__(
            message,
            ErrorCode.CIRCUIT_BREAKER_OPEN,
            details,
            None
        )


class RetryExhaustedError(ResilienceError):
    """Retry attempts exhausted"""
    
    def __init__(
        self,
        message: str,
        attempts: int,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        details = details or {}
        details["attempts"] = attempts
        super().__init__(
            message,
            ErrorCode.RETRY_EXHAUSTED,
            details,
            original_error
        )
