"""Smart Money risk manager with SMC integration."""

from __future__ import annotations

import pandas as pd
from loguru import logger

from jamlechtrader.analytics.enhanced_smc import SMCAnalyzer
from jamlechtrader.analytics.smart_money import SmartMoneyAnalyzer
from jamlechtrader.core.constants import SMC_DEFAULT_LOOKBACK, SMC_RETRACEMENT_DEEP_THRESHOLD
from jamlechtrader.portfolio.risk import RiskLimits, RiskManager


class SmartMoneyRiskManager(RiskManager):
    """Risk manager enhanced with Smart Money Concepts."""

    def __init__(self, limits: RiskLimits | None = None, smc_lookback: int = SMC_DEFAULT_LOOKBACK) -> None:
        super().__init__(limits)
        self.smc_analyzer = SmartMoneyAnalyzer(lookback=smc_lookback)
        self._smc = SMCAnalyzer(swing_length=min(smc_lookback, 10))

    def assess_trade_risk(self, df: pd.DataFrame, side: str, entry_price: float) -> dict[str, any]:
        """Assess trade risk using SMC analysis with enriched data."""
        analysis = self.smc_analyzer.analyze(df)

        risk_assessment = {
            "risk_score": analysis.get("risk_score", 50),
            "bias": analysis.get("bias", "neutral"),
            "should_trade": True,
            "position_size_multiplier": 1.0,
            "stop_loss_adjustment": 0.0,
            "reason": "Standard trade",
            "mitigation_status": "unknown",
            "retracement_warning": False,
            "liquidity_swept": False,
            "ob_strength": 0.0,
        }

        if analysis.get("risk_score", 50) > 70:
            risk_assessment["should_trade"] = False
            risk_assessment["reason"] = "Risk score too high"
            return risk_assessment

        # Bias alignment
        if (side == "BUY" and analysis["bias"] == "bearish") or \
           (side == "SELL" and analysis["bias"] == "bullish"):
            risk_assessment["position_size_multiplier"] = 0.5
            risk_assessment["reason"] = "Trading against bias"
        elif (side == "BUY" and analysis["bias"] == "bullish") or \
             (side == "SELL" and analysis["bias"] == "bearish"):
            risk_assessment["position_size_multiplier"] = 1.5
            risk_assessment["reason"] = "Strong bias alignment"

        # Deep retracement reduces position size
        retracement_pct = analysis.get("retracement_pct", 0.0)
        if retracement_pct > SMC_RETRACEMENT_DEEP_THRESHOLD:
            risk_assessment["position_size_multiplier"] *= 0.5
            risk_assessment["retracement_warning"] = True
            risk_assessment["reason"] = "Deep retracement warning"

        # Mitigated FVGs allow tighter stops
        mitigated_count = analysis.get("mitigated_fvg_count", 0)
        if mitigated_count > 0:
            risk_assessment["mitigation_status"] = "mitigated"
            risk_assessment["stop_loss_adjustment"] = -0.3
        else:
            risk_assessment["mitigation_status"] = "unmitigated"

        # Swept liquidity increases confidence
        swept_count = analysis.get("swept_liquidity_count", 0)
        if swept_count > 0:
            risk_assessment["liquidity_swept"] = True
            risk_assessment["position_size_multiplier"] *= 1.2

        # Strong OBs increase confidence
        ob_score = analysis.get("ob_volume_weighted_score", 0.0)
        risk_assessment["ob_strength"] = ob_score
        if ob_score > 50:
            risk_assessment["position_size_multiplier"] *= 1.3

        # Entry zone proximity
        entry_zones = self.smc_analyzer.get_entry_zones(df)

        if side == "BUY":
            for zone in entry_zones.get("bullish_zones", []):
                if abs(entry_price - zone["price"]) / entry_price < 0.01:
                    risk_assessment["stop_loss_adjustment"] = -0.5
                    break
        else:
            for zone in entry_zones.get("bearish_zones", []):
                if abs(entry_price - zone["price"]) / entry_price < 0.01:
                    risk_assessment["stop_loss_adjustment"] = -0.5
                    break

        # Nearby unswept liquidity warning
        nearby_liquidity = [
            lz for lz in self.smc_analyzer.liquidity_zones
            if abs(entry_price - lz.price) / entry_price < 0.02 and not lz.swept
        ]
        if nearby_liquidity:
            risk_assessment["stop_loss_adjustment"] = 0.5
            risk_assessment["reason"] = "Nearby unswept liquidity zone"

        return risk_assessment

    def check_fvg_mitigation(self, df: pd.DataFrame, side: str, entry_price: float) -> bool:
        """Check if entering against an unmitigated FVG.

        Returns True if the trade is safe (no dangerous unmitigated gap),
        False if the entry is inside a dangerous unmitigated FVG.
        """
        fvg_df = self._smc.fair_value_gaps(df)

        for idx in fvg_df.index:
            fvg_val = fvg_df.at[idx, "FVG"]
            if pd.isna(fvg_val):
                continue
            fvg_type = int(fvg_val)
            top = fvg_df.at[idx, "Top"]
            bottom = fvg_df.at[idx, "Bottom"]
            mit_idx = fvg_df.at[idx, "MitigatedIndex"]

            if pd.isna(top) or pd.isna(bottom):
                continue
            # Only concerned with unmitigated gaps
            if not pd.isna(mit_idx):
                continue

            # Buying inside a bearish FVG is dangerous
            if side == "BUY" and fvg_type == -1:
                if float(bottom) <= entry_price <= float(top):
                    return False

            # Selling inside a bullish FVG is dangerous
            if side == "SELL" and fvg_type == 1:
                if float(bottom) <= entry_price <= float(top):
                    return False

        return True

    def check_liquidity_sweep_safety(self, df: pd.DataFrame, side: str, entry_price: float) -> dict:
        """Check if entry is near unswept liquidity zones.

        Returns dict with: safe, unswept_zones, nearest_price, recommendation.
        """
        liq_df = self._smc.liquidity(df)
        unswept_zones: list[dict] = []
        nearest_price = None
        min_distance = float("inf")

        for idx in liq_df.index:
            liq_val = liq_df.at[idx, "Liquidity"]
            if pd.isna(liq_val):
                continue
            swept = liq_df.at[idx, "Swept"] if "Swept" in liq_df.columns else 0.0
            if not pd.isna(swept) and float(swept) != 0.0:
                continue  # Already swept, skip

            level = liq_df.at[idx, "Level"] if "Level" in liq_df.columns else 0.0
            price = float(level) if not pd.isna(level) else 0.0
            if price == 0.0:
                continue

            distance = abs(entry_price - price)
            distance_pct = distance / entry_price

            if distance_pct < 0.02:  # Within 2%
                unswept_zones.append({
                    "price": price,
                    "type": "buy_side" if int(liq_val) == 1 else "sell_side",
                    "distance_pct": distance_pct * 100,
                })
                if distance < min_distance:
                    min_distance = distance
                    nearest_price = price

        safe = len(unswept_zones) == 0
        recommendation = "Clear to trade" if safe else "Caution: unswept liquidity nearby"

        return {
            "safe": safe,
            "unswept_zones": unswept_zones,
            "nearest_price": nearest_price,
            "recommendation": recommendation,
        }

    def calculate_optimal_stop_loss(self, df: pd.DataFrame, side: str, entry_price: float) -> float:
        """Calculate optimal stop loss using volume-weighted OBs."""
        base_stop_pct = self.limits.stop_loss_pct
        assessment = self.assess_trade_risk(df, side, entry_price)
        adjusted_stop_pct = base_stop_pct + assessment["stop_loss_adjustment"]

        entry_zones = self.smc_analyzer.get_entry_zones(df)

        if side == "BUY":
            # Sort by volume (strongest OBs first)
            zones = sorted(
                entry_zones.get("bullish_zones", []),
                key=lambda z: z.get("volume", 0),
                reverse=True,
            )
            for zone in zones:
                if zone["price"] < entry_price:
                    stop_distance = (entry_price - zone["price"]) / entry_price * 100
                    if stop_distance < adjusted_stop_pct * 1.5:
                        pct = zone.get("percentage", 0)
                        buffer = 0.995 if pct > 50 else 0.99  # Tighter for strong OBs
                        return zone["price"] * buffer
            return entry_price * (1 - adjusted_stop_pct / 100)
        else:
            zones = sorted(
                entry_zones.get("bearish_zones", []),
                key=lambda z: z.get("volume", 0),
                reverse=True,
            )
            for zone in zones:
                if zone["price"] > entry_price:
                    stop_distance = (zone["price"] - entry_price) / entry_price * 100
                    if stop_distance < adjusted_stop_pct * 1.5:
                        pct = zone.get("percentage", 0)
                        buffer = 1.005 if pct > 50 else 1.01
                        return zone["price"] * buffer
            return entry_price * (1 + adjusted_stop_pct / 100)

    def calculate_optimal_take_profit(self, df: pd.DataFrame, side: str, entry_price: float) -> float:
        """Calculate optimal take profit targeting unmitigated FVGs and unswept liquidity."""
        base_tp_pct = self.limits.take_profit_pct

        # Primary target: nearest unmitigated FVG in profit direction
        fvg_target = self._find_fvg_target(df, side, entry_price)
        if fvg_target is not None:
            return fvg_target

        # Secondary target: nearest unswept liquidity zone
        liq_target = self._find_liquidity_target(df, side, entry_price)
        if liq_target is not None:
            return liq_target

        # Fallback: percentage-based TP
        if side == "BUY":
            return entry_price * (1 + base_tp_pct / 100)
        else:
            return entry_price * (1 - base_tp_pct / 100)

    def _find_fvg_target(self, df: pd.DataFrame, side: str, entry_price: float) -> float | None:
        """Find nearest unmitigated FVG as TP target."""
        fvg_df = self._smc.fair_value_gaps(df)
        best_target = None
        best_distance = float("inf")

        for idx in fvg_df.index:
            fvg_val = fvg_df.at[idx, "FVG"]
            if pd.isna(fvg_val):
                continue
            mit_idx = fvg_df.at[idx, "MitigatedIndex"]
            if not pd.isna(mit_idx):
                continue  # Already mitigated
            top = fvg_df.at[idx, "Top"]
            bottom = fvg_df.at[idx, "Bottom"]
            if pd.isna(top) or pd.isna(bottom):
                continue

            mid = (float(top) + float(bottom)) / 2

            if side == "BUY" and mid > entry_price:
                dist = mid - entry_price
                if dist < best_distance:
                    best_distance = dist
                    best_target = float(bottom) * 0.995  # Take profit just before gap
            elif side == "SELL" and mid < entry_price:
                dist = entry_price - mid
                if dist < best_distance:
                    best_distance = dist
                    best_target = float(top) * 1.005

        return best_target

    def _find_liquidity_target(self, df: pd.DataFrame, side: str, entry_price: float) -> float | None:
        """Find nearest unswept liquidity zone as TP target."""
        liq_df = self._smc.liquidity(df)
        best_target = None
        best_distance = float("inf")

        for idx in liq_df.index:
            liq_val = liq_df.at[idx, "Liquidity"]
            if pd.isna(liq_val):
                continue
            swept = liq_df.at[idx, "Swept"] if "Swept" in liq_df.columns else 0.0
            if not pd.isna(swept) and float(swept) != 0.0:
                continue

            level = liq_df.at[idx, "Level"] if "Level" in liq_df.columns else 0.0
            price = float(level) if not pd.isna(level) else 0.0
            if price == 0.0:
                continue

            if side == "BUY" and price > entry_price:
                dist = price - entry_price
                if dist < best_distance:
                    best_distance = dist
                    best_target = price * 0.998
            elif side == "SELL" and price < entry_price:
                dist = entry_price - price
                if dist < best_distance:
                    best_distance = dist
                    best_target = price * 1.002

        return best_target
