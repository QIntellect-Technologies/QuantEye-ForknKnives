"""
Logging configuration for the attendance system.
"""

import logging
import logging.handlers
from pathlib import Path
from config import LOG_DIR, LOG_LEVEL, LOG_FORMAT, LOG_MAX_SIZE, LOG_BACKUP_COUNT

# Create logs directory
LOG_DIR.mkdir(exist_ok=True)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, LOG_LEVEL))

# File handler with rotation
file_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / 'attendance.log',
    maxBytes=LOG_MAX_SIZE,
    backupCount=LOG_BACKUP_COUNT
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
root_logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(name)
