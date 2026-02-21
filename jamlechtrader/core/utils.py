"""Common utility functions."""

from typing import Any


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp value between min and max."""
    return max(min_value, min(value, max_value))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division with default value."""
    return numerator / denominator if denominator != 0 else default


def percentage_change(old_value: float, new_value: float) -> float:
    """Calculate percentage change."""
    return safe_divide(new_value - old_value, old_value) * 100


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format amount as currency."""
    return f"{currency} {amount:,.2f}"


def validate_positive(value: float, name: str) -> None:
    """Validate that value is positive."""
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
