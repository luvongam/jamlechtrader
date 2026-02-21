"""Technical indicators implemented with pandas/numpy.

Uses pandas-ta when available, falls back to pure pandas/numpy implementations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta

    _HAS_PANDAS_TA = True
except ImportError:
    _HAS_PANDAS_TA = False


def sma(series: pd.Series, period: int) -> pd.Series:
    if _HAS_PANDAS_TA:
        return ta.sma(series, length=period)
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    if _HAS_PANDAS_TA:
        return ta.ema(series, length=period)
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    if _HAS_PANDAS_TA:
        return ta.rsi(series, length=period)
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def bollinger_bands(
    series: pd.Series, period: int = 20, std: float = 2.0
) -> pd.DataFrame:
    """Returns DataFrame with columns: BBL_{period}_{std}, BBM_{period}_{std}, BBU_{period}_{std}."""
    if _HAS_PANDAS_TA:
        return ta.bbands(series, length=period, std=std)
    mid = series.rolling(window=period).mean()
    std_dev = series.rolling(window=period).std()
    upper = mid + std * std_dev
    lower = mid - std * std_dev
    return pd.DataFrame({
        f"BBL_{period}_{std}": lower,
        f"BBM_{period}_{std}": mid,
        f"BBU_{period}_{std}": upper,
    })


def atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    if _HAS_PANDAS_TA:
        return ta.atr(high=high, low=low, close=close, length=period)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Returns DataFrame with MACD line, histogram, and signal line."""
    if _HAS_PANDAS_TA:
        return ta.macd(series, fast=fast, slow=slow, signal=signal)
    fast_ema = series.ewm(span=fast, adjust=False).mean()
    slow_ema = series.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        f"MACD_{fast}_{slow}_{signal}": macd_line,
        f"MACDh_{fast}_{slow}_{signal}": histogram,
        f"MACDs_{fast}_{slow}_{signal}": signal_line,
    })


def adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.DataFrame:
    """Returns DataFrame with ADX, +DI, -DI."""
    if _HAS_PANDAS_TA:
        return ta.adx(high=high, low=low, close=close, length=period)

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr_val = atr(high, low, close, period)

    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr_val)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr_val)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx_val = dx.rolling(window=period).mean()

    return pd.DataFrame({
        f"ADX_{period}": adx_val,
        f"DMP_{period}": plus_di,
        f"DMN_{period}": minus_di,
    })
