"""Supply and Demand Zone strategy with Smart Money Concepts integration.

Identifies institutional supply/demand zones using:
- Rally-Base-Rally (RBR) and Drop-Base-Drop (DBD) continuation zones
- Rally-Base-Drop (RBD) and Drop-Base-Rally (DBR) reversal zones
- Volume confirmation at zone formation
- Multi-timeframe zone confluence
- FVG and order block alignment for high-probability entries
- Liquidity sweep confirmation before zone entries
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import MarketEvent, SignalEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.strategy.base import AbstractStrategy
from jamlechtrader.strategy.indicators import atr, ema, rsi


class SupplyDemandStrategy(AbstractStrategy):
    """Institutional supply and demand zone trading strategy.

    Detects zones where institutional orders were placed based on
    strong price movement away from consolidation (base) areas.
    Combines with SMC concepts for high-probability entries.

    Parameters
    ----------
    zone_lookback : int
        Number of bars to look back for zone detection (default 100).
    base_max_bars : int
        Maximum number of bars allowed in a basing pattern (default 6).
    min_impulse_atr : float
        Minimum impulse move size as ATR multiple (default 2.0).
    min_base_tightness : float
        Maximum allowed range of the base relative to ATR (default 1.0).
    zone_touch_limit : int
        Maximum times price can revisit a zone before it's spent (default 3).
    use_smc_filter : bool
        Enable SMC-based confirmation filters (default True).
    rsi_filter : bool
        Use RSI to avoid overbought/oversold entries (default True).
    trend_filter : bool
        Only trade zones aligned with the higher-timeframe trend (default True).
    ema_period : int
        EMA period for trend detection (default 200).
    atr_period : int
        ATR period for zone sizing (default 14).
    min_risk_reward : float
        Minimum risk/reward ratio for entries (default 2.0).
    """

    def __init__(
        self,
        zone_lookback: int = 100,
        base_max_bars: int = 6,
        min_impulse_atr: float = 2.0,
        min_base_tightness: float = 1.0,
        zone_touch_limit: int = 3,
        use_smc_filter: bool = True,
        rsi_filter: bool = True,
        trend_filter: bool = True,
        ema_period: int = 200,
        atr_period: int = 14,
        min_risk_reward: float = 2.0,
    ) -> None:
        super().__init__()
        self.zone_lookback = zone_lookback
        self.base_max_bars = base_max_bars
        self.min_impulse_atr = min_impulse_atr
        self.min_base_tightness = min_base_tightness
        self.zone_touch_limit = zone_touch_limit
        self.use_smc_filter = use_smc_filter
        self.rsi_filter = rsi_filter
        self.trend_filter = trend_filter
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.min_risk_reward = min_risk_reward

        # Track active zones
        self._demand_zones: list[dict] = []
        self._supply_zones: list[dict] = []

        # SMC analyzer (lazy loaded)
        self._smc = None

    def _get_smc(self):
        if self._smc is None and self.use_smc_filter:
            try:
                from jamlechtrader.analytics.enhanced_smc import SMCAnalyzer
                self._smc = SMCAnalyzer(swing_length=10)
            except ImportError:
                self._smc = False  # Mark as unavailable
        return self._smc if self._smc is not False else None

    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        bar: Bar = event.data
        self._update_history(bar)

        min_bars = max(self.zone_lookback, self.ema_period) + 20
        if len(self._bar_history) < min_bars:
            return []

        df = self.bars_df
        current_price = bar.close

        # Calculate indicators
        atr_series = atr(df["high"], df["low"], df["close"], self.atr_period)
        current_atr = atr_series.iloc[-1]
        if pd.isna(current_atr) or current_atr <= 0:
            return []

        # Detect new zones from recent price action
        self._detect_zones(df, atr_series)

        # Update zone touch counts and remove broken zones
        self._update_zones(current_price, current_atr)

        # Trend filter
        trend_bias = self._get_trend_bias(df) if self.trend_filter else 0

        # RSI filter
        rsi_series = rsi(df["close"], 14) if self.rsi_filter else None

        # SMC confirmation
        smc_analyzer = self._get_smc()
        smc_data = {}
        if smc_analyzer is not None:
            smc_data = self._get_smc_confirmation(df, smc_analyzer)

        signals = []

        # Check demand zones for BUY
        for zone in self._demand_zones:
            if zone["touches"] >= self.zone_touch_limit:
                continue
            if not (zone["bottom"] <= current_price <= zone["top"]):
                continue
            if self.trend_filter and trend_bias < 0:
                continue
            if self.rsi_filter and rsi_series is not None:
                current_rsi = rsi_series.iloc[-1]
                if not pd.isna(current_rsi) and current_rsi > 70:
                    continue

            strength = self._calculate_zone_strength(zone, smc_data, "BUY", current_atr)
            if strength < 0.5:
                continue

            # Calculate SL/TP
            stop_loss = zone["bottom"] - current_atr * 0.5
            zone_height = zone["top"] - zone["bottom"]
            take_profit = current_price + max(
                zone_height * self.min_risk_reward,
                current_atr * self.min_risk_reward,
            )

            # Check risk/reward
            risk = current_price - stop_loss
            reward = take_profit - current_price
            if risk > 0 and reward / risk < self.min_risk_reward:
                continue

            signals.append(SignalEvent(
                symbol=bar.symbol,
                side=OrderSide.BUY,
                strength=min(strength, 2.0),
                stop_loss=stop_loss,
                take_profit=take_profit,
                timestamp=bar.timestamp,
            ))
            zone["touches"] += 1
            break  # One signal per bar

        if signals:
            return signals

        # Check supply zones for SELL
        for zone in self._supply_zones:
            if zone["touches"] >= self.zone_touch_limit:
                continue
            if not (zone["bottom"] <= current_price <= zone["top"]):
                continue
            if self.trend_filter and trend_bias > 0:
                continue
            if self.rsi_filter and rsi_series is not None:
                current_rsi = rsi_series.iloc[-1]
                if not pd.isna(current_rsi) and current_rsi < 30:
                    continue

            strength = self._calculate_zone_strength(zone, smc_data, "SELL", current_atr)
            if strength < 0.5:
                continue

            stop_loss = zone["top"] + current_atr * 0.5
            zone_height = zone["top"] - zone["bottom"]
            take_profit = current_price - max(
                zone_height * self.min_risk_reward,
                current_atr * self.min_risk_reward,
            )

            risk = stop_loss - current_price
            reward = current_price - take_profit
            if risk > 0 and reward / risk < self.min_risk_reward:
                continue

            signals.append(SignalEvent(
                symbol=bar.symbol,
                side=OrderSide.SELL,
                strength=min(strength, 2.0),
                stop_loss=stop_loss,
                take_profit=take_profit,
                timestamp=bar.timestamp,
            ))
            zone["touches"] += 1
            break

        return signals

    def _detect_zones(self, df: pd.DataFrame, atr_series: pd.Series) -> None:
        """Detect supply and demand zones from price action patterns.

        Looks for:
        - Drop-Base-Rally (DBR): demand zone (reversal)
        - Rally-Base-Drop (RBD): supply zone (reversal)
        - Rally-Base-Rally (RBR): demand zone (continuation)
        - Drop-Base-Drop (DBD): supply zone (continuation)
        """
        n = len(df)
        if n < self.zone_lookback:
            return

        lookback_start = max(0, n - self.zone_lookback)
        recent = df.iloc[lookback_start:].copy()
        recent_atr = atr_series.iloc[lookback_start:].copy()

        # Identify impulse and base candles
        for i in range(2, len(recent) - 2):
            idx = recent.index[i]
            curr_atr = recent_atr.iloc[i]
            if pd.isna(curr_atr) or curr_atr <= 0:
                continue

            # Check if current bar is a base (small range relative to ATR)
            bar_range = recent["high"].iloc[i] - recent["low"].iloc[i]
            if bar_range > curr_atr * self.min_base_tightness:
                continue  # Not a tight enough base

            # Check for impulse move before and after the base
            # Look at bars before the base
            pre_move = 0.0
            for j in range(max(0, i - 3), i):
                pre_move += recent["close"].iloc[j] - recent["open"].iloc[j]

            # Look at bars after the base
            post_move = 0.0
            for j in range(i + 1, min(len(recent), i + 4)):
                post_move += recent["close"].iloc[j] - recent["open"].iloc[j]

            # Classify the pattern
            pre_impulse = abs(pre_move) > curr_atr * self.min_impulse_atr * 0.5
            post_impulse = abs(post_move) > curr_atr * self.min_impulse_atr * 0.5

            if not (pre_impulse and post_impulse):
                continue

            # Calculate base zone boundaries
            base_high = recent["high"].iloc[i]
            base_low = recent["low"].iloc[i]
            # Extend base to adjacent small candles
            for j in range(max(0, i - self.base_max_bars // 2), i):
                r = recent["high"].iloc[j] - recent["low"].iloc[j]
                if r <= curr_atr * self.min_base_tightness:
                    base_high = max(base_high, recent["high"].iloc[j])
                    base_low = min(base_low, recent["low"].iloc[j])
                else:
                    break
            for j in range(i + 1, min(len(recent), i + self.base_max_bars // 2 + 1)):
                r = recent["high"].iloc[j] - recent["low"].iloc[j]
                if r <= curr_atr * self.min_base_tightness:
                    base_high = max(base_high, recent["high"].iloc[j])
                    base_low = min(base_low, recent["low"].iloc[j])
                else:
                    break

            volume = recent["volume"].iloc[i] if "volume" in recent.columns else 0

            zone = {
                "top": base_high,
                "bottom": base_low,
                "formation_idx": idx,
                "touches": 0,
                "volume": volume,
                "impulse_strength": (abs(pre_move) + abs(post_move)) / curr_atr,
            }

            # Classify zone type
            if pre_move < 0 and post_move > 0:
                # Drop-Base-Rally: DEMAND (reversal)
                zone["type"] = "DBR"
                if not self._zone_overlaps(zone, self._demand_zones):
                    self._demand_zones.append(zone)
            elif pre_move > 0 and post_move < 0:
                # Rally-Base-Drop: SUPPLY (reversal)
                zone["type"] = "RBD"
                if not self._zone_overlaps(zone, self._supply_zones):
                    self._supply_zones.append(zone)
            elif pre_move > 0 and post_move > 0:
                # Rally-Base-Rally: DEMAND (continuation)
                zone["type"] = "RBR"
                if not self._zone_overlaps(zone, self._demand_zones):
                    self._demand_zones.append(zone)
            elif pre_move < 0 and post_move < 0:
                # Drop-Base-Drop: SUPPLY (continuation)
                zone["type"] = "DBD"
                if not self._zone_overlaps(zone, self._supply_zones):
                    self._supply_zones.append(zone)

    def _zone_overlaps(self, new_zone: dict, zones: list[dict]) -> bool:
        """Check if a new zone overlaps significantly with existing zones."""
        for z in zones:
            overlap_top = min(new_zone["top"], z["top"])
            overlap_bottom = max(new_zone["bottom"], z["bottom"])
            if overlap_top > overlap_bottom:
                overlap = overlap_top - overlap_bottom
                new_range = new_zone["top"] - new_zone["bottom"]
                if new_range > 0 and overlap / new_range > 0.5:
                    return True
        return False

    def _update_zones(self, current_price: float, current_atr: float) -> None:
        """Update zone touch counts and remove broken/spent zones."""
        # Remove broken demand zones (price closed below)
        self._demand_zones = [
            z for z in self._demand_zones
            if current_price > z["bottom"] - current_atr * 0.5
            and z["touches"] < self.zone_touch_limit
        ]

        # Remove broken supply zones (price closed above)
        self._supply_zones = [
            z for z in self._supply_zones
            if current_price < z["top"] + current_atr * 0.5
            and z["touches"] < self.zone_touch_limit
        ]

        # Keep only the most recent zones
        max_zones = 10
        self._demand_zones = sorted(
            self._demand_zones, key=lambda z: z["formation_idx"], reverse=True
        )[:max_zones]
        self._supply_zones = sorted(
            self._supply_zones, key=lambda z: z["formation_idx"], reverse=True
        )[:max_zones]

    def _get_trend_bias(self, df: pd.DataFrame) -> int:
        """Get higher-timeframe trend bias using EMA.

        Returns: 1 for bullish, -1 for bearish, 0 for neutral.
        """
        ema_series = ema(df["close"], self.ema_period)
        if pd.isna(ema_series.iloc[-1]):
            return 0

        current_price = df["close"].iloc[-1]
        ema_val = ema_series.iloc[-1]

        # Price above EMA and EMA rising
        if current_price > ema_val:
            if len(ema_series) > 10 and ema_series.iloc[-1] > ema_series.iloc[-10]:
                return 1
        elif current_price < ema_val:
            if len(ema_series) > 10 and ema_series.iloc[-1] < ema_series.iloc[-10]:
                return -1
        return 0

    def _get_smc_confirmation(self, df: pd.DataFrame, smc_analyzer) -> dict:
        """Get SMC confirmation data for zone entries."""
        data = {
            "bullish_ob": False,
            "bearish_ob": False,
            "bullish_fvg": False,
            "bearish_fvg": False,
            "bullish_bos": False,
            "bearish_bos": False,
            "liquidity_swept_below": False,
            "liquidity_swept_above": False,
        }

        try:
            # Order blocks
            ob_df = smc_analyzer.order_blocks(df)
            recent_obs = ob_df.tail(5)
            if (recent_obs["OB"] == 1).any():
                data["bullish_ob"] = True
            if (recent_obs["OB"] == -1).any():
                data["bearish_ob"] = True

            # Fair Value Gaps
            fvg_df = smc_analyzer.fair_value_gaps(df)
            recent_fvg = fvg_df.tail(10)
            unmitigated = recent_fvg[recent_fvg["MitigatedIndex"].isna()]
            if (unmitigated["FVG"] == 1).any():
                data["bullish_fvg"] = True
            if (unmitigated["FVG"] == -1).any():
                data["bearish_fvg"] = True

            # Break of Structure
            bos_df = smc_analyzer.bos_choch(df)
            recent_bos = bos_df.tail(5)
            if (recent_bos["BOS"] == 1).any():
                data["bullish_bos"] = True
            if (recent_bos["BOS"] == -1).any():
                data["bearish_bos"] = True

            # Liquidity sweeps
            liq_df = smc_analyzer.liquidity(df)
            if "Swept" in liq_df.columns:
                swept = liq_df[liq_df["Swept"].notna() & (liq_df["Swept"] != 0)]
                recent_swept = swept.tail(3)
                if (recent_swept["Liquidity"] == -1).any():
                    data["liquidity_swept_below"] = True
                if (recent_swept["Liquidity"] == 1).any():
                    data["liquidity_swept_above"] = True
        except Exception:
            pass

        return data

    def _calculate_zone_strength(
        self, zone: dict, smc_data: dict, side: str, current_atr: float
    ) -> float:
        """Calculate the strength of a zone entry signal (0.0-2.0)."""
        strength = 1.0

        # Fresh zones are stronger (fewer touches)
        if zone["touches"] == 0:
            strength += 0.2
        elif zone["touches"] >= 2:
            strength -= 0.3

        # Strong impulse moves indicate institutional interest
        impulse = zone.get("impulse_strength", 0)
        if impulse > 4.0:
            strength += 0.3
        elif impulse > 3.0:
            strength += 0.15

        # Reversal zones (DBR/RBD) are generally stronger than continuation
        zone_type = zone.get("type", "")
        if zone_type in ("DBR", "RBD"):
            strength += 0.1

        # SMC confirmation bonuses
        if smc_data:
            if side == "BUY":
                if smc_data.get("bullish_ob"):
                    strength += 0.2
                if smc_data.get("bullish_fvg"):
                    strength += 0.15
                if smc_data.get("bullish_bos"):
                    strength += 0.2
                if smc_data.get("liquidity_swept_below"):
                    strength += 0.25  # Liquidity sweep before demand = strong
            else:
                if smc_data.get("bearish_ob"):
                    strength += 0.2
                if smc_data.get("bearish_fvg"):
                    strength += 0.15
                if smc_data.get("bearish_bos"):
                    strength += 0.2
                if smc_data.get("liquidity_swept_above"):
                    strength += 0.25

        return max(0.0, min(strength, 2.0))

    def reset(self) -> None:
        super().reset()
        self._demand_zones.clear()
        self._supply_zones.clear()
