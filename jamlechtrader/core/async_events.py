"""Async event system using asyncio.Queue."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine

from loguru import logger

AsyncEventHandler = Callable[[Any], Coroutine[Any, Any, None]]


class AsyncEventBus:
    """Asynchronous publish/subscribe event bus.

    Handlers are coroutines dispatched concurrently via asyncio.gather().
    """

    def __init__(self, max_queue_size: int = 10_000) -> None:
        self._handlers: dict[type, list[AsyncEventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=max_queue_size)
        self._running = False

    def subscribe(self, event_type: type, handler: AsyncEventHandler) -> None:
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: type, handler: AsyncEventHandler) -> None:
        self._handlers[event_type].remove(handler)

    async def publish(self, event: Any) -> None:
        await self._queue.put(event)

    async def process_events(self) -> None:
        """Process events from the queue until stopped."""
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            handlers = self._handlers.get(type(event), [])
            if not handlers:
                continue

            tasks = [asyncio.create_task(h(event)) for h in handlers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Async event handler error for {type(event).__name__}: {result}"
                    )

            self._queue.task_done()

    def stop(self) -> None:
        self._running = False

    def clear(self) -> None:
        self._handlers.clear()

    @property
    def pending(self) -> int:
        return self._queue.qsize()
