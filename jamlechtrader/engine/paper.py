"""Paper trading engine — live MT5 data with simulated fills."""

from __future__ import annotations

import time
from datetime import datetime

from loguru import logger

from jamlechtrader.core.enums import Timeframe
from jamlechtrader.core.events import EventBus, MarketEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.execution.paper import PaperExecutor
from jamlechtrader.mt5.connection import MT5Connection
from jamlechtrader.mt5.data import MT5Data
from jamlechtrader.portfolio.portfolio import Portfolio
from jamlechtrader.portfolio.risk import RiskManager
from jamlechtrader.portfolio.sizing import PositionSizer
from jamlechtrader.strategy.base import AbstractStrategy


class PaperEngine:
    """Runs a strategy on live MT5 data with paper (virtual) execution."""

    def __init__(
        self,
        connection: MT5Connection,
        strategy: AbstractStrategy,
        symbol: str,
        timeframe: Timeframe,
        portfolio: Portfolio | None = None,
        executor: PaperExecutor | None = None,
        risk_manager: RiskManager | None = None,
        sizer: PositionSizer | None = None,
    ) -> None:
        self.connection = connection
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.portfolio = portfolio or Portfolio()
        self.executor = executor or PaperExecutor()
        self.risk_manager = risk_manager or RiskManager()
        self.sizer = sizer or PositionSizer()
        self.event_bus = EventBus()
        self._mt5_data = MT5Data()
        self._running = False
        self._last_bar_time: datetime | None = None

    def run(self, duration_seconds: int | None = None) -> dict:
        """Run paper trading. Blocks until stop() or duration expires."""
        if not self.connection.is_connected:
            if not self.connection.connect():
                raise RuntimeError("Failed to connect to MT5")

        self._running = True
        self.strategy.on_start()
        start_time = time.time()

        logger.info(f"Paper engine started: {self.symbol} {self.timeframe.value}")

        try:
            while self._running:
                if duration_seconds and (time.time() - start_time) > duration_seconds:
                    break

                bars = self._mt5_data.get_latest_bars(self.symbol, self.timeframe, count=1)
                if not bars:
                    time.sleep(1)
                    continue

                current_bar = bars[-1]

                # Only process new bars
                if self._last_bar_time and current_bar.timestamp <= self._last_bar_time:
                    time.sleep(1)
                    continue

                self._last_bar_time = current_bar.timestamp

                # Update tick for paper executor
                tick = self._mt5_data.get_current_tick(self.symbol)
                if tick:
                    self.executor.set_current_tick(tick)

                # Update market prices
                self.portfolio.update_market_price(self.symbol, current_bar.close)

                # Feed to strategy
                market_event = MarketEvent(
                    symbol=self.symbol,
                    timestamp=current_bar.timestamp,
                    data=current_bar,
                )
                signals = self.strategy.on_bar(market_event)

                for signal in signals:
                    quantity = self.sizer.calculate(
                        equity=self.portfolio.equity, bar=current_bar
                    )
                    order = self.portfolio.generate_order(signal, quantity)
                    if order is None:
                        continue

                    snapshot = self.portfolio.take_snapshot(current_bar.timestamp)
                    checked_order = self.risk_manager.check_order(order, snapshot)
                    if checked_order is None:
                        continue

                    fill = self.executor.execute_order(checked_order)
                    if fill is not None:
                        self.portfolio.on_fill(fill)

                self.portfolio.take_snapshot(current_bar.timestamp)
                time.sleep(1)

        finally:
            self.strategy.on_stop()

        logger.info("Paper engine stopped")
        return {
            "trades": len(self.portfolio.closed_trades),
            "final_equity": self.portfolio.equity,
            "fills": len(self.executor.fill_log),
            "closed_trades": self.portfolio.closed_trades,
        }

    def stop(self) -> None:
        self._running = False
