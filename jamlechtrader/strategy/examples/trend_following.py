"""Trend following strategy - rides strong trends with ADX filter."""

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import MarketEvent, SignalEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.strategy.base import AbstractStrategy
from jamlechtrader.strategy.indicators import ema


class TrendFollowingStrategy(AbstractStrategy):
    """EMA trend with momentum confirmation."""

    def __init__(self, ema_period: int = 50, momentum_period: int = 10) -> None:
        super().__init__()
        self.ema_period = ema_period
        self.momentum_period = momentum_period

    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        bar: Bar = event.data
        self._update_history(bar)

        if len(self._bar_history) < self.ema_period + self.momentum_period:
            return []

        df = self.bars_df
        close = df["close"]
        ema_val = ema(close, self.ema_period)
        momentum = close.pct_change(self.momentum_period)

        if ema_val.iloc[-1] is None or momentum.iloc[-1] is None:
            return []

        signals = []
        if close.iloc[-1] > ema_val.iloc[-1] and momentum.iloc[-1] > 0.01:
            signals.append(SignalEvent(
                symbol=bar.symbol,
                side=OrderSide.BUY,
                strength=1.0,
                timestamp=bar.timestamp,
            ))
        elif close.iloc[-1] < ema_val.iloc[-1] and momentum.iloc[-1] < -0.01:
            signals.append(SignalEvent(
                symbol=bar.symbol,
                side=OrderSide.SELL,
                strength=1.0,
                timestamp=bar.timestamp,
            ))

        return signals
