"""Enhanced Smart Money Concepts analyzer — delegates to smartmoneyconcepts package."""

from __future__ import annotations

import os

import pandas as pd
from loguru import logger

# Suppress the package's GitHub star banner
os.environ.setdefault("SMC_CREDIT", "0")

from smartmoneyconcepts import smc  # noqa: E402

from jamlechtrader.core.constants import (
    SMC_BOS_CLOSE_BREAK,
    SMC_DEFAULT_SWING_LENGTH,
    SMC_FVG_JOIN_CONSECUTIVE,
    SMC_LIQUIDITY_RANGE_PCT,
    SMC_OB_CLOSE_MITIGATION,
)


def _prepare_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Select and normalise columns expected by smartmoneyconcepts."""
    cols = {"open": "open", "high": "high", "low": "low", "close": "close"}
    ohlc = df[list(cols.keys())].copy()
    if "volume" in df.columns:
        ohlc["volume"] = df["volume"].values
    else:
        ohlc["volume"] = 0.0
    ohlc = ohlc.reset_index(drop=True)
    return ohlc


class SMCAnalyzer:
    """Professional Smart Money Concepts analyzer backed by smartmoneyconcepts."""

    def __init__(self, swing_length: int = SMC_DEFAULT_SWING_LENGTH) -> None:
        self.swing_length = swing_length

    def swing_highs_lows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect swing highs and lows.

        Returns DataFrame with columns: HighLow (1/-1/NaN), Level.
        """
        ohlc = _prepare_ohlc(df)
        result = smc.swing_highs_lows(ohlc, swing_length=self.swing_length)
        result.index = df.index
        return result

    def bos_choch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Break of Structure and Change of Character.

        Returns DataFrame with columns: BOS, CHOCH, Level, BrokenIndex.
        """
        ohlc = _prepare_ohlc(df)
        swings = smc.swing_highs_lows(ohlc, swing_length=self.swing_length)
        result = smc.bos_choch(ohlc, swings, close_break=SMC_BOS_CLOSE_BREAK)
        result.index = df.index
        return result

    def order_blocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Order Blocks.

        Returns DataFrame with columns: OB (1/-1/NaN), Top, Bottom,
        OBVolume, MitigatedIndex, Percentage.
        """
        ohlc = _prepare_ohlc(df)
        swings = smc.swing_highs_lows(ohlc, swing_length=self.swing_length)
        result = smc.ob(ohlc, swings, close_mitigation=SMC_OB_CLOSE_MITIGATION)
        result.index = df.index
        return result

    def fair_value_gaps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect Fair Value Gaps.

        Returns DataFrame with columns: FVG (1/-1/NaN), Top, Bottom,
        MitigatedIndex.
        """
        ohlc = _prepare_ohlc(df)
        result = smc.fvg(ohlc, join_consecutive=SMC_FVG_JOIN_CONSECUTIVE)
        result.index = df.index
        return result

    def liquidity(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect liquidity zones.

        Returns DataFrame with columns: Liquidity (1/-1/NaN), Level, End, Swept.
        """
        ohlc = _prepare_ohlc(df)
        swings = smc.swing_highs_lows(ohlc, swing_length=self.swing_length)
        result = smc.liquidity(ohlc, swings, range_percent=SMC_LIQUIDITY_RANGE_PCT)
        result.index = df.index
        return result

    def previous_high_low(self, df: pd.DataFrame, time_frame: str = "1D") -> pd.DataFrame:
        """Get previous period high/low.

        Returns DataFrame with columns: PreviousHigh, PreviousLow,
        BrokenHigh, BrokenLow.
        """
        ohlc = _prepare_ohlc(df)
        if isinstance(df.index, pd.DatetimeIndex):
            ohlc.index = df.index
        result = smc.previous_high_low(ohlc, time_frame=time_frame)
        result.index = df.index
        return result

    def sessions(self, df: pd.DataFrame, session: str = "London") -> pd.DataFrame:
        """Mark trading sessions.

        Returns DataFrame with columns: Active (0/1), High, Low.
        """
        ohlc = _prepare_ohlc(df)
        if isinstance(df.index, pd.DatetimeIndex):
            ohlc.index = df.index
        result = smc.sessions(ohlc, session=session)
        result.index = df.index
        return result

    def retracements(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate retracement percentages from swings.

        Returns DataFrame with columns: Direction, CurrentRetracement%,
        DeepestRetracement%.
        """
        ohlc = _prepare_ohlc(df)
        swings = smc.swing_highs_lows(ohlc, swing_length=self.swing_length)
        result = smc.retracements(ohlc, swings)
        result.index = df.index
        return result
