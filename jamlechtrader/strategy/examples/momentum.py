"""RSI + ADX momentum / trend following strategy."""

from __future__ import annotations

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import MarketEvent, SignalEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.strategy.base import AbstractStrategy
from jamlechtrader.strategy.indicators import adx, rsi


class MomentumStrategy(AbstractStrategy):
    """
    RSI + ADX trend following.

    BUY when RSI < oversold AND ADX > threshold (strong trend).
    SELL when RSI > overbought AND ADX > threshold.
    """

    def __init__(
        self,
        rsi_period: int = 14,
        adx_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        adx_threshold: float = 25.0,
    ) -> None:
        super().__init__()
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.adx_threshold = adx_threshold

    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        bar: Bar = event.data
        self._update_history(bar)

        min_bars = max(self.rsi_period, self.adx_period) + 2
        if len(self._bar_history) < min_bars:
            return []

        df = self.bars_df
        close = df["close"]
        high = df["high"]
        low = df["low"]

        rsi_series = rsi(close, period=self.rsi_period)
        adx_df = adx(high, low, close, period=self.adx_period)

        if rsi_series is None or adx_df is None or adx_df.empty:
            return []

        adx_col = [c for c in adx_df.columns if c.startswith("ADX_")][0]

        current_rsi = rsi_series.iloc[-1]
        current_adx = adx_df[adx_col].iloc[-1]

        if current_rsi is None or current_adx is None:
            return []

        signals = []

        if current_rsi < self.rsi_oversold and current_adx > self.adx_threshold:
            signals.append(
                SignalEvent(
                    symbol=bar.symbol,
                    side=OrderSide.BUY,
                    strength=current_adx / 100.0,
                    timestamp=bar.timestamp,
                )
            )
        elif current_rsi > self.rsi_overbought and current_adx > self.adx_threshold:
            signals.append(
                SignalEvent(
                    symbol=bar.symbol,
                    side=OrderSide.SELL,
                    strength=current_adx / 100.0,
                    timestamp=bar.timestamp,
                )
            )

        return signals
