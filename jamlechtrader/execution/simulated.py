"""Simulated executor for backtesting — models spread, slippage, commission."""

from __future__ import annotations

import random
import uuid

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import FillEvent, OrderEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.execution.base import AbstractExecutionHandler


class SimulatedExecutor(AbstractExecutionHandler):
    """Fills orders at simulated prices using historical bar data."""

    def __init__(
        self,
        slippage_pips: float = 0.5,
        commission_per_lot: float = 7.0,
        use_bar_spread: bool = True,
    ) -> None:
        self.slippage_pips = slippage_pips
        self.commission_per_lot = commission_per_lot
        self.use_bar_spread = use_bar_spread
        self._current_bar: Bar | None = None

    def set_current_bar(self, bar: Bar) -> None:
        """Update the current bar for fill simulation."""
        self._current_bar = bar

    def execute_order(self, order: OrderEvent) -> FillEvent | None:
        if self._current_bar is None:
            return None

        bar = self._current_bar

        # Base fill price is the bar's open (next-bar open execution)
        base_price = bar.open

        # Apply spread
        spread_adjustment = 0.0
        if self.use_bar_spread and bar.spread > 0:
            # spread is in points; apply half to each side
            point = 0.00001 if "JPY" not in bar.symbol else 0.001
            spread_adjustment = bar.spread * point / 2
        else:
            spread_adjustment = self.slippage_pips * 0.0001

        # Apply slippage (random within range)
        slippage = random.uniform(0, self.slippage_pips) * 0.0001

        if order.side == OrderSide.BUY:
            fill_price = base_price + spread_adjustment + slippage
        else:
            fill_price = base_price - spread_adjustment - slippage

        commission = self.commission_per_lot * order.quantity

        return FillEvent(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=round(fill_price, 5),
            commission=commission,
            slippage=slippage,
            order_id=str(uuid.uuid4())[:8],
            timestamp=order.timestamp,
        )
