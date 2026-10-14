"""Parquet data cache — download once, backtest many times."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from jamlechtrader.core.enums import Timeframe
from jamlechtrader.core.models import Bar


class DataStore:
    """Cache market data as Parquet files for fast reloading."""

    def __init__(self, base_dir: str | Path = "./data_cache") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, symbol: str, timeframe: Timeframe) -> Path:
        return self.base_dir / f"{symbol}_{timeframe.value}.parquet"

    def download(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Download bars from Yahoo Finance and save as Parquet."""
        from jamlechtrader.data.yahoo_provider import YahooFinanceProvider

        provider = YahooFinanceProvider(symbol, timeframe, start, end)
        provider.load()
        bars = provider.get_all_bars()

        if not bars:
            logger.warning(f"No data downloaded for {symbol} {timeframe} from Yahoo Finance")
            return pd.DataFrame()

        df = pd.DataFrame([b.model_dump() for b in bars])
        path = self._file_path(symbol, timeframe)
        df.to_parquet(path, index=False)
        logger.info(f"Saved {len(df)} bars to {path}")
        return df

    def load(self, symbol: str, timeframe: Timeframe) -> list[Bar]:
        """Load bars from cached Parquet file."""
        path = self._file_path(symbol, timeframe)
        if not path.exists():
            logger.warning(f"No cached data at {path}")
            return []

        df = pd.read_parquet(path)
        bars = []
        for _, row in df.iterrows():
            bars.append(Bar(**row.to_dict()))
        logger.info(f"Loaded {len(bars)} cached bars from {path}")
        return bars

    def has_cache(self, symbol: str, timeframe: Timeframe) -> bool:
        return self._file_path(symbol, timeframe).exists()
