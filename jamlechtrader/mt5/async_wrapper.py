"""Async wrapper around synchronous MT5 calls via ThreadPoolExecutor."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from loguru import logger

from jamlechtrader.core.enums import Timeframe
from jamlechtrader.core.models import Bar, Fill, Order, Position

if TYPE_CHECKING:
    from jamlechtrader.mt5.connection import MT5Connection
    from jamlechtrader.mt5.data import MT5Data
    from jamlechtrader.mt5.executor import MT5Executor


class AsyncMT5:
    """Wraps synchronous MT5 calls in a thread pool for async usage.

    Uses a small ThreadPoolExecutor (4 workers) since MT5 operations
    are I/O-bound and the MT5 library is not thread-safe beyond
    sequential calls.
    """

    def __init__(
        self,
        connection: MT5Connection,
        executor: MT5Executor,
        data: MT5Data,
        max_workers: int = 4,
    ) -> None:
        self._connection = connection
        self._executor = executor
        self._data = data
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="mt5-async")

    async def _run_in_pool(self, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._pool, lambda: func(*args, **kwargs))

    async def connect(self) -> bool:
        return await self._run_in_pool(self._connection.connect)

    async def disconnect(self) -> None:
        await self._run_in_pool(self._connection.disconnect)

    async def is_connected(self) -> bool:
        return await self._run_in_pool(lambda: self._connection.is_connected)

    async def get_latest_bars(
        self, symbol: str, timeframe: Timeframe, count: int = 1
    ) -> list[Bar]:
        return await self._run_in_pool(self._data.get_latest_bars, symbol, timeframe, count)

    async def send_order(self, order: Order) -> Fill | None:
        return await self._run_in_pool(self._executor.send_order, order)

    async def close_position(self, position: Position) -> Fill | None:
        return await self._run_in_pool(self._executor.close_position, position)

    async def get_positions(self, symbol: str | None = None) -> list[Position]:
        return await self._run_in_pool(self._executor.get_positions, symbol)

    async def get_current_tick(self, symbol: str):
        import MetaTrader5 as mt5
        return await self._run_in_pool(mt5.symbol_info_tick, symbol)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False)
