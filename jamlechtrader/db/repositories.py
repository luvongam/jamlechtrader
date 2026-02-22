"""Repository pattern for async database operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jamlechtrader.db.models import (
    AuditLogRow,
    ClosedTradeRow,
    FillRow,
    OrderRow,
    PortfolioSnapshotRow,
    PositionRow,
)


class OrderRepository:
    """Async CRUD for orders."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs) -> OrderRow:
        row = OrderRow(**kwargs)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_id(self, order_id: str) -> OrderRow | None:
        return await self._session.get(OrderRow, order_id)

    async def get_by_client_order_id(self, client_order_id: str) -> OrderRow | None:
        stmt = select(OrderRow).where(OrderRow.client_order_id == client_order_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_open_orders(self) -> Sequence[OrderRow]:
        stmt = select(OrderRow).where(
            OrderRow.status.in_(["PENDING", "SUBMITTED", "PARTIALLY_FILLED"])
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_status(self, order_id: str, status: str) -> None:
        stmt = (
            update(OrderRow)
            .where(OrderRow.id == order_id)
            .values(status=status, updated_at=datetime.now(tz=UTC))
        )
        await self._session.execute(stmt)

    async def get_by_symbol(self, symbol: str) -> Sequence[OrderRow]:
        stmt = select(OrderRow).where(OrderRow.symbol == symbol)
        result = await self._session.execute(stmt)
        return result.scalars().all()


class FillRepository:
    """Async CRUD for fills."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs) -> FillRow:
        row = FillRow(**kwargs)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_order_id(self, order_id: str) -> Sequence[FillRow]:
        stmt = select(FillRow).where(FillRow.order_id == order_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()


class PositionRepository:
    """Async CRUD for positions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, symbol: str, **kwargs) -> PositionRow:
        stmt = select(PositionRow).where(PositionRow.symbol == symbol)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            row = PositionRow(symbol=symbol, **kwargs)
            self._session.add(row)
        else:
            for key, value in kwargs.items():
                setattr(row, key, value)
            row.updated_at = datetime.now(tz=UTC)
        await self._session.flush()
        return row

    async def delete(self, symbol: str) -> None:
        stmt = select(PositionRow).where(PositionRow.symbol == symbol)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def get_all(self) -> Sequence[PositionRow]:
        stmt = select(PositionRow)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_symbol(self, symbol: str) -> PositionRow | None:
        stmt = select(PositionRow).where(PositionRow.symbol == symbol)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class SnapshotRepository:
    """Async CRUD for portfolio snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs) -> PortfolioSnapshotRow:
        row = PortfolioSnapshotRow(**kwargs)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_latest(self) -> PortfolioSnapshotRow | None:
        stmt = select(PortfolioSnapshotRow).order_by(
            PortfolioSnapshotRow.timestamp.desc()
        ).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_since(self, since: datetime) -> Sequence[PortfolioSnapshotRow]:
        stmt = (
            select(PortfolioSnapshotRow)
            .where(PortfolioSnapshotRow.timestamp >= since)
            .order_by(PortfolioSnapshotRow.timestamp)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class AuditLogRepository:
    """Async APPEND-ONLY audit log. No update or delete operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, **kwargs) -> AuditLogRow:
        row = AuditLogRow(**kwargs)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_correlation_id(self, correlation_id: str) -> Sequence[AuditLogRow]:
        stmt = (
            select(AuditLogRow)
            .where(AuditLogRow.correlation_id == correlation_id)
            .order_by(AuditLogRow.timestamp)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_event_type(
        self, event_type: str, *, limit: int = 100
    ) -> Sequence[AuditLogRow]:
        stmt = (
            select(AuditLogRow)
            .where(AuditLogRow.event_type == event_type)
            .order_by(AuditLogRow.timestamp.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_recent(self, limit: int = 50) -> Sequence[AuditLogRow]:
        stmt = (
            select(AuditLogRow)
            .order_by(AuditLogRow.timestamp.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class ClosedTradeRepository:
    """Async CRUD for closed trades."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs) -> ClosedTradeRow:
        row = ClosedTradeRow(**kwargs)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_symbol(self, symbol: str) -> Sequence[ClosedTradeRow]:
        stmt = (
            select(ClosedTradeRow)
            .where(ClosedTradeRow.symbol == symbol)
            .order_by(ClosedTradeRow.exit_time.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_recent(self, limit: int = 50) -> Sequence[ClosedTradeRow]:
        stmt = (
            select(ClosedTradeRow)
            .order_by(ClosedTradeRow.exit_time.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
