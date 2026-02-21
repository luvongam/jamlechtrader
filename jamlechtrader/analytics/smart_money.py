"""Smart Money Concepts (SMC) analyzer for risk assessment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd
from loguru import logger

if TYPE_CHECKING:
    from jamlechtrader.core.models import Bar


@dataclass
class OrderBlock:
    """Institutional order block."""
    price: float
    timestamp: pd.Timestamp
    type: str  # "bullish" or "bearish"
    strength: float


@dataclass
class FairValueGap:
    """Fair Value Gap (imbalance)."""
    high: float
    low: float
    timestamp: pd.Timestamp
    type: str  # "bullish" or "bearish"


@dataclass
class LiquidityZone:
    """Liquidity pool zone."""
    price: float
    timestamp: pd.Timestamp
    type: str  # "buy_side" or "sell_side"
    swept: bool = False


class SmartMoneyAnalyzer:
    """Analyze market structure using Smart Money Concepts."""

    def __init__(self, lookback: int = 50) -> None:
        self.lookback = lookback
        self.order_blocks: list[OrderBlock] = []
        self.fvgs: list[FairValueGap] = []
        self.liquidity_zones: list[LiquidityZone] = []

    def analyze(self, df: pd.DataFrame) -> dict:
        """Analyze price data for smart money patterns."""
        if len(df) < self.lookback:
            return {}

        # Detect market structure
        structure = self._detect_market_structure(df)
        
        # Find order blocks
        self.order_blocks = self._find_order_blocks(df)
        
        # Find fair value gaps
        self.fvgs = self._find_fair_value_gaps(df)
        
        # Find liquidity zones
        self.liquidity_zones = self._find_liquidity_zones(df)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(df, structure)

        return {
            "market_structure": structure,
            "order_blocks": len(self.order_blocks),
            "fair_value_gaps": len(self.fvgs),
            "liquidity_zones": len(self.liquidity_zones),
            "risk_score": risk_score,
            "bias": self._determine_bias(structure, df),
        }

    def _detect_market_structure(self, df: pd.DataFrame) -> dict:
        """Detect higher highs, higher lows, lower highs, lower lows."""
        highs = df["high"].values
        lows = df["low"].values
        
        # Find swing points
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(df) - 2):
            # Swing high
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append((i, highs[i]))
            
            # Swing low
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append((i, lows[i]))

        # Determine trend
        trend = "ranging"
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            if swing_highs[-1][1] > swing_highs[-2][1] and swing_lows[-1][1] > swing_lows[-2][1]:
                trend = "bullish"
            elif swing_highs[-1][1] < swing_highs[-2][1] and swing_lows[-1][1] < swing_lows[-2][1]:
                trend = "bearish"

        return {
            "trend": trend,
            "swing_highs": swing_highs[-5:] if swing_highs else [],
            "swing_lows": swing_lows[-5:] if swing_lows else [],
        }

    def _find_order_blocks(self, df: pd.DataFrame) -> list[OrderBlock]:
        """Find institutional order blocks."""
        order_blocks = []
        
        for i in range(3, len(df)):
            # Bullish order block: strong move up after consolidation
            if df["close"].iloc[i] > df["close"].iloc[i-1] * 1.005:
                prev_candle = df.iloc[i-1]
                if prev_candle["close"] < prev_candle["open"]:  # Bearish candle before breakout
                    order_blocks.append(OrderBlock(
                        price=(prev_candle["high"] + prev_candle["low"]) / 2,
                        timestamp=prev_candle.name,
                        type="bullish",
                        strength=abs(df["close"].iloc[i] - df["close"].iloc[i-1]) / df["close"].iloc[i-1]
                    ))
            
            # Bearish order block: strong move down after consolidation
            if df["close"].iloc[i] < df["close"].iloc[i-1] * 0.995:
                prev_candle = df.iloc[i-1]
                if prev_candle["close"] > prev_candle["open"]:  # Bullish candle before breakdown
                    order_blocks.append(OrderBlock(
                        price=(prev_candle["high"] + prev_candle["low"]) / 2,
                        timestamp=prev_candle.name,
                        type="bearish",
                        strength=abs(df["close"].iloc[i-1] - df["close"].iloc[i]) / df["close"].iloc[i-1]
                    ))

        return order_blocks[-10:]  # Keep last 10

    def _find_fair_value_gaps(self, df: pd.DataFrame) -> list[FairValueGap]:
        """Find fair value gaps (imbalances)."""
        fvgs = []
        
        for i in range(2, len(df)):
            # Bullish FVG: gap between candle[i-2] high and candle[i] low
            if df["low"].iloc[i] > df["high"].iloc[i-2]:
                gap_size = df["low"].iloc[i] - df["high"].iloc[i-2]
                if gap_size > df["close"].iloc[i] * 0.001:  # Significant gap
                    fvgs.append(FairValueGap(
                        high=df["low"].iloc[i],
                        low=df["high"].iloc[i-2],
                        timestamp=df.index[i],
                        type="bullish"
                    ))
            
            # Bearish FVG: gap between candle[i-2] low and candle[i] high
            if df["high"].iloc[i] < df["low"].iloc[i-2]:
                gap_size = df["low"].iloc[i-2] - df["high"].iloc[i]
                if gap_size > df["close"].iloc[i] * 0.001:
                    fvgs.append(FairValueGap(
                        high=df["low"].iloc[i-2],
                        low=df["high"].iloc[i],
                        timestamp=df.index[i],
                        type="bearish"
                    ))

        return fvgs[-10:]

    def _find_liquidity_zones(self, df: pd.DataFrame) -> list[LiquidityZone]:
        """Find liquidity pools (equal highs/lows)."""
        zones = []
        highs = df["high"].values
        lows = df["low"].values
        
        # Find equal highs (buy-side liquidity)
        for i in range(1, len(df) - 1):
            if abs(highs[i] - highs[i-1]) / highs[i] < 0.0005:  # Equal highs
                zones.append(LiquidityZone(
                    price=highs[i],
                    timestamp=df.index[i],
                    type="buy_side"
                ))
        
        # Find equal lows (sell-side liquidity)
        for i in range(1, len(df) - 1):
            if abs(lows[i] - lows[i-1]) / lows[i] < 0.0005:  # Equal lows
                zones.append(LiquidityZone(
                    price=lows[i],
                    timestamp=df.index[i],
                    type="sell_side"
                ))

        return zones[-10:]

    def _calculate_risk_score(self, df: pd.DataFrame, structure: dict) -> float:
        """Calculate risk score (0-100, lower is better)."""
        risk = 50.0  # Neutral
        
        # Trend alignment reduces risk
        if structure["trend"] == "bullish":
            risk -= 15
        elif structure["trend"] == "bearish":
            risk -= 15
        else:
            risk += 10  # Ranging is riskier
        
        # Order blocks provide support/resistance
        risk -= min(len(self.order_blocks) * 3, 15)
        
        # FVGs indicate potential reversal zones
        risk += min(len(self.fvgs) * 2, 10)
        
        # Liquidity zones indicate potential stop hunts
        unswept_liquidity = len([z for z in self.liquidity_zones if not z.swept])
        risk += min(unswept_liquidity * 3, 15)
        
        # Volatility check
        atr = df["high"] - df["low"]
        recent_volatility = atr.iloc[-10:].mean()
        avg_volatility = atr.mean()
        if recent_volatility > avg_volatility * 1.5:
            risk += 10
        
        return max(0, min(100, risk))

    def _determine_bias(self, structure: dict, df: pd.DataFrame) -> str:
        """Determine trading bias based on SMC analysis."""
        current_price = df["close"].iloc[-1]
        
        # Check if price is near order blocks
        bullish_obs = [ob for ob in self.order_blocks if ob.type == "bullish" and abs(current_price - ob.price) / current_price < 0.01]
        bearish_obs = [ob for ob in self.order_blocks if ob.type == "bearish" and abs(current_price - ob.price) / current_price < 0.01]
        
        # Check FVGs
        bullish_fvgs = [fvg for fvg in self.fvgs if fvg.type == "bullish" and fvg.low <= current_price <= fvg.high]
        bearish_fvgs = [fvg for fvg in self.fvgs if fvg.type == "bearish" and fvg.low <= current_price <= fvg.high]
        
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
        
        # Find nearest bullish order block
        bullish_entries = []
        for ob in self.order_blocks:
            if ob.type == "bullish" and ob.price < current_price:
                bullish_entries.append({
                    "price": ob.price,
                    "strength": ob.strength,
                    "distance_pct": (current_price - ob.price) / current_price * 100
                })
        
        # Find nearest bearish order block
        bearish_entries = []
        for ob in self.order_blocks:
            if ob.type == "bearish" and ob.price > current_price:
                bearish_entries.append({
                    "price": ob.price,
                    "strength": ob.strength,
                    "distance_pct": (ob.price - current_price) / current_price * 100
                })
        
        return {
            "bullish_zones": sorted(bullish_entries, key=lambda x: x["distance_pct"])[:3],
            "bearish_zones": sorted(bearish_entries, key=lambda x: x["distance_pct"])[:3],
        }
