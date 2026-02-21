"""Scalping strategy - quick trades on small price movements."""

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import MarketEvent, SignalEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.strategy.base import AbstractStrategy
from jamlechtrader.strategy.indicators import ema, rsi


class ScalpingStrategy(AbstractStrategy):
    """Fast EMA crossover with RSI filter for scalping."""

    def __init__(self, fast: int = 5, slow: int = 13, rsi_period: int = 14) -> None:
        super().__init__()
        self.fast = fast
        self.slow = slow
        self.rsi_period = rsi_period

    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        bar: Bar = event.data
        self._update_history(bar)

        if len(self._bar_history) < max(self.slow, self.rsi_period) + 1:
            return []

        df = self.bars_df
        close = df["close"]
        fast_ema = ema(close, self.fast)
        slow_ema = ema(close, self.slow)
        rsi_val = rsi(close, self.rsi_period)

        if fast_ema.iloc[-2] is None or rsi_val.iloc[-1] is None:
            return []

        signals = []
        if fast_ema.iloc[-2] <= slow_ema.iloc[-2] and fast_ema.iloc[-1] > slow_ema.iloc[-1]:
            if rsi_val.iloc[-1] < 70:
                signals.append(SignalEvent(
                    symbol=bar.symbol,
                    side=OrderSide.BUY,
                    strength=1.0,
                    timestamp=bar.timestamp,
                ))
        elif fast_ema.iloc[-2] >= slow_ema.iloc[-2] and fast_ema.iloc[-1] < slow_ema.iloc[-1]:
            if rsi_val.iloc[-1] > 30:
                signals.append(SignalEvent(
                    symbol=bar.symbol,
                    side=OrderSide.SELL,
                    strength=1.0,
                    timestamp=bar.timestamp,
                ))

        return signals
