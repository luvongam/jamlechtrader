"""Risk management with enterprise-grade validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from jamlechtrader.core.constants import (
    DEFAULT_MAX_DRAWDOWN,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_RISK_PER_TRADE,
)
from jamlechtrader.core.exceptions import RiskLimitError

if TYPE_CHECKING:
    from jamlechtrader.core.events import OrderEvent
    from jamlechtrader.core.models import PortfolioSnapshot


@dataclass(frozen=True)
class RiskLimits:
    """Immutable risk management limits."""
    max_daily_drawdown_pct: float = DEFAULT_MAX_DRAWDOWN * 100
    max_position_size: float = 1.0
    max_open_positions: int = DEFAULT_MAX_POSITIONS
    max_risk_per_trade_pct: float = DEFAULT_RISK_PER_TRADE * 100
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 4.0
    max_order_size: float = 10.0


class RiskManager:
    """Validates orders and enforces risk limits."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()
        self._daily_start_equity: float | None = None
        self._daily_peak_equity: float | None = None
        self._halted = False

    def check_order(
        self, order: OrderEvent, portfolio: PortfolioSnapshot
    ) -> OrderEvent | None:
        """Validate order against risk rules."""
        if self._halted:
            logger.warning("Trading halted due to risk limits")
            return None

        try:
            self._check_daily_drawdown(portfolio.equity)
            self._check_position_limits(portfolio)
            self._validate_order_size(order)
            return order
        except RiskLimitError as e:
            logger.warning(f"Order rejected: {e}")
            return None

    def _check_daily_drawdown(self, current_equity: float) -> None:
        """Check daily drawdown limit."""
        if self._daily_start_equity is None:
            self._daily_start_equity = current_equity
            self._daily_peak_equity = current_equity
            return

        self._daily_peak_equity = max(self._daily_peak_equity, current_equity)
        drawdown_pct = (
            (self._daily_peak_equity - current_equity) / self._daily_peak_equity * 100
        )

        if drawdown_pct >= self.limits.max_daily_drawdown_pct:
            self._halted = True
            raise RiskLimitError(
                f"Daily drawdown {drawdown_pct:.2f}% exceeds limit {self.limits.max_daily_drawdown_pct}%"
            )

    def _check_position_limits(self, portfolio: PortfolioSnapshot) -> None:
        """Check position count limits."""
        if len(portfolio.positions) >= self.limits.max_open_positions:
            raise RiskLimitError(
                f"Max open positions ({self.limits.max_open_positions}) reached"
            )

    def _validate_order_size(self, order: OrderEvent) -> None:
        """Validate order size."""
        if order.quantity > self.limits.max_order_size:
            raise RiskLimitError(
                f"Order size {order.quantity} exceeds max {self.limits.max_order_size}"
            )
        
        if order.quantity > self.limits.max_position_size:
            logger.info(f"Clamping order size to {self.limits.max_position_size}")
            order.quantity = self.limits.max_position_size

    def calculate_position_size(
        self, equity: float, price: float, stop_distance_pct: float
    ) -> float:
        """Calculate optimal position size."""
        risk_amount = equity * (self.limits.max_risk_per_trade_pct / 100)
        stop_distance = price * (stop_distance_pct / 100)
        position_size = risk_amount / stop_distance if stop_distance > 0 else 0
        return min(position_size, self.limits.max_position_size)

    def reset_daily(self, equity: float) -> None:
        """Reset daily tracking."""
        self._daily_start_equity = equity
        self._daily_peak_equity = equity
        self._halted = False
        logger.info("Daily risk limits reset")

    @property
    def is_halted(self) -> bool:
        """Check if trading is halted."""
        return self._halted
