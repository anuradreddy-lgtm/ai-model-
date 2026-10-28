"""Diagnostic logging system for JARVIS."""

import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
from jarvis.config import config


def setup_logger(name: str = "jarvis") -> logging.Logger:
    """Configure and return application logger with console and file handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s:%(funcName)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    try:
        log_file = config.logs_dir / "jarvis.log"
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as exc:
        print(f"Warning: Could not initialize file logging: {exc}", file=sys.stderr)

    return logger


logger = setup_logger()
