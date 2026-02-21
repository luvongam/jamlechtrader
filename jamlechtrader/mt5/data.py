"""MT5 data retrieval: historical bars, live ticks, symbol info."""

from __future__ import annotations

from datetime import UTC, datetime

import MetaTrader5 as mt5
import pandas as pd
from loguru import logger

from jamlechtrader.core.enums import Timeframe
from jamlechtrader.core.models import Bar, Tick
from jamlechtrader.mt5.utils import rates_to_bars, tick_to_model, to_mt5_timeframe


class MT5Data:
    """Retrieves market data from the MT5 terminal."""

    def get_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        """Fetch historical OHLCV bars."""
        mt5_tf = to_mt5_timeframe(timeframe)
        rates = mt5.copy_rates_range(symbol, mt5_tf, start, end)
        if rates is None or len(rates) == 0:
            logger.warning(f"No bars returned for {symbol} {timeframe} {start}-{end}")
            return []
        return rates_to_bars(rates, symbol)

    def get_bars_df(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Fetch historical bars as a DataFrame."""
        mt5_tf = to_mt5_timeframe(timeframe)
        rates = mt5.copy_rates_range(symbol, mt5_tf, start, end)
        if rates is None or len(rates) == 0:
            logger.warning(f"No bars returned for {symbol} {timeframe}")
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        df.rename(
            columns={"tick_volume": "tick_volume", "real_volume": "volume"},
            inplace=True,
        )
        return df

    def get_latest_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 100,
    ) -> list[Bar]:
        """Fetch the most recent N bars."""
        mt5_tf = to_mt5_timeframe(timeframe)
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
        if rates is None or len(rates) == 0:
            return []
        return rates_to_bars(rates, symbol)

    def get_ticks(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        flags: int = mt5.COPY_TICKS_ALL,
    ) -> list[Tick]:
        """Fetch historical ticks."""
        ticks = mt5.copy_ticks_range(symbol, start, end, flags)
        if ticks is None or len(ticks) == 0:
            return []
        result = []
        for t in ticks:
            result.append(
                Tick(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(t[0], tz=UTC),
                    bid=float(t[1]),
                    ask=float(t[2]),
                    last=float(t[3]),
                    volume=float(t[4]) if len(t) > 4 else 0.0,
                )
            )
        return result

    def get_current_tick(self, symbol: str) -> Tick | None:
        """Get the latest tick for a symbol."""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return tick_to_model(tick, symbol)

    def get_symbols(self, group: str = "") -> list[str]:
        """Get available symbol names, optionally filtered by group."""
        if group:
            symbols = mt5.symbols_get(group=group)
        else:
            symbols = mt5.symbols_get()
        if symbols is None:
            return []
        return [s.name for s in symbols]

    def symbol_info(self, symbol: str) -> dict | None:
        """Get detailed symbol information."""
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        return {
            "name": info.name,
            "description": info.description,
            "point": info.point,
            "digits": info.digits,
            "spread": info.spread,
            "trade_contract_size": info.trade_contract_size,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "currency_base": info.currency_base,
            "currency_profit": info.currency_profit,
            "currency_margin": info.currency_margin,
        }
