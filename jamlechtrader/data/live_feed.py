"""Live tick feed from MT5 — polls for new ticks and emits MarketEvents."""

from __future__ import annotations

import time
from datetime import datetime

from loguru import logger

from jamlechtrader.core.events import EventBus, MarketEvent
from jamlechtrader.core.models import Tick
from jamlechtrader.mt5.data import MT5Data


class LiveFeed:
    """Polls MT5 for live ticks and publishes MarketEvents."""

    def __init__(
        self,
        symbol: str,
        event_bus: EventBus,
        poll_interval: float = 0.1,
    ) -> None:
        self.symbol = symbol
        self.event_bus = event_bus
        self.poll_interval = poll_interval
        self._mt5_data = MT5Data()
        self._running = False
        self._last_tick_time: datetime | None = None

    def start(self) -> None:
        """Start polling for ticks. Blocks until stop() is called."""
        self._running = True
        logger.info(f"LiveFeed started for {self.symbol}")

        while self._running:
            tick = self._mt5_data.get_current_tick(self.symbol)
            if tick is not None and tick.timestamp != self._last_tick_time:
                self._last_tick_time = tick.timestamp
                event = MarketEvent(
                    symbol=self.symbol,
                    timestamp=tick.timestamp,
                    data=tick,
                )
                self.event_bus.publish(event)
            time.sleep(self.poll_interval)

    def stop(self) -> None:
        """Stop the feed loop."""
        self._running = False
        logger.info(f"LiveFeed stopped for {self.symbol}")

    def get_latest_tick(self) -> Tick | None:
        return self._mt5_data.get_current_tick(self.symbol)
