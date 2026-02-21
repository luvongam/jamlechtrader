"""Backtest engine — event loop over historical bars."""

from __future__ import annotations

from loguru import logger

from jamlechtrader.core.events import EventBus, FillEvent, MarketEvent, OrderEvent, SignalEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.data.base import AbstractDataHandler
from jamlechtrader.execution.simulated import SimulatedExecutor
from jamlechtrader.portfolio.portfolio import Portfolio
from jamlechtrader.portfolio.risk import RiskManager
from jamlechtrader.portfolio.sizing import PositionSizer
from jamlechtrader.strategy.base import AbstractStrategy


class BacktestEngine:
    """Runs a strategy over historical data with simulated execution."""

    def __init__(
        self,
        data_handler: AbstractDataHandler,
        strategy: AbstractStrategy,
        portfolio: Portfolio | None = None,
        executor: SimulatedExecutor | None = None,
        risk_manager: RiskManager | None = None,
        sizer: PositionSizer | None = None,
    ) -> None:
        self.data_handler = data_handler
        self.strategy = strategy
        self.portfolio = portfolio or Portfolio()
        self.executor = executor or SimulatedExecutor()
        self.risk_manager = risk_manager or RiskManager()
        self.sizer = sizer or PositionSizer()
        self.event_bus = EventBus()
        self._trade_log: list[dict] = []

    def run(self) -> dict:
        """Execute the backtest and return results."""
        logger.info(f"Starting backtest with {self.strategy.name}")

        self.data_handler.load()
        self.strategy.on_start()

        bar_count = 0
        signal_count = 0
        fill_count = 0

        for bar in self.data_handler.bars():
            bar_count += 1

            # Update market prices for existing positions
            self.portfolio.update_market_price(bar.symbol, bar.close)

            # Set current bar for the simulated executor
            self.executor.set_current_bar(bar)

            # Create market event and feed to strategy
            market_event = MarketEvent(
                symbol=bar.symbol, timestamp=bar.timestamp, data=bar
            )
            signals = self.strategy.on_bar(market_event)

            for signal in signals:
                signal_count += 1

                # Size the position
                quantity = self.sizer.calculate(equity=self.portfolio.equity, bar=bar)

                # Generate order from signal
                order = self.portfolio.generate_order(signal, quantity)
                if order is None:
                    continue

                # Risk check
                snapshot = self.portfolio.take_snapshot(bar.timestamp)
                checked_order = self.risk_manager.check_order(order, snapshot)
                if checked_order is None:
                    continue

                # Execute
                fill = self.executor.execute_order(checked_order)
                if fill is not None:
                    fill_count += 1
                    self.portfolio.on_fill(fill)

            # Take snapshot for equity curve
            self.portfolio.take_snapshot(bar.timestamp)

        self.strategy.on_stop()

        logger.info(
            f"Backtest complete: {bar_count} bars, {signal_count} signals, {fill_count} fills"
        )

        return {
            "bars": bar_count,
            "signals": signal_count,
            "fills": fill_count,
            "trades": len(self.portfolio.closed_trades),
            "final_equity": self.portfolio.equity,
            "total_return_pct": (
                (self.portfolio.equity - self.portfolio.initial_cash)
                / self.portfolio.initial_cash
                * 100
            ),
            "max_drawdown": max(
                (s.drawdown for s in self.portfolio.equity_curve), default=0.0
            ),
            "closed_trades": self.portfolio.closed_trades,
            "equity_curve": self.portfolio.equity_curve,
        }
