"""Smart Money risk manager with SMC integration."""

from __future__ import annotations

import pandas as pd
from loguru import logger

from jamlechtrader.analytics.smart_money import SmartMoneyAnalyzer
from jamlechtrader.core.constants import SMC_DEFAULT_LOOKBACK
from jamlechtrader.portfolio.risk import RiskLimits, RiskManager


class SmartMoneyRiskManager(RiskManager):
    """Risk manager enhanced with Smart Money Concepts."""

    def __init__(self, limits: RiskLimits | None = None, smc_lookback: int = SMC_DEFAULT_LOOKBACK) -> None:
        super().__init__(limits)
        self.smc_analyzer = SmartMoneyAnalyzer(lookback=smc_lookback)

    def assess_trade_risk(self, df: pd.DataFrame, side: str, entry_price: float) -> dict[str, any]:
        """Assess trade risk using SMC analysis."""
        analysis = self.smc_analyzer.analyze(df)
        
        risk_assessment = {
            "risk_score": analysis.get("risk_score", 50),
            "bias": analysis.get("bias", "neutral"),
            "should_trade": True,
            "position_size_multiplier": 1.0,
            "stop_loss_adjustment": 0.0,
            "reason": "Standard trade",
        }

        if analysis["risk_score"] > 70:
            risk_assessment["should_trade"] = False
            risk_assessment["reason"] = "Risk score too high"
            return risk_assessment

        if (side == "BUY" and analysis["bias"] == "bearish") or \
           (side == "SELL" and analysis["bias"] == "bullish"):
            risk_assessment["position_size_multiplier"] = 0.5
            risk_assessment["reason"] = "Trading against bias"
        elif (side == "BUY" and analysis["bias"] == "bullish") or \
             (side == "SELL" and analysis["bias"] == "bearish"):
            risk_assessment["position_size_multiplier"] = 1.5
            risk_assessment["reason"] = "Strong bias alignment"

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

        nearby_liquidity = [
            lz for lz in self.smc_analyzer.liquidity_zones
            if abs(entry_price - lz.price) / entry_price < 0.02 and not lz.swept
        ]
        
        if nearby_liquidity:
            risk_assessment["stop_loss_adjustment"] = 0.5
            risk_assessment["reason"] = "Nearby liquidity zone"

        return risk_assessment

    def calculate_optimal_stop_loss(self, df: pd.DataFrame, side: str, entry_price: float) -> float:
        """Calculate optimal stop loss using SMC levels."""
        base_stop_pct = self.limits.stop_loss_pct
        assessment = self.assess_trade_risk(df, side, entry_price)
        adjusted_stop_pct = base_stop_pct + assessment["stop_loss_adjustment"]
        
        entry_zones = self.smc_analyzer.get_entry_zones(df)
        
        if side == "BUY":
            for zone in entry_zones.get("bullish_zones", []):
                if zone["price"] < entry_price:
                    stop_distance = (entry_price - zone["price"]) / entry_price * 100
                    if stop_distance < adjusted_stop_pct * 1.5:
                        return zone["price"] * 0.995
            return entry_price * (1 - adjusted_stop_pct / 100)
        else:
            for zone in entry_zones.get("bearish_zones", []):
                if zone["price"] > entry_price:
                    stop_distance = (zone["price"] - entry_price) / entry_price * 100
                    if stop_distance < adjusted_stop_pct * 1.5:
                        return zone["price"] * 1.005
            return entry_price * (1 + adjusted_stop_pct / 100)

    def calculate_optimal_take_profit(self, df: pd.DataFrame, side: str, entry_price: float) -> float:
        """Calculate optimal take profit using SMC levels."""
        base_tp_pct = self.limits.take_profit_pct
        entry_zones = self.smc_analyzer.get_entry_zones(df)
        
        if side == "BUY":
            for zone in entry_zones.get("bearish_zones", []):
                if zone["price"] > entry_price:
                    return zone["price"] * 0.995
            return entry_price * (1 + base_tp_pct / 100)
        else:
            for zone in entry_zones.get("bullish_zones", []):
                if zone["price"] < entry_price:
                    return zone["price"] * 1.005
            return entry_price * (1 - base_tp_pct / 100)
