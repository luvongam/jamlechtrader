"""Bollinger Band mean reversion strategy."""

from __future__ import annotations

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import MarketEvent, SignalEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.strategy.base import AbstractStrategy
from jamlechtrader.strategy.indicators import bollinger_bands


class MeanReversionStrategy(AbstractStrategy):
    """
    Bollinger Band mean reversion.

    BUY when price closes below the lower band.
    SELL when price closes above the upper band.
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0) -> None:
        super().__init__()
        self.period = period
        self.std_dev = std_dev

    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        bar: Bar = event.data
        self._update_history(bar)

        if len(self._bar_history) < self.period + 1:
            return []

        df = self.bars_df
        close = df["close"]
        bb = bollinger_bands(close, period=self.period, std=self.std_dev)

        if bb is None or bb.empty:
            return []

        # Column names from pandas_ta: BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
        lower_col = [c for c in bb.columns if c.startswith("BBL_")][0]
        upper_col = [c for c in bb.columns if c.startswith("BBU_")][0]

        lower = bb[lower_col].iloc[-1]
        upper = bb[upper_col].iloc[-1]
        current_close = bar.close

        signals = []

        if current_close < lower:
            signals.append(
                SignalEvent(
                    symbol=bar.symbol,
                    side=OrderSide.BUY,
                    strength=1.0,
                    timestamp=bar.timestamp,
                )
            )
        elif current_close > upper:
            signals.append(
                SignalEvent(
                    symbol=bar.symbol,
                    side=OrderSide.SELL,
                    strength=1.0,
                    timestamp=bar.timestamp,
                )
            )

        return signals
