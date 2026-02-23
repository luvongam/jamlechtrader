"""Event router — routes events to symbol-specific or type-specific queues."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from loguru import logger


class EventRouter:
    """Routes events to symbol-specific or event-type-specific queues.

    Useful for processing events for different symbols independently.
    """

    def __init__(self) -> None:
        self._symbol_queues: dict[str, asyncio.Queue[Any]] = defaultdict(
            lambda: asyncio.Queue(maxsize=5_000)
        )
        self._type_queues: dict[type, asyncio.Queue[Any]] = defaultdict(
            lambda: asyncio.Queue(maxsize=5_000)
        )

    async def route_by_symbol(self, event: Any) -> None:
        """Route an event to its symbol-specific queue."""
        symbol = getattr(event, "symbol", None)
        if symbol is None:
            logger.warning(f"Event {type(event).__name__} has no symbol attribute")
            return
        await self._symbol_queues[symbol].put(event)

    async def route_by_type(self, event: Any) -> None:
        """Route an event to its type-specific queue."""
        await self._type_queues[type(event)].put(event)

    def get_symbol_queue(self, symbol: str) -> asyncio.Queue[Any]:
        return self._symbol_queues[symbol]

    def get_type_queue(self, event_type: type) -> asyncio.Queue[Any]:
        return self._type_queues[event_type]

    @property
    def symbols(self) -> list[str]:
        return list(self._symbol_queues.keys())
