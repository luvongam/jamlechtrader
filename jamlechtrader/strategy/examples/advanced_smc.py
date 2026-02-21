"""Advanced Smart Money strategy using professional SMC implementation."""

from jamlechtrader.analytics.enhanced_smc import SMCAnalyzer
from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import MarketEvent, SignalEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.strategy.base import AbstractStrategy


class AdvancedSmartMoneyStrategy(AbstractStrategy):
    """Professional SMC strategy with BOS, CHoCH, OB, and FVG."""

    def __init__(
        self, 
        swing_length: int = 10, 
        risk_threshold: float = 60.0,
        min_risk_reward: float = 2.0
    ) -> None:
        super().__init__()
        self.swing_length = swing_length
        self.risk_threshold = risk_threshold
        self.min_risk_reward = min_risk_reward
        self.smc = SMCAnalyzer(swing_length=swing_length)

    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        bar: Bar = event.data
        self._update_history(bar)

        if len(self._bar_history) < 50:
            return []

        df = self.bars_df
        
        # Analyze with all SMC indicators
        df_bos = self.smc.bos_choch(df)
        df_ob = self.smc.order_blocks(df)
        df_fvg = self.smc.fair_value_gaps(df)
        
        signals = []
        current_price = bar.close
        
        # Check for bullish setup
        bullish_obs = df_ob[df_ob["OB"] == 1].tail(3)
        if len(bullish_obs) > 0:
            latest_ob = bullish_obs.iloc[-1]
            if latest_ob["Bottom"] <= current_price <= latest_ob["Top"] * 1.005:
                # Check BOS confirmation
                recent_bos = df_bos[df_bos["BOS"] == 1].tail(1)
                if len(recent_bos) > 0:
                    signals.append(SignalEvent(
                        symbol=bar.symbol,
                        side=OrderSide.BUY,
                        strength=1.0,
                        timestamp=bar.timestamp,
                    ))
        
        # Check for bearish setup
        bearish_obs = df_ob[df_ob["OB"] == -1].tail(3)
        if len(bearish_obs) > 0:
            latest_ob = bearish_obs.iloc[-1]
            if latest_ob["Bottom"] * 0.995 <= current_price <= latest_ob["Top"]:
                # Check BOS confirmation
                recent_bos = df_bos[df_bos["BOS"] == -1].tail(1)
                if len(recent_bos) > 0:
                    signals.append(SignalEvent(
                        symbol=bar.symbol,
                        side=OrderSide.SELL,
                        strength=1.0,
                        timestamp=bar.timestamp,
                    ))

        return signals
