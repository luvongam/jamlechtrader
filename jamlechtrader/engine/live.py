"""Live trading engine — real MT5 data and execution."""

from __future__ import annotations

import time
from datetime import datetime

from loguru import logger

from jamlechtrader.core.enums import Timeframe
from jamlechtrader.core.events import EventBus, MarketEvent
from jamlechtrader.execution.mt5_executor import MT5LiveExecutor
from jamlechtrader.mt5.connection import MT5Connection
from jamlechtrader.mt5.data import MT5Data
from jamlechtrader.portfolio.portfolio import Portfolio
from jamlechtrader.portfolio.risk import RiskManager
from jamlechtrader.portfolio.sizing import PositionSizer
from jamlechtrader.strategy.base import AbstractStrategy


class LiveEngine:
    """Runs a strategy with live MT5 data and real order execution."""

    def __init__(
        self,
        connection: MT5Connection,
        strategy: AbstractStrategy,
        symbol: str,
        timeframe: Timeframe,
        portfolio: Portfolio | None = None,
        executor: MT5LiveExecutor | None = None,
        risk_manager: RiskManager | None = None,
        sizer: PositionSizer | None = None,
    ) -> None:
        self.connection = connection
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.portfolio = portfolio or Portfolio()
        self.executor = executor or MT5LiveExecutor()
        self.risk_manager = risk_manager or RiskManager()
        self.sizer = sizer or PositionSizer()
        self.event_bus = EventBus()
        self._mt5_data = MT5Data()
        self._running = False
        self._last_bar_time: datetime | None = None

    def run(self) -> None:
        """Start live trading. Blocks until stop() is called."""
        if not self.connection.is_connected:
            if not self.connection.connect():
                raise RuntimeError("Failed to connect to MT5")

        self._running = True
        self.strategy.on_start()

        logger.info(
            f"LIVE engine started: {self.symbol} {self.timeframe.value} — USE WITH CAUTION"
        )

        try:
            while self._running:
                bars = self._mt5_data.get_latest_bars(
                    self.symbol, self.timeframe, count=1
                )
                if not bars:
                    time.sleep(1)
                    continue

                current_bar = bars[-1]

                if (
                    self._last_bar_time
                    and current_bar.timestamp <= self._last_bar_time
                ):
                    time.sleep(1)
                    continue

                self._last_bar_time = current_bar.timestamp
                logger.debug(f"New bar: {current_bar.timestamp} O={current_bar.open} C={current_bar.close}")

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
                        logger.info(
                            f"LIVE FILL: {fill.side.value} {fill.quantity} {fill.symbol} @ {fill.price}"
                        )

                self.portfolio.take_snapshot(current_bar.timestamp)
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Live engine interrupted by user")
        finally:
            self.strategy.on_stop()
            logger.info("Live engine stopped")

    def stop(self) -> None:
        self._running = False
