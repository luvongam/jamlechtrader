"""Paper trading executor — virtual fills using live MT5 prices."""

from __future__ import annotations

import uuid

from loguru import logger

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import FillEvent, OrderEvent
from jamlechtrader.core.models import Tick
from jamlechtrader.execution.base import AbstractExecutionHandler


class PaperExecutor(AbstractExecutionHandler):
    """Simulates fills using live tick data (no real orders placed)."""

    def __init__(self, commission_per_lot: float = 7.0) -> None:
        self.commission_per_lot = commission_per_lot
        self._current_tick: Tick | None = None
        self.fill_log: list[FillEvent] = []

    def set_current_tick(self, tick: Tick) -> None:
        """Update current tick for fill pricing."""
        self._current_tick = tick

    def execute_order(self, order: OrderEvent) -> FillEvent | None:
        if self._current_tick is None:
            logger.warning("No tick available for paper execution")
            return None

        tick = self._current_tick

        if order.side == OrderSide.BUY:
            fill_price = tick.ask
        else:
            fill_price = tick.bid

        commission = self.commission_per_lot * order.quantity

        fill = FillEvent(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
            order_id=f"paper-{uuid.uuid4().hex[:8]}",
            timestamp=order.timestamp,
        )
        self.fill_log.append(fill)
        logger.info(
            f"[PAPER] {order.side.value} {order.quantity} {order.symbol} @ {fill_price}"
        )
        return fill
