"""Live MT5 execution handler — wraps mt5/executor.py for the engine layer."""

from __future__ import annotations

from loguru import logger

from jamlechtrader.core.enums import OrderType
from jamlechtrader.core.events import FillEvent, OrderEvent
from jamlechtrader.core.models import Order
from jamlechtrader.execution.base import AbstractExecutionHandler
from jamlechtrader.mt5.executor import MT5Executor


class MT5LiveExecutor(AbstractExecutionHandler):
    """Sends real orders to MetaTrader 5."""

    def __init__(self) -> None:
        self._executor = MT5Executor()

    def execute_order(self, order_event: OrderEvent) -> FillEvent | None:
        """Convert OrderEvent to Order model and send via MT5."""
        order = Order(
            symbol=order_event.symbol,
            side=order_event.side,
            order_type=order_event.order_type,
            quantity=order_event.quantity,
            price=order_event.price,
            stop_loss=order_event.stop_loss,
            take_profit=order_event.take_profit,
            comment="jamlechtrader live",
        )

        fill = self._executor.send_order(order)
        if fill is None:
            logger.warning(f"MT5 order rejected: {order_event.symbol} {order_event.side.value}")
            return None

        return FillEvent(
            symbol=fill.symbol,
            side=fill.side,
            quantity=fill.quantity,
            price=fill.price,
            commission=fill.commission,
            order_id=fill.order_id,
            timestamp=fill.timestamp,
        )
