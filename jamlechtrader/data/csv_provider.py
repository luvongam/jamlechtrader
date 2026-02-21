"""CSV/Parquet data provider for offline testing."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
from loguru import logger

from jamlechtrader.core.models import Bar
from jamlechtrader.data.base import AbstractDataHandler


class CSVDataProvider(AbstractDataHandler):
    """Loads bars from a CSV or Parquet file."""

    def __init__(self, file_path: str | Path, symbol: str = "UNKNOWN") -> None:
        self.file_path = Path(file_path)
        self.symbol = symbol
        self._bars: list[Bar] = []
        self._index = 0

    def load(self) -> None:
        if self.file_path.suffix == ".parquet":
            df = pd.read_parquet(self.file_path)
        else:
            df = pd.read_csv(self.file_path, parse_dates=["time"])

        # Normalize column names
        col_map = {}
        for col in df.columns:
            lower = col.lower()
            if lower in ("time", "datetime", "date", "timestamp"):
                col_map[col] = "time"
            elif lower in ("open",):
                col_map[col] = "open"
            elif lower in ("high",):
                col_map[col] = "high"
            elif lower in ("low",):
                col_map[col] = "low"
            elif lower in ("close",):
                col_map[col] = "close"
            elif lower in ("volume", "real_volume"):
                col_map[col] = "volume"
            elif lower in ("spread",):
                col_map[col] = "spread"
            elif lower in ("tick_volume",):
                col_map[col] = "tick_volume"
        df.rename(columns=col_map, inplace=True)

        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])

        for col in ("spread", "tick_volume"):
            if col not in df.columns:
                df[col] = 0

        if "volume" not in df.columns:
            df["volume"] = df.get("tick_volume", 0)

        self._bars = []
        for _, row in df.iterrows():
            self._bars.append(
                Bar(
                    symbol=self.symbol,
                    timestamp=row["time"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    spread=int(row["spread"]),
                    tick_volume=float(row["tick_volume"]),
                )
            )
        self._index = 0
        logger.info(f"Loaded {len(self._bars)} bars from {self.file_path}")

    def bars(self) -> Iterator[Bar]:
        self._index = 0
        for bar in self._bars:
            self._index += 1
            yield bar

    def has_next(self) -> bool:
        return self._index < len(self._bars)
