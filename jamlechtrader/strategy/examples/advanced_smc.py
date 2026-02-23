"""Advanced Smart Money strategy using professional SMC implementation."""

import pandas as pd

from jamlechtrader.analytics.enhanced_smc import SMCAnalyzer
from jamlechtrader.core.constants import SMC_RETRACEMENT_DEEP_THRESHOLD
from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import MarketEvent, SignalEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.strategy.base import AbstractStrategy


class AdvancedSmartMoneyStrategy(AbstractStrategy):
    """Professional SMC strategy with BOS, CHoCH, OB, and FVG.

    Uses enriched data from the ``smartmoneyconcepts`` package:
    - Filters OBs by ``Percentage`` (volume quality gate)
    - Targets unmitigated FVGs (``MitigatedIndex`` is NaN)
    - Checks swept liquidity for confirmation
    - Skips deep-retracement setups
    """

    def __init__(
        self,
        swing_length: int = 10,
        risk_threshold: float = 60.0,
        min_risk_reward: float = 2.0,
        ob_min_percentage: float = 30.0,
    ) -> None:
        super().__init__()
        self.swing_length = swing_length
        self.risk_threshold = risk_threshold
        self.min_risk_reward = min_risk_reward
        self.ob_min_percentage = ob_min_percentage
        self.smc = SMCAnalyzer(swing_length=swing_length)

    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        bar: Bar = event.data
        self._update_history(bar)

        if len(self._bar_history) < 50:
            return []

        df = self.bars_df

        # Skip deep-retracement setups
        ret_df = self.smc.retracements(df)
        if "CurrentRetracement%" in ret_df.columns:
            last_ret = ret_df["CurrentRetracement%"].dropna()
            if len(last_ret) > 0 and last_ret.iloc[-1] > SMC_RETRACEMENT_DEEP_THRESHOLD:
                return []

        # Analyze with all SMC indicators
        df_bos = self.smc.bos_choch(df)
        df_ob = self.smc.order_blocks(df)
        df_fvg = self.smc.fair_value_gaps(df)
        df_liq = self.smc.liquidity(df)

        signals = []
        current_price = bar.close

        # Filter OBs by volume quality gate
        bullish_obs = df_ob[df_ob["OB"] == 1]
        if "Percentage" in bullish_obs.columns:
            bullish_obs = bullish_obs[bullish_obs["Percentage"].fillna(0) > self.ob_min_percentage]
        bullish_obs = bullish_obs.tail(3)

        if len(bullish_obs) > 0:
            latest_ob = bullish_obs.iloc[-1]
            if latest_ob["Bottom"] <= current_price <= latest_ob["Top"] * 1.005:
                # Check BOS confirmation
                recent_bos = df_bos[df_bos["BOS"] == 1].tail(1)
                # Check for unmitigated bullish FVGs as targets
                unmitigated_fvgs = df_fvg[
                    (df_fvg["FVG"] == 1) & (df_fvg["MitigatedIndex"].isna())
                ]
                # Check swept liquidity for confirmation
                swept_liq = df_liq[
                    (df_liq["Liquidity"] == -1)
                    & ("Swept" in df_liq.columns)
                    & (df_liq.get("Swept", pd.Series(dtype=float)).fillna(0) != 0)
                ] if "Swept" in df_liq.columns else pd.DataFrame()

                if len(recent_bos) > 0:
                    strength = 1.0
                    if len(swept_liq) > 0:
                        strength = min(strength + 0.3, 2.0)
                    signals.append(SignalEvent(
                        symbol=bar.symbol,
                        side=OrderSide.BUY,
                        strength=strength,
                        timestamp=bar.timestamp,
                    ))

        # Check for bearish setup
        bearish_obs = df_ob[df_ob["OB"] == -1]
        if "Percentage" in bearish_obs.columns:
            bearish_obs = bearish_obs[bearish_obs["Percentage"].fillna(0) > self.ob_min_percentage]
        bearish_obs = bearish_obs.tail(3)

        if len(bearish_obs) > 0:
            latest_ob = bearish_obs.iloc[-1]
            if latest_ob["Bottom"] * 0.995 <= current_price <= latest_ob["Top"]:
                recent_bos = df_bos[df_bos["BOS"] == -1].tail(1)
                swept_liq = df_liq[
                    (df_liq["Liquidity"] == 1)
                    & (df_liq.get("Swept", pd.Series(dtype=float)).fillna(0) != 0)
                ] if "Swept" in df_liq.columns else pd.DataFrame()

                if len(recent_bos) > 0:
                    strength = 1.0
                    if len(swept_liq) > 0:
                        strength = min(strength + 0.3, 2.0)
                    signals.append(SignalEvent(
                        symbol=bar.symbol,
                        side=OrderSide.SELL,
                        strength=strength,
                        timestamp=bar.timestamp,
                    ))

        return signals
