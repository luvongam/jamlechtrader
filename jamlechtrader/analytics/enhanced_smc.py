"""Enhanced Smart Money Concepts analyzer - Professional implementation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class OrderBlock:
    """Order Block structure."""
    top: float
    bottom: float
    timestamp: pd.Timestamp
    ob_type: int  # 1 = bullish, -1 = bearish


@dataclass
class FairValueGap:
    """Fair Value Gap structure."""
    top: float
    bottom: float
    timestamp: pd.Timestamp
    fvg_type: int  # 1 = bullish, -1 = bearish


@dataclass
class BreakOfStructure:
    """Break of Structure."""
    level: float
    timestamp: pd.Timestamp
    bos_type: int  # 1 = bullish, -1 = bearish


class SMCAnalyzer:
    """Professional Smart Money Concepts analyzer."""

    def __init__(self, swing_length: int = 10) -> None:
        self.swing_length = swing_length

    def swing_highs_lows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect swing highs and lows."""
        result = df.copy()
        result["HighLow"] = 0
        
        highs = df["high"].values
        lows = df["low"].values
        
        for i in range(self.swing_length, len(df) - self.swing_length):
            # Swing high
            if all(highs[i] >= highs[i-j] for j in range(1, self.swing_length + 1)) and \
               all(highs[i] >= highs[i+j] for j in range(1, self.swing_length + 1)):
                result.loc[result.index[i], "HighLow"] = 1
            
            # Swing low
            if all(lows[i] <= lows[i-j] for j in range(1, self.swing_length + 1)) and \
               all(lows[i] <= lows[i+j] for j in range(1, self.swing_length + 1)):
                result.loc[result.index[i], "HighLow"] = -1
        
        return result

    def bos_choch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Break of Structure (BOS) and Change of Character (CHoCH)."""
        result = self.swing_highs_lows(df)
        result["BOS"] = 0
        result["CHOCH"] = 0
        
        swing_highs = result[result["HighLow"] == 1]
        swing_lows = result[result["HighLow"] == -1]
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return result
        
        # Detect BOS (continuation)
        for i in range(1, len(swing_highs)):
            if swing_highs.iloc[i]["high"] > swing_highs.iloc[i-1]["high"]:
                idx = swing_highs.index[i]
                result.loc[idx, "BOS"] = 1
        
        for i in range(1, len(swing_lows)):
            if swing_lows.iloc[i]["low"] < swing_lows.iloc[i-1]["low"]:
                idx = swing_lows.index[i]
                result.loc[idx, "BOS"] = -1
        
        # Detect CHoCH (reversal)
        for i in range(len(result) - 1):
            if result.iloc[i]["HighLow"] == 1:  # Was swing high
                future = result.iloc[i+1:]
                if len(future[future["HighLow"] == -1]) > 0:
                    next_low = future[future["HighLow"] == -1].iloc[0]
                    if next_low["low"] < result.iloc[i]["low"]:
                        result.loc[next_low.name, "CHOCH"] = -1
        
        return result

    def order_blocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Order Blocks."""
        result = df.copy()
        result["OB"] = 0
        result["Top"] = np.nan
        result["Bottom"] = np.nan
        
        for i in range(2, len(df) - 1):
            # Bullish OB: Last down candle before strong up move
            if df["close"].iloc[i] > df["close"].iloc[i-1] * 1.002:  # 0.2% move
                if df["close"].iloc[i-1] < df["open"].iloc[i-1]:  # Down candle
                    result.loc[result.index[i-1], "OB"] = 1
                    result.loc[result.index[i-1], "Top"] = df["high"].iloc[i-1]
                    result.loc[result.index[i-1], "Bottom"] = df["low"].iloc[i-1]
            
            # Bearish OB: Last up candle before strong down move
            if df["close"].iloc[i] < df["close"].iloc[i-1] * 0.998:  # 0.2% move
                if df["close"].iloc[i-1] > df["open"].iloc[i-1]:  # Up candle
                    result.loc[result.index[i-1], "OB"] = -1
                    result.loc[result.index[i-1], "Top"] = df["high"].iloc[i-1]
                    result.loc[result.index[i-1], "Bottom"] = df["low"].iloc[i-1]
        
        return result

    def fair_value_gaps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Fair Value Gaps (FVG)."""
        result = df.copy()
        result["FVG"] = 0
        result["Top"] = np.nan
        result["Bottom"] = np.nan
        
        for i in range(2, len(df)):
            # Bullish FVG: Gap between candle[i-2] high and candle[i] low
            if df["low"].iloc[i] > df["high"].iloc[i-2]:
                gap = df["low"].iloc[i] - df["high"].iloc[i-2]
                if gap > df["close"].iloc[i] * 0.0005:  # Minimum 0.05% gap
                    result.loc[result.index[i], "FVG"] = 1
                    result.loc[result.index[i], "Top"] = df["low"].iloc[i]
                    result.loc[result.index[i], "Bottom"] = df["high"].iloc[i-2]
            
            # Bearish FVG: Gap between candle[i-2] low and candle[i] high
            if df["high"].iloc[i] < df["low"].iloc[i-2]:
                gap = df["low"].iloc[i-2] - df["high"].iloc[i]
                if gap > df["close"].iloc[i] * 0.0005:
                    result.loc[result.index[i], "FVG"] = -1
                    result.loc[result.index[i], "Top"] = df["low"].iloc[i-2]
                    result.loc[result.index[i], "Bottom"] = df["high"].iloc[i]
        
        return result

    def liquidity(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect liquidity zones (equal highs/lows)."""
        result = self.swing_highs_lows(df)
        result["Liquidity"] = 0
        
        swing_highs = result[result["HighLow"] == 1]
        swing_lows = result[result["HighLow"] == -1]
        
        # Equal highs (buy-side liquidity)
        for i in range(1, len(swing_highs)):
            curr_high = swing_highs.iloc[i]["high"]
            prev_high = swing_highs.iloc[i-1]["high"]
            if abs(curr_high - prev_high) / prev_high < 0.001:  # Within 0.1%
                result.loc[swing_highs.index[i], "Liquidity"] = 1
        
        # Equal lows (sell-side liquidity)
        for i in range(1, len(swing_lows)):
            curr_low = swing_lows.iloc[i]["low"]
            prev_low = swing_lows.iloc[i-1]["low"]
            if abs(curr_low - prev_low) / prev_low < 0.001:
                result.loc[swing_lows.index[i], "Liquidity"] = -1
        
        return result

    def previous_high_low(self, df: pd.DataFrame, timeframe: str = "D") -> pd.DataFrame:
        """Get previous period high/low."""
        result = df.copy()
        result["PrevHigh"] = df["high"].shift(1)
        result["PrevLow"] = df["low"].shift(1)
        return result

    def sessions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Mark trading sessions (Asian, London, New York)."""
        result = df.copy()
        result["Session"] = "None"
        
        if not isinstance(df.index, pd.DatetimeIndex):
            return result
        
        hour = df.index.hour
        
        # Asian session: 00:00-09:00 UTC
        result.loc[(hour >= 0) & (hour < 9), "Session"] = "Asian"
        
        # London session: 08:00-17:00 UTC
        result.loc[(hour >= 8) & (hour < 17), "Session"] = "London"
        
        # New York session: 13:00-22:00 UTC
        result.loc[(hour >= 13) & (hour < 22), "Session"] = "NewYork"
        
        return result
