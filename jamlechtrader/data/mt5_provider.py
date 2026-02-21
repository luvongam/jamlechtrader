"""MT5 historical data provider — fetches bars from MT5 terminal."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from loguru import logger

from jamlechtrader.core.enums import Timeframe
from jamlechtrader.core.models import Bar
from jamlechtrader.data.base import AbstractDataHandler
from jamlechtrader.mt5.data import MT5Data


class MT5DataProvider(AbstractDataHandler):
    """Provides historical bars from MetaTrader 5."""

    def __init__(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.start = start
        self.end = end
        self._mt5_data = MT5Data()
        self._bars: list[Bar] = []
        self._index = 0

    def load(self) -> None:
        self._bars = self._mt5_data.get_bars(self.symbol, self.timeframe, self.start, self.end)
        self._index = 0
        logger.info(f"Loaded {len(self._bars)} bars for {self.symbol} {self.timeframe}")

    def bars(self) -> Iterator[Bar]:
        self._index = 0
        for bar in self._bars:
            self._index += 1
            yield bar

    def has_next(self) -> bool:
        return self._index < len(self._bars)

    def get_all_bars(self) -> list[Bar]:
        return list(self._bars)
