"""Correlation ID propagation using contextvars."""

from __future__ import annotations

import contextvars
import uuid

_correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def new_correlation_id() -> str:
    """Generate a new correlation ID and set it in the current context."""
    cid = str(uuid.uuid4())
    _correlation_id_var.set(cid)
    return cid


def get_correlation_id() -> str | None:
    """Get the current correlation ID from context."""
    return _correlation_id_var.get()


def set_correlation_id(cid: str) -> None:
    """Explicitly set a correlation ID in the current context."""
    _correlation_id_var.set(cid)
