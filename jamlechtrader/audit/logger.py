"""Structured audit logging for all trading events."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from jamlechtrader.db.repositories import AuditLogRepository


def new_correlation_id() -> str:
    """Generate a new correlation ID for linking related audit events."""
    return str(uuid.uuid4())


class AuditLogger:
    """Append-only audit logger wrapping AuditLogRepository.

    Every method records an immutable event with a correlation_id
    linking the entire order lifecycle together.
    """

    def __init__(self, repository: AuditLogRepository) -> None:
        self._repo = repository

    async def log_order_created(
        self, correlation_id: str, order_data: dict[str, Any], source: str = "engine"
    ) -> None:
        await self._repo.append(
            event_type="ORDER_CREATED",
            event_data=order_data,
            correlation_id=correlation_id,
            source=source,
        )
        logger.debug(f"[audit] ORDER_CREATED corr={correlation_id[:8]}")

    async def log_order_submitted(
        self, correlation_id: str, order_data: dict[str, Any], source: str = "executor"
    ) -> None:
        await self._repo.append(
            event_type="ORDER_SUBMITTED",
            event_data=order_data,
            correlation_id=correlation_id,
            source=source,
        )
        logger.debug(f"[audit] ORDER_SUBMITTED corr={correlation_id[:8]}")

    async def log_fill_received(
        self, correlation_id: str, fill_data: dict[str, Any], source: str = "executor"
    ) -> None:
        await self._repo.append(
            event_type="FILL_RECEIVED",
            event_data=fill_data,
            correlation_id=correlation_id,
            source=source,
        )
        logger.debug(f"[audit] FILL_RECEIVED corr={correlation_id[:8]}")

    async def log_risk_rejected(
        self, correlation_id: str, reason: str, order_data: dict[str, Any] | None = None
    ) -> None:
        await self._repo.append(
            event_type="RISK_REJECTED",
            event_data={"reason": reason, "order": order_data},
            correlation_id=correlation_id,
            source="risk_manager",
        )
        logger.debug(f"[audit] RISK_REJECTED corr={correlation_id[:8]} reason={reason}")

    async def log_position_opened(
        self, correlation_id: str, position_data: dict[str, Any]
    ) -> None:
        await self._repo.append(
            event_type="POSITION_OPENED",
            event_data=position_data,
            correlation_id=correlation_id,
            source="portfolio",
        )
        logger.debug(f"[audit] POSITION_OPENED corr={correlation_id[:8]}")

    async def log_position_closed(
        self, correlation_id: str, trade_data: dict[str, Any]
    ) -> None:
        await self._repo.append(
            event_type="POSITION_CLOSED",
            event_data=trade_data,
            correlation_id=correlation_id,
            source="portfolio",
        )
        logger.debug(f"[audit] POSITION_CLOSED corr={correlation_id[:8]}")

    async def log_system_event(
        self, event_type: str, data: dict[str, Any] | None = None, source: str = "system"
    ) -> None:
        await self._repo.append(
            event_type=event_type,
            event_data=data,
            source=source,
        )
        logger.debug(f"[audit] {event_type} source={source}")
