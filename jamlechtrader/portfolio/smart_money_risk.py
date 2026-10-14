"""Smart Money risk manager with SMC integration.

Implements institutional-grade risk management using:
- Market structure analysis (BOS/CHoCH) for bias confirmation
- Order block proximity for stop loss placement
- Fair Value Gap mitigation awareness
- Liquidity sweep detection for entry timing
- Session-aware risk scaling
- Multi-confluent position sizing
"""

from __future__ import annotations

import pandas as pd
from loguru import logger

from jamlechtrader.analytics.enhanced_smc import SMCAnalyzer
from jamlechtrader.analytics.smart_money import SmartMoneyAnalyzer
from jamlechtrader.core.constants import SMC_DEFAULT_LOOKBACK, SMC_RETRACEMENT_DEEP_THRESHOLD
from jamlechtrader.portfolio.risk import RiskLimits, RiskManager


class SmartMoneyRiskManager(RiskManager):
    """Risk manager enhanced with Smart Money Concepts.

    Provides institutional-style risk management by analyzing market
    structure, order flow footprints, and liquidity conditions to
    dynamically adjust position sizes and stop/target levels.
    """

    def __init__(self, limits: RiskLimits | None = None, smc_lookback: int = SMC_DEFAULT_LOOKBACK) -> None:
        super().__init__(limits)
        self.smc_analyzer = SmartMoneyAnalyzer(lookback=smc_lookback)
        self._smc = SMCAnalyzer(swing_length=min(smc_lookback, 10))
        self._consecutive_smc_rejects = 0
        self._max_smc_rejects = 3  # Pause after 3 consecutive SMC-rejected trades

    def assess_trade_risk(self, df: pd.DataFrame, side: str, entry_price: float) -> dict[str, any]:
        """Assess trade risk using full SMC analysis.

        Returns a comprehensive risk assessment including:
        - Market structure alignment score
        - Confluence count (OB + FVG + liquidity + BOS)
        - Dynamic position size multiplier
        - Optimal stop loss and take profit adjustments
        """
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
            "confluence_count": 0,
            "market_structure": "neutral",
            "session_risk_factor": 1.0,
        }

        # Check if we should pause due to consecutive SMC rejections
        if self._consecutive_smc_rejects >= self._max_smc_rejects:
            risk_assessment["should_trade"] = False
            risk_assessment["reason"] = f"Paused: {self._consecutive_smc_rejects} consecutive SMC rejections"
            return risk_assessment

        if analysis.get("risk_score", 50) > 70:
            risk_assessment["should_trade"] = False
            risk_assessment["reason"] = "Risk score too high"
            self._consecutive_smc_rejects += 1
            return risk_assessment

        # Market structure analysis via BOS/CHoCH
        market_structure = self._analyze_market_structure(df, side)
        risk_assessment["market_structure"] = market_structure["direction"]
        confluence = 0

        if market_structure["aligned"]:
            risk_assessment["position_size_multiplier"] *= 1.2
            confluence += 1
        elif market_structure["counter_trend"]:
            risk_assessment["position_size_multiplier"] *= 0.4
            risk_assessment["reason"] = "Counter-trend trade (CHoCH needed)"

        # Bias alignment
        if (side == "BUY" and analysis["bias"] == "bearish") or \
           (side == "SELL" and analysis["bias"] == "bullish"):
            risk_assessment["position_size_multiplier"] *= 0.5
            risk_assessment["reason"] = "Trading against bias"
        elif (side == "BUY" and analysis["bias"] == "bullish") or \
             (side == "SELL" and analysis["bias"] == "bearish"):
            risk_assessment["position_size_multiplier"] *= 1.3
            risk_assessment["reason"] = "Strong bias alignment"
            confluence += 1

        # Deep retracement reduces position size
        retracement_pct = analysis.get("retracement_pct", 0.0)
        if retracement_pct > SMC_RETRACEMENT_DEEP_THRESHOLD:
            risk_assessment["position_size_multiplier"] *= 0.5
            risk_assessment["retracement_warning"] = True
            risk_assessment["reason"] = "Deep retracement warning"
        elif 50.0 < retracement_pct <= 78.6:
            # Optimal retracement zone (OTE) — increase confidence
            risk_assessment["position_size_multiplier"] *= 1.15
            confluence += 1

        # Mitigated FVGs allow tighter stops
        mitigated_count = analysis.get("mitigated_fvg_count", 0)
        if mitigated_count > 0:
            risk_assessment["mitigation_status"] = "mitigated"
            risk_assessment["stop_loss_adjustment"] = -0.3
        else:
            risk_assessment["mitigation_status"] = "unmitigated"

        # Unmitigated FVG confluence
        unmitigated_fvg_aligned = self._check_fvg_confluence(df, side, entry_price)
        if unmitigated_fvg_aligned:
            confluence += 1

        # Swept liquidity increases confidence
        swept_count = analysis.get("swept_liquidity_count", 0)
        if swept_count > 0:
            risk_assessment["liquidity_swept"] = True
            risk_assessment["position_size_multiplier"] *= 1.2
            confluence += 1

        # Strong OBs increase confidence
        ob_score = analysis.get("ob_volume_weighted_score", 0.0)
        risk_assessment["ob_strength"] = ob_score
        if ob_score > 50:
            risk_assessment["position_size_multiplier"] *= 1.3
            confluence += 1

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

        # Confluence-based scaling
        risk_assessment["confluence_count"] = confluence
        if confluence >= 4:
            risk_assessment["position_size_multiplier"] *= 1.3
            risk_assessment["reason"] = f"High confluence ({confluence} factors)"
        elif confluence <= 1:
            risk_assessment["position_size_multiplier"] *= 0.6
            risk_assessment["reason"] = f"Low confluence ({confluence} factors)"

        # Cap the multiplier to prevent excessive sizing
        risk_assessment["position_size_multiplier"] = min(
            risk_assessment["position_size_multiplier"], 2.5
        )

        # Reset rejection counter on successful assessment
        if risk_assessment["should_trade"]:
            self._consecutive_smc_rejects = 0

        return risk_assessment

    def _analyze_market_structure(self, df: pd.DataFrame, side: str) -> dict:
        """Analyze market structure using BOS and CHoCH.

        Returns dict with direction, aligned (bool), and counter_trend (bool).
        """
        result = {"direction": "neutral", "aligned": False, "counter_trend": False}

        try:
            bos_df = self._smc.bos_choch(df)
            recent = bos_df.tail(10)

            # Count recent bullish/bearish BOS
            bullish_bos = (recent["BOS"] == 1).sum()
            bearish_bos = (recent["BOS"] == -1).sum()

            # CHoCH signals trend reversal
            bullish_choch = (recent["CHOCH"] == 1).sum() if "CHOCH" in recent.columns else 0
            bearish_choch = (recent["CHOCH"] == -1).sum() if "CHOCH" in recent.columns else 0

            if bullish_bos > bearish_bos and bullish_choch == 0:
                result["direction"] = "bullish"
                result["aligned"] = side == "BUY"
                result["counter_trend"] = side == "SELL"
            elif bearish_bos > bullish_bos and bearish_choch == 0:
                result["direction"] = "bearish"
                result["aligned"] = side == "SELL"
                result["counter_trend"] = side == "BUY"
            elif bullish_choch > 0 and side == "BUY":
                result["direction"] = "reversal_bullish"
                result["aligned"] = True
            elif bearish_choch > 0 and side == "SELL":
                result["direction"] = "reversal_bearish"
                result["aligned"] = True
        except Exception:
            pass

        return result

    def _check_fvg_confluence(self, df: pd.DataFrame, side: str, entry_price: float) -> bool:
        """Check if an unmitigated FVG aligns with the trade direction."""
        try:
            fvg_df = self._smc.fair_value_gaps(df)
            for idx in fvg_df.index:
                fvg_val = fvg_df.at[idx, "FVG"]
                if pd.isna(fvg_val):
                    continue
                mit_idx = fvg_df.at[idx, "MitigatedIndex"]
                if not pd.isna(mit_idx):
                    continue
                top = fvg_df.at[idx, "Top"]
                bottom = fvg_df.at[idx, "Bottom"]
                if pd.isna(top) or pd.isna(bottom):
                    continue

                mid = (float(top) + float(bottom)) / 2
                distance_pct = abs(entry_price - mid) / entry_price

                # FVG within 2% of entry in the profit direction
                if side == "BUY" and int(fvg_val) == 1 and distance_pct < 0.02:
                    return True
                if side == "SELL" and int(fvg_val) == -1 and distance_pct < 0.02:
                    return True
        except Exception:
            pass
        return False

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
