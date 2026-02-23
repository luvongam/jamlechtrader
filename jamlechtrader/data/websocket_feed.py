"""WebSocket feed for receiving real-time market data."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from jamlechtrader.core.async_events import AsyncEventBus


class WebSocketFeed:
    """Receive real-time market data via WebSocket and publish MarketEvents.

    Connects to a WebSocket server and publishes incoming data as
    MarketEvent instances to the AsyncEventBus.
    """

    def __init__(
        self,
        url: str,
        event_bus: AsyncEventBus,
        symbols: list[str] | None = None,
    ) -> None:
        self._url = url
        self._event_bus = event_bus
        self._symbols = symbols or []
        self._running = False
        self._ws = None

    async def connect(self) -> None:
        """Connect to the WebSocket server and start receiving data."""
        import websockets

        self._running = True
        logger.info(f"Connecting to WebSocket feed: {self._url}")

        while self._running:
            try:
                async with websockets.connect(self._url) as ws:
                    self._ws = ws
                    logger.info("WebSocket feed connected")

                    if self._symbols:
                        subscribe_msg = json.dumps({
                            "action": "subscribe",
                            "symbols": self._symbols,
                        })
                        await ws.send(subscribe_msg)

                    async for message in ws:
                        if not self._running:
                            break
                        await self._process_message(message)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"WebSocket feed error: {e}")
                if self._running:
                    logger.info("Reconnecting WebSocket in 5s...")
                    await asyncio.sleep(5)

    async def _process_message(self, raw_message: str | bytes) -> None:
        """Parse incoming WebSocket message and publish as MarketEvent."""
        try:
            data = json.loads(raw_message)
            symbol = data.get("symbol")
            if symbol is None:
                return

            from jamlechtrader.core.events import MarketEvent
            from jamlechtrader.core.models import Tick

            tick = Tick(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(data.get("timestamp", 0), tz=UTC),
                bid=data.get("bid", 0.0),
                ask=data.get("ask", 0.0),
                last=data.get("last", 0.0),
                volume=data.get("volume", 0.0),
            )

            event = MarketEvent(
                symbol=symbol,
                timestamp=tick.timestamp,
                data=tick,
            )
            await self._event_bus.publish(event)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse WebSocket message: {e}")

    def stop(self) -> None:
        self._running = False

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and not self._ws.closed
