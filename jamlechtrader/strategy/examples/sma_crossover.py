"""SMA Crossover strategy — fast SMA crosses above/below slow SMA."""

from __future__ import annotations

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import MarketEvent, SignalEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.strategy.base import AbstractStrategy
from jamlechtrader.strategy.indicators import sma


class SMACrossoverStrategy(AbstractStrategy):
    """
    Simple Moving Average crossover.

    BUY when fast SMA crosses above slow SMA.
    SELL when fast SMA crosses below slow SMA.
    """

    def __init__(self, fast_period: int = 10, slow_period: int = 30) -> None:
        super().__init__()
        self.fast_period = fast_period
        self.slow_period = slow_period

    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        bar: Bar = event.data
        self._update_history(bar)

        if len(self._bar_history) < self.slow_period + 1:
            return []

        df = self.bars_df
        close = df["close"]
        fast_sma = sma(close, self.fast_period)
        slow_sma = sma(close, self.slow_period)

        if fast_sma.iloc[-2] is None or slow_sma.iloc[-2] is None:
            return []

        # Crossover detection
        prev_fast = fast_sma.iloc[-2]
        prev_slow = slow_sma.iloc[-2]
        curr_fast = fast_sma.iloc[-1]
        curr_slow = slow_sma.iloc[-1]

        signals = []

        if prev_fast <= prev_slow and curr_fast > curr_slow:
            signals.append(
                SignalEvent(
                    symbol=bar.symbol,
                    side=OrderSide.BUY,
                    strength=1.0,
                    timestamp=bar.timestamp,
                )
            )
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            signals.append(
                SignalEvent(
                    symbol=bar.symbol,
                    side=OrderSide.SELL,
                    strength=1.0,
                    timestamp=bar.timestamp,
                )
            )

        return signals
