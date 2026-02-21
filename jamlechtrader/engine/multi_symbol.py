"""Multi-symbol trading engine."""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger

from jamlechtrader.core.enums import Timeframe
from jamlechtrader.core.events import MarketEvent
from jamlechtrader.data.live_feed import LiveDataFeed
from jamlechtrader.execution.mt5_executor import MT5Executor
from jamlechtrader.portfolio.portfolio import Portfolio
from jamlechtrader.portfolio.sizing import PositionSizer

if TYPE_CHECKING:
    from jamlechtrader.mt5.connection import MT5Connection
    from jamlechtrader.strategy.base import AbstractStrategy


class MultiSymbolEngine:
    """Trade multiple symbols with one or more strategies."""

    def __init__(
        self,
        connection: MT5Connection,
        symbols: list[str],
        strategies: dict[str, AbstractStrategy],
        timeframe: Timeframe = Timeframe.M5,
        initial_cash: float = 10000.0,
    ) -> None:
        self.connection = connection
        self.symbols = symbols
        self.strategies = strategies
        self.timeframe = timeframe
        self.portfolio = Portfolio(initial_cash=initial_cash)
        self.executor = MT5Executor(connection)
        self.sizer = PositionSizer(method="fixed", fixed_lot=0.01)
        self.feeds = {sym: LiveDataFeed(connection, sym, timeframe) for sym in symbols}

    def run(self, duration_seconds: int = 3600) -> dict:
        """Run multi-symbol trading."""
        logger.info(f"Starting multi-symbol trading: {self.symbols}")
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            for symbol, feed in self.feeds.items():
                bar = feed.get_latest_bar()
                if bar is None:
                    continue

                event = MarketEvent(data=bar)
                
                for strategy in self.strategies.values():
                    signals = strategy.on_bar(event)
                    
                    for signal in signals:
                        position = self.portfolio.get_position(signal.symbol)
                        lot_size = self.sizer.calculate(signal, self.portfolio)
                        
                        if signal.side.value == "BUY" and (position is None or position.quantity <= 0):
                            self.executor.execute_order(signal.symbol, "BUY", lot_size)
                        elif signal.side.value == "SELL" and (position is None or position.quantity >= 0):
                            self.executor.execute_order(signal.symbol, "SELL", lot_size)

            time.sleep(1)

        return {
            "symbols": self.symbols,
            "final_equity": self.portfolio.equity,
            "trades": len(self.portfolio.closed_trades),
        }
