"""State recovery after crash — rebuild portfolio from database."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.models import Position, PortfolioSnapshot
from jamlechtrader.db.repositories import OrderRepository, PositionRepository, SnapshotRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class StateRecovery:
    """Recover portfolio state from database after a crash or restart."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._positions = PositionRepository(session)
        self._orders = OrderRepository(session)
        self._snapshots = SnapshotRepository(session)

    async def recover_portfolio(self) -> tuple[dict[str, Position], PortfolioSnapshot | None]:
        """Load open positions and last snapshot from DB."""
        position_rows = await self._positions.get_all()
        positions: dict[str, Position] = {}
        for row in position_rows:
            positions[row.symbol] = Position(
                symbol=row.symbol,
                side=OrderSide(row.side),
                quantity=row.quantity,
                entry_price=row.entry_price,
                current_price=row.current_price,
                stop_loss=row.stop_loss,
                take_profit=row.take_profit,
                unrealized_pnl=row.unrealized_pnl,
                ticket=row.ticket,
                open_time=row.opened_at,
            )

        snapshot_row = await self._snapshots.get_latest()
        snapshot = None
        if snapshot_row is not None:
            snapshot = PortfolioSnapshot(
                timestamp=snapshot_row.timestamp,
                cash=snapshot_row.cash,
                equity=snapshot_row.equity,
                margin_used=snapshot_row.margin_used,
                unrealized_pnl=snapshot_row.unrealized_pnl,
                realized_pnl=snapshot_row.realized_pnl,
                drawdown=snapshot_row.drawdown,
            )

        logger.info(
            f"State recovery: {len(positions)} open positions, "
            f"snapshot={'yes' if snapshot else 'none'}"
        )
        return positions, snapshot

    async def recover_open_orders(self) -> list[dict]:
        """Load SUBMITTED/PARTIALLY_FILLED orders for reconciliation."""
        order_rows = await self._orders.get_open_orders()
        orders = []
        for row in order_rows:
            orders.append({
                "id": row.id,
                "client_order_id": row.client_order_id,
                "symbol": row.symbol,
                "side": row.side,
                "order_type": row.order_type,
                "quantity": row.quantity,
                "price": row.price,
                "status": row.status,
                "strategy_name": row.strategy_name,
            })
        logger.info(f"Recovered {len(orders)} open orders for reconciliation")
        return orders

    async def save_state(
        self,
        positions: dict[str, Position],
        cash: float,
        equity: float,
        realized_pnl: float,
        drawdown: float,
    ) -> None:
        """Persist full portfolio state to database."""
        # Update positions
        current_symbols = set()
        for symbol, pos in positions.items():
            current_symbols.add(symbol)
            await self._positions.upsert(
                symbol=symbol,
                side=pos.side.value,
                quantity=pos.quantity,
                entry_price=pos.entry_price,
                current_price=pos.current_price,
                stop_loss=pos.stop_loss,
                take_profit=pos.take_profit,
                unrealized_pnl=pos.unrealized_pnl,
                ticket=pos.ticket,
            )

        # Remove positions no longer open
        all_rows = await self._positions.get_all()
        for row in all_rows:
            if row.symbol not in current_symbols:
                await self._positions.delete(row.symbol)

        # Save snapshot
        positions_json = [
            {
                "symbol": p.symbol,
                "side": p.side.value,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "unrealized_pnl": p.unrealized_pnl,
            }
            for p in positions.values()
        ]
        await self._snapshots.create(
            cash=cash,
            equity=equity,
            unrealized_pnl=sum(p.unrealized_pnl for p in positions.values()),
            realized_pnl=realized_pnl,
            drawdown=drawdown,
            positions=positions_json,
        )

        await self._session.commit()
        logger.debug("Portfolio state saved to database")
