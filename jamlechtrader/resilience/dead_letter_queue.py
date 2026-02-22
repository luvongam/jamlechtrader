"""Dead letter queue for failed orders awaiting retry or review."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger


@dataclass
class DeadLetterEntry:
    order_data: dict[str, Any]
    error: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    retry_count: int = 0


class DeadLetterQueue:
    """Thread-safe queue for failed orders."""

    def __init__(self, max_size: int = 1000) -> None:
        self._queue: deque[DeadLetterEntry] = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add(self, order_data: dict[str, Any], error: str) -> None:
        entry = DeadLetterEntry(order_data=order_data, error=error)
        with self._lock:
            self._queue.append(entry)
        logger.warning(f"Order added to dead letter queue: {error}")

    def peek(self) -> DeadLetterEntry | None:
        with self._lock:
            return self._queue[0] if self._queue else None

    def pop(self) -> DeadLetterEntry | None:
        with self._lock:
            return self._queue.popleft() if self._queue else None

    def retry(self) -> DeadLetterEntry | None:
        """Pop the oldest entry for retry, incrementing its retry count."""
        entry = self.pop()
        if entry is not None:
            entry.retry_count += 1
        return entry

    def discard(self) -> DeadLetterEntry | None:
        """Discard the oldest entry."""
        return self.pop()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def all_entries(self) -> list[DeadLetterEntry]:
        with self._lock:
            return list(self._queue)
