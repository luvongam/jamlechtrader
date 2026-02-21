"""Breakout strategy - trades when price breaks support/resistance levels."""

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import MarketEvent, SignalEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.strategy.base import AbstractStrategy


class BreakoutStrategy(AbstractStrategy):
    """Trade breakouts above/below recent highs/lows."""

    def __init__(self, lookback: int = 20, threshold: float = 0.001) -> None:
        super().__init__()
        self.lookback = lookback
        self.threshold = threshold

    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        bar: Bar = event.data
        self._update_history(bar)

        if len(self._bar_history) < self.lookback + 1:
            return []

        df = self.bars_df.iloc[-(self.lookback + 1):-1]
        high = df["high"].max()
        low = df["low"].min()

        signals = []
        if bar.close > high * (1 + self.threshold):
            signals.append(SignalEvent(
                symbol=bar.symbol,
                side=OrderSide.BUY,
                strength=1.0,
                timestamp=bar.timestamp,
            ))
        elif bar.close < low * (1 - self.threshold):
            signals.append(SignalEvent(
                symbol=bar.symbol,
                side=OrderSide.SELL,
                strength=1.0,
                timestamp=bar.timestamp,
            ))

        return signals
