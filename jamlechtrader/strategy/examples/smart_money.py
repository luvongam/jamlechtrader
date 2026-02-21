"""Smart Money Concepts trading strategy."""

from jamlechtrader.analytics.smart_money import SmartMoneyAnalyzer
from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import MarketEvent, SignalEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.strategy.base import AbstractStrategy


class SmartMoneyStrategy(AbstractStrategy):
    """Trade based on institutional Smart Money Concepts."""

    def __init__(self, lookback: int = 50, risk_threshold: float = 60.0) -> None:
        super().__init__()
        self.lookback = lookback
        self.risk_threshold = risk_threshold
        self.smc_analyzer = SmartMoneyAnalyzer(lookback=lookback)

    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        bar: Bar = event.data
        self._update_history(bar)

        if len(self._bar_history) < self.lookback:
            return []

        df = self.bars_df
        
        # Analyze smart money patterns
        analysis = self.smc_analyzer.analyze(df)
        
        # Skip if risk is too high
        if analysis.get("risk_score", 100) > self.risk_threshold:
            return []

        signals = []
        bias = analysis.get("bias", "neutral")
        current_price = bar.close
        
        # Get entry zones
        entry_zones = self.smc_analyzer.get_entry_zones(df)
        
        # Bullish setup: price near bullish order block + bullish bias
        if bias == "bullish":
            for zone in entry_zones.get("bullish_zones", []):
                if abs(current_price - zone["price"]) / current_price < 0.005:  # Within 0.5%
                    signals.append(SignalEvent(
                        symbol=bar.symbol,
                        side=OrderSide.BUY,
                        strength=zone["strength"],
                        timestamp=bar.timestamp,
                    ))
                    break
        
        # Bearish setup: price near bearish order block + bearish bias
        elif bias == "bearish":
            for zone in entry_zones.get("bearish_zones", []):
                if abs(current_price - zone["price"]) / current_price < 0.005:
                    signals.append(SignalEvent(
                        symbol=bar.symbol,
                        side=OrderSide.SELL,
                        strength=zone["strength"],
                        timestamp=bar.timestamp,
                    ))
                    break

        return signals
