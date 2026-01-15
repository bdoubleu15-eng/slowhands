"""
Logging Configuration

Centralized logging setup for the SlowHands agent.
Supports structured JSON logging and correlation IDs.
"""

import logging
import sys
import json
import time
from typing import Optional, Dict, Any
from contextvars import ContextVar

# Context variable to store correlation ID for the current request/task
_correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

_logging_configured = False


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return _correlation_id_ctx.get()


def set_correlation_id(correlation_id: Optional[str]) -> None:
    """Set the current correlation ID."""
    _correlation_id_ctx.set(correlation_id)


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as a JSON string.
        """
        # Create a dictionary with standard fields
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        
        # Add correlation ID if available
        correlation_id = get_correlation_id()
        if correlation_id:
            log_data["correlation_id"] = correlation_id
            
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields from record if they don't conflict
        for key, value in record.__dict__.items():
            if key not in ["args", "asctime", "created", "exc_info", "exc_text", "filename",
                          "funcName", "levelname", "levelno", "lineno", "module", "msecs",
                          "message", "msg", "name", "pathname", "process", "processName",
                          "relativeCreated", "stack_info", "thread", "threadName"]:
                log_data[key] = value
                
        return json.dumps(log_data)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = True,
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file to write logs to
        json_format: Whether to use JSON formatting (default: True)
    """
    global _logging_configured

    # Avoid duplicate configuration
    if _logging_configured:
        return

    # Create formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Get root logger for our package
    root_logger = logging.getLogger("src")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    root_logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Reduce noise from external libraries
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Configure uvicorn access logs to be less noisy or use our format if needed
    # logging.getLogger("uvicorn.access").handlers = []
    # logging.getLogger("uvicorn.access").propagate = True

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a module.

    Args:
        name: Module name (will be prefixed with 'src.')

    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"src.{name}")
