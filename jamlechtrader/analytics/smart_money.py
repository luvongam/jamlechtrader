"""Smart Money Concepts (SMC) analyzer for risk assessment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from loguru import logger

from jamlechtrader.analytics.enhanced_smc import SMCAnalyzer
from jamlechtrader.core.constants import (
    SMC_OB_VOLUME_WEIGHT_FACTOR,
    SMC_RETRACEMENT_DEEP_THRESHOLD,
    SMC_SWEPT_LIQUIDITY_RISK_BONUS,
)

if TYPE_CHECKING:
    from jamlechtrader.core.models import Bar


@dataclass
class OrderBlock:
    """Institutional order block."""
    price: float
    timestamp: pd.Timestamp
    type: str  # "bullish" or "bearish"
    strength: float
    top: float = 0.0
    bottom: float = 0.0
    volume: float = 0.0
    percentage: float = 0.0


@dataclass
class FairValueGap:
    """Fair Value Gap (imbalance)."""
    high: float
    low: float
    timestamp: pd.Timestamp
    type: str  # "bullish" or "bearish"
    mitigated_index: int | None = None


@dataclass
class LiquidityZone:
    """Liquidity pool zone."""
    price: float
    timestamp: pd.Timestamp
    type: str  # "buy_side" or "sell_side"
    swept: bool = False
    level: float = 0.0
    end: float = 0.0


class SmartMoneyAnalyzer:
    """Analyze market structure using Smart Money Concepts.

    Delegates detection to the ``smartmoneyconcepts`` package via
    :class:`SMCAnalyzer` and enriches the results with risk-relevant
    scores and metadata.
    """

    def __init__(self, lookback: int = 50) -> None:
        self.lookback = lookback
        self.order_blocks: list[OrderBlock] = []
        self.fvgs: list[FairValueGap] = []
        self.liquidity_zones: list[LiquidityZone] = []
        self._smc = SMCAnalyzer(swing_length=min(lookback, 10))

    def analyze(self, df: pd.DataFrame) -> dict:
        """Analyze price data for smart money patterns."""
        if len(df) < self.lookback:
            return {}

        structure = self._detect_market_structure(df)
        self.order_blocks = self._find_order_blocks(df)
        self.fvgs = self._find_fair_value_gaps(df)
        self.liquidity_zones = self._find_liquidity_zones(df)

        risk_score = self._calculate_risk_score(df, structure)

        # Enriched fields from package data
        retracement_pct = self._get_retracement_pct(df)
        mitigated_fvg_count = sum(1 for f in self.fvgs if f.mitigated_index is not None)
        swept_liquidity_count = sum(1 for z in self.liquidity_zones if z.swept)
        ob_volume_weighted_score = self._ob_volume_weighted_score()

        return {
            "market_structure": structure,
            "order_blocks": len(self.order_blocks),
            "fair_value_gaps": len(self.fvgs),
            "liquidity_zones": len(self.liquidity_zones),
            "risk_score": risk_score,
            "bias": self._determine_bias(structure, df),
            "retracement_pct": retracement_pct,
            "mitigated_fvg_count": mitigated_fvg_count,
            "swept_liquidity_count": swept_liquidity_count,
            "ob_volume_weighted_score": ob_volume_weighted_score,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_market_structure(self, df: pd.DataFrame) -> dict:
        """Detect higher highs, higher lows, lower highs, lower lows."""
        swings = self._smc.swing_highs_lows(df)

        swing_highs_mask = swings["HighLow"] == 1
        swing_lows_mask = swings["HighLow"] == -1

        swing_high_prices = df.loc[swing_highs_mask, "high"].values
        swing_low_prices = df.loc[swing_lows_mask, "low"].values

        swing_highs = list(zip(
            df.index[swing_highs_mask].tolist(),
            swing_high_prices.tolist(),
        ))
        swing_lows = list(zip(
            df.index[swing_lows_mask].tolist(),
            swing_low_prices.tolist(),
        ))

        trend = "ranging"
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            if swing_highs[-1][1] > swing_highs[-2][1] and swing_lows[-1][1] > swing_lows[-2][1]:
                trend = "bullish"
            elif swing_highs[-1][1] < swing_highs[-2][1] and swing_lows[-1][1] < swing_lows[-2][1]:
                trend = "bearish"

        return {
            "trend": trend,
            "swing_highs": swing_highs[-5:],
            "swing_lows": swing_lows[-5:],
        }

    def _find_order_blocks(self, df: pd.DataFrame) -> list[OrderBlock]:
        """Find institutional order blocks via package."""
        ob_df = self._smc.order_blocks(df)
        order_blocks: list[OrderBlock] = []

        for idx in ob_df.index:
            ob_val = ob_df.at[idx, "OB"]
            if pd.isna(ob_val):
                continue
            ob_type = int(ob_val)
            top = ob_df.at[idx, "Top"]
            bottom = ob_df.at[idx, "Bottom"]
            ob_volume = ob_df.at[idx, "OBVolume"] if "OBVolume" in ob_df.columns else 0.0
            percentage = ob_df.at[idx, "Percentage"] if "Percentage" in ob_df.columns else 0.0

            order_blocks.append(OrderBlock(
                price=(top + bottom) / 2,
                timestamp=idx,
                type="bullish" if ob_type == 1 else "bearish",
                strength=float(percentage) / 100.0 if not pd.isna(percentage) else 0.5,
                top=float(top) if not pd.isna(top) else 0.0,
                bottom=float(bottom) if not pd.isna(bottom) else 0.0,
                volume=float(ob_volume) if not pd.isna(ob_volume) else 0.0,
                percentage=float(percentage) if not pd.isna(percentage) else 0.0,
            ))

        return order_blocks[-10:]

    def _find_fair_value_gaps(self, df: pd.DataFrame) -> list[FairValueGap]:
        """Find fair value gaps via package."""
        fvg_df = self._smc.fair_value_gaps(df)
        fvgs: list[FairValueGap] = []

        for idx in fvg_df.index:
            fvg_val = fvg_df.at[idx, "FVG"]
            if pd.isna(fvg_val):
                continue
            fvg_type = int(fvg_val)
            top = fvg_df.at[idx, "Top"]
            bottom = fvg_df.at[idx, "Bottom"]
            mit_idx = fvg_df.at[idx, "MitigatedIndex"]

            fvgs.append(FairValueGap(
                high=float(top) if not pd.isna(top) else 0.0,
                low=float(bottom) if not pd.isna(bottom) else 0.0,
                timestamp=idx,
                type="bullish" if fvg_type == 1 else "bearish",
                mitigated_index=int(mit_idx) if not pd.isna(mit_idx) else None,
            ))

        return fvgs[-10:]

    def _find_liquidity_zones(self, df: pd.DataFrame) -> list[LiquidityZone]:
        """Find liquidity pools via package."""
        liq_df = self._smc.liquidity(df)
        zones: list[LiquidityZone] = []

        for idx in liq_df.index:
            liq_val = liq_df.at[idx, "Liquidity"]
            if pd.isna(liq_val):
                continue
            liq_type = int(liq_val)
            level = liq_df.at[idx, "Level"] if "Level" in liq_df.columns else 0.0
            end = liq_df.at[idx, "End"] if "End" in liq_df.columns else 0.0
            swept = liq_df.at[idx, "Swept"] if "Swept" in liq_df.columns else 0.0
            is_swept = not pd.isna(swept) and float(swept) != 0.0

            price = float(level) if not pd.isna(level) else df.at[idx, "high" if liq_type == 1 else "low"]

            zones.append(LiquidityZone(
                price=price,
                timestamp=idx,
                type="buy_side" if liq_type == 1 else "sell_side",
                swept=is_swept,
                level=float(level) if not pd.isna(level) else 0.0,
                end=float(end) if not pd.isna(end) else 0.0,
            ))

        return zones[-10:]

    def _get_retracement_pct(self, df: pd.DataFrame) -> float:
        """Return the latest current retracement percentage."""
        try:
            ret_df = self._smc.retracements(df)
            col = "CurrentRetracement%"
            if col in ret_df.columns:
                last_valid = ret_df[col].dropna()
                if len(last_valid) > 0:
                    return float(last_valid.iloc[-1])
        except Exception:
            logger.debug("Retracement calculation skipped")
        return 0.0

    def _ob_volume_weighted_score(self) -> float:
        """Average OB volume strength (0-100)."""
        if not self.order_blocks:
            return 0.0
        total = sum(ob.percentage for ob in self.order_blocks)
        return total / len(self.order_blocks)

    def _calculate_risk_score(self, df: pd.DataFrame, structure: dict) -> float:
        """Calculate risk score (0-100, lower is better)."""
        risk = 50.0

        # Trend alignment
        if structure["trend"] in ("bullish", "bearish"):
            risk -= 15
        else:
            risk += 10

        # Volume-weighted OB adjustment: stronger OBs reduce risk more
        for ob in self.order_blocks:
            weight = 1.0 + ob.percentage / 100.0 * SMC_OB_VOLUME_WEIGHT_FACTOR
            risk -= min(3 * weight, 5)
        risk = max(risk, 0)

        # Mitigated vs unmitigated FVGs
        unmitigated = [f for f in self.fvgs if f.mitigated_index is None]
        mitigated = [f for f in self.fvgs if f.mitigated_index is not None]
        risk += min(len(unmitigated) * 2, 10)
        risk -= min(len(mitigated) * 1, 5)

        # Swept vs unswept liquidity
        unswept = [z for z in self.liquidity_zones if not z.swept]
        swept = [z for z in self.liquidity_zones if z.swept]
        risk += min(len(unswept) * 3, 15)
        risk -= min(len(swept) * SMC_SWEPT_LIQUIDITY_RISK_BONUS / 5, 10)

        # Deep retracement penalty
        retracement = self._get_retracement_pct(df)
        if retracement > SMC_RETRACEMENT_DEEP_THRESHOLD:
            risk += 10

        # Volatility check
        atr = df["high"] - df["low"]
        recent_volatility = atr.iloc[-10:].mean()
        avg_volatility = atr.mean()
        if recent_volatility > avg_volatility * 1.5:
            risk += 10

        return max(0.0, min(100.0, risk))

    def _determine_bias(self, structure: dict, df: pd.DataFrame) -> str:
        """Determine trading bias based on SMC analysis."""
        current_price = df["close"].iloc[-1]

        bullish_obs = [
            ob for ob in self.order_blocks
            if ob.type == "bullish" and abs(current_price - ob.price) / current_price < 0.01
        ]
        bearish_obs = [
            ob for ob in self.order_blocks
            if ob.type == "bearish" and abs(current_price - ob.price) / current_price < 0.01
        ]

        bullish_fvgs = [
            f for f in self.fvgs if f.type == "bullish" and f.low <= current_price <= f.high
        ]
        bearish_fvgs = [
            f for f in self.fvgs if f.type == "bearish" and f.low <= current_price <= f.high
        ]

        score = 0
        if structure["trend"] == "bullish":
            score += 2
        elif structure["trend"] == "bearish":
            score -= 2

        score += len(bullish_obs) - len(bearish_obs)
        score += len(bullish_fvgs) - len(bearish_fvgs)

        if score > 1:
            return "bullish"
        elif score < -1:
            return "bearish"
        return "neutral"

    def get_entry_zones(self, df: pd.DataFrame) -> dict:
        """Get optimal entry zones based on SMC."""
        current_price = df["close"].iloc[-1]

        bullish_entries = []
        for ob in self.order_blocks:
            if ob.type == "bullish" and ob.price < current_price:
                bullish_entries.append({
                    "price": ob.price,
                    "strength": ob.strength,
                    "distance_pct": (current_price - ob.price) / current_price * 100,
                    "volume": ob.volume,
                    "percentage": ob.percentage,
                })

        bearish_entries = []
        for ob in self.order_blocks:
            if ob.type == "bearish" and ob.price > current_price:
                bearish_entries.append({
                    "price": ob.price,
                    "strength": ob.strength,
                    "distance_pct": (ob.price - current_price) / current_price * 100,
                    "volume": ob.volume,
                    "percentage": ob.percentage,
                })

        return {
            "bullish_zones": sorted(bullish_entries, key=lambda x: x["distance_pct"])[:3],
            "bearish_zones": sorted(bearish_entries, key=lambda x: x["distance_pct"])[:3],
        }
