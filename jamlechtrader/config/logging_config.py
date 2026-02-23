"""Structured logging configuration using loguru with correlation ID support."""

import sys

from loguru import logger

from jamlechtrader.monitoring.correlation import get_correlation_id


def _correlation_filter(record):
    """Add correlation_id to log records."""
    record["extra"]["correlation_id"] = get_correlation_id() or "-"
    return True


def setup_logging(level: str = "INFO") -> None:
    """Configure loguru for the application with correlation ID in format."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        filter=_correlation_filter,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<dim>{extra[correlation_id]}</dim> | "
            "<level>{message}</level>"
        ),
    )
    logger.add(
        "logs/jamlechtrader_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="1 day",
        retention="30 days",
        filter=_correlation_filter,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | "
            "{extra[correlation_id]} | {message}"
        ),
    )
