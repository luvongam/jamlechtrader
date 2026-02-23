"""Enterprise-grade risk management with per-symbol limits, VaR, and kill switch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

from jamlechtrader.core.constants import DEFAULT_MAX_DRAWDOWN, DEFAULT_MAX_POSITIONS
from jamlechtrader.core.exceptions import RiskLimitError

if TYPE_CHECKING:
    from jamlechtrader.audit.logger import AuditLogger
    from jamlechtrader.core.events import OrderEvent
    from jamlechtrader.core.models import PortfolioSnapshot
    from jamlechtrader.portfolio.kill_switch import KillSwitch
    from jamlechtrader.portfolio.var import VaRCalculator


@dataclass(frozen=True)
class EnterpriseRiskLimits:
    """Extended risk limits for institutional trading."""

    # Basic limits
    max_daily_drawdown_pct: float = DEFAULT_MAX_DRAWDOWN * 100
    max_position_size: float = 1.0
    max_open_positions: int = DEFAULT_MAX_POSITIONS
    max_risk_per_trade_pct: float = 2.0
    max_order_size: float = 10.0

    # Per-symbol limits
    per_symbol_max_position: dict[str, float] = field(default_factory=dict)
    per_symbol_max_notional: dict[str, float] = field(default_factory=dict)

    # Notional / leverage
    max_total_notional: float = 1_000_000.0
    max_leverage_ratio: float = 10.0
    max_margin_utilization_pct: float = 80.0

    # VaR
    var_confidence_level: float = 0.95
    max_var_pct: float = 5.0

    # Kill switch
    kill_switch_drawdown_pct: float = 10.0
    kill_switch_max_loss: float = 50_000.0
    kill_switch_consecutive_losses: int = 10


class EnterpriseRiskManager:
    """Ordered risk check pipeline with audit logging.

    Checks run in sequence — the first failure rejects the order.
    """

    def __init__(
        self,
        limits: EnterpriseRiskLimits | None = None,
        audit_logger: AuditLogger | None = None,
        var_calculator: VaRCalculator | None = None,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        self.limits = limits or EnterpriseRiskLimits()
        self._audit_logger = audit_logger
        self._var_calculator = var_calculator
        self._kill_switch = kill_switch
        self._daily_start_equity: float | None = None
        self._daily_peak_equity: float | None = None
        self._halted = False
        self._consecutive_losses = 0

    def check_order(
        self,
        order: OrderEvent,
        portfolio: PortfolioSnapshot,
        correlation_id: str | None = None,
    ) -> OrderEvent | None:
        """Run the full risk check pipeline."""
        if self._halted:
            logger.warning("Trading halted — order rejected")
            return None

        checks = [
            self._check_daily_drawdown,
            self._check_position_limits,
            self._check_per_symbol_limits,
            self._check_notional_limits,
            self._check_margin_requirements,
            self._check_leverage_ratio,
            self._check_var_limit,
            self._check_kill_switch,
        ]

        for check in checks:
            try:
                check(order, portfolio)
            except RiskLimitError as e:
                logger.warning(f"Order rejected by {check.__name__}: {e}")
                return None

        return order

    def _check_daily_drawdown(self, order: OrderEvent, portfolio: PortfolioSnapshot) -> None:
        equity = portfolio.equity
        if self._daily_start_equity is None:
            self._daily_start_equity = equity
            self._daily_peak_equity = equity
            return

        self._daily_peak_equity = max(self._daily_peak_equity, equity)
        if self._daily_peak_equity > 0:
            dd_pct = (self._daily_peak_equity - equity) / self._daily_peak_equity * 100
            if dd_pct >= self.limits.max_daily_drawdown_pct:
                self._halted = True
                raise RiskLimitError(
                    f"Daily drawdown {dd_pct:.2f}% >= limit {self.limits.max_daily_drawdown_pct}%"
                )

    def _check_position_limits(self, order: OrderEvent, portfolio: PortfolioSnapshot) -> None:
        if len(portfolio.positions) >= self.limits.max_open_positions:
            raise RiskLimitError(
                f"Max open positions ({self.limits.max_open_positions}) reached"
            )

    def _check_per_symbol_limits(self, order: OrderEvent, portfolio: PortfolioSnapshot) -> None:
        symbol = order.symbol
        if symbol in self.limits.per_symbol_max_position:
            max_qty = self.limits.per_symbol_max_position[symbol]
            current_qty = sum(
                p.quantity for p in portfolio.positions if p.symbol == symbol
            )
            if current_qty + order.quantity > max_qty:
                raise RiskLimitError(
                    f"Per-symbol position limit for {symbol}: "
                    f"{current_qty + order.quantity:.4f} > {max_qty:.4f}"
                )

        if symbol in self.limits.per_symbol_max_notional:
            max_notional = self.limits.per_symbol_max_notional[symbol]
            price = order.price or 0.0
            notional = (order.quantity * price) if price > 0 else 0.0
            current_notional = sum(
                p.quantity * p.current_price
                for p in portfolio.positions
                if p.symbol == symbol
            )
            if current_notional + notional > max_notional:
                raise RiskLimitError(
                    f"Per-symbol notional limit for {symbol}: "
                    f"{current_notional + notional:.2f} > {max_notional:.2f}"
                )

    def _check_notional_limits(self, order: OrderEvent, portfolio: PortfolioSnapshot) -> None:
        total_notional = sum(
            p.quantity * p.current_price for p in portfolio.positions
        )
        price = order.price or 0.0
        order_notional = order.quantity * price if price > 0 else 0.0
        if total_notional + order_notional > self.limits.max_total_notional:
            raise RiskLimitError(
                f"Total notional {total_notional + order_notional:.2f} "
                f"> limit {self.limits.max_total_notional:.2f}"
            )

    def _check_margin_requirements(self, order: OrderEvent, portfolio: PortfolioSnapshot) -> None:
        if portfolio.equity > 0 and portfolio.margin_used > 0:
            utilization = (portfolio.margin_used / portfolio.equity) * 100
            if utilization >= self.limits.max_margin_utilization_pct:
                raise RiskLimitError(
                    f"Margin utilization {utilization:.1f}% "
                    f">= limit {self.limits.max_margin_utilization_pct}%"
                )

    def _check_leverage_ratio(self, order: OrderEvent, portfolio: PortfolioSnapshot) -> None:
        total_notional = sum(
            p.quantity * p.current_price for p in portfolio.positions
        )
        if portfolio.equity > 0:
            leverage = total_notional / portfolio.equity
            if leverage >= self.limits.max_leverage_ratio:
                raise RiskLimitError(
                    f"Leverage ratio {leverage:.1f}x >= limit {self.limits.max_leverage_ratio}x"
                )

    def _check_var_limit(self, order: OrderEvent, portfolio: PortfolioSnapshot) -> None:
        if self._var_calculator is None:
            return
        try:
            var_pct = self._var_calculator.portfolio_var(
                portfolio, self.limits.var_confidence_level
            )
            if var_pct > self.limits.max_var_pct:
                raise RiskLimitError(
                    f"Portfolio VaR {var_pct:.2f}% > limit {self.limits.max_var_pct}%"
                )
        except Exception as e:
            logger.warning(f"VaR calculation failed: {e}")

    def _check_kill_switch(self, order: OrderEvent, portfolio: PortfolioSnapshot) -> None:
        if self._kill_switch is not None and self._kill_switch.is_triggered:
            raise RiskLimitError("Kill switch is active — trading halted")

        # Check consecutive losses
        if self._consecutive_losses >= self.limits.kill_switch_consecutive_losses:
            self._halted = True
            raise RiskLimitError(
                f"Consecutive losses ({self._consecutive_losses}) "
                f">= limit ({self.limits.kill_switch_consecutive_losses})"
            )

    def record_trade_result(self, pnl: float) -> None:
        """Track consecutive losses for kill switch."""
        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    def reset_daily(self, equity: float) -> None:
        self._daily_start_equity = equity
        self._daily_peak_equity = equity
        self._halted = False
        self._consecutive_losses = 0
        logger.info("Enterprise risk limits reset")

    @property
    def is_halted(self) -> bool:
        return self._halted
