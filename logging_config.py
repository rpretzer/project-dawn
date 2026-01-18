"""
Logging Configuration

Provides structured logging with JSON format option and configurable log levels.
"""

import json
import logging
import os
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging
    
    Outputs logs in JSON format for easy parsing and aggregation.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        if hasattr(record, "context"):
            log_data["context"] = record.context
        
        return json.dumps(log_data)


def setup_logging(
    level: Optional[str] = None,
    format: str = "text",  # "text" or "json"
) -> None:
    """
    Setup logging configuration
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               If None, uses LOG_LEVEL environment variable or INFO
        format: Log format ("text" or "json")
                If "json", uses LOG_FORMAT environment variable or "text"
    """
    # Get log level from environment or parameter
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    log_level = getattr(logging, level, logging.INFO)
    
    # Get log format from environment or parameter
    if format == "text":
        log_format_env = os.getenv("LOG_FORMAT", "text").lower()
        use_json = log_format_env == "json"
    else:
        use_json = format.lower() == "json"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # Set formatter
    if use_json:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    logging.info(f"Logging configured: level={level}, format={'json' if use_json else 'text'}")


# Setup logging on import if LOG_LEVEL or LOG_FORMAT is set
if os.getenv("LOG_LEVEL") or os.getenv("LOG_FORMAT"):
    setup_logging()
