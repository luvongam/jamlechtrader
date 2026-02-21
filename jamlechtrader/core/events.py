"""Event system: event dataclasses and synchronous pub/sub bus."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from jamlechtrader.core.enums import OrderSide, OrderType


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


@dataclass
class MarketEvent:
    """New market data available (bar or tick)."""

    symbol: str
    timestamp: datetime
    data: Any  # Bar or Tick model


@dataclass
class SignalEvent:
    """Strategy signal to open/close a position."""

    symbol: str
    side: OrderSide
    strength: float = 1.0
    stop_loss: float | None = None
    take_profit: float | None = None
    timestamp: datetime = field(default_factory=_utcnow)


@dataclass
class OrderEvent:
    """Order to be sent to execution."""

    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    timestamp: datetime = field(default_factory=_utcnow)


@dataclass
class FillEvent:
    """Execution fill result."""

    symbol: str
    side: OrderSide
    quantity: float
    price: float
    commission: float = 0.0
    slippage: float = 0.0
    order_id: str = ""
    timestamp: datetime = field(default_factory=_utcnow)


EventHandler = Callable[[Any], None]


class EventBus:
    """Synchronous publish/subscribe event bus."""

    def __init__(self) -> None:
        self._handlers: dict[type, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: type, handler: EventHandler) -> None:
        self._handlers[event_type].remove(handler)

    def publish(self, event: Any) -> None:
        for handler in self._handlers.get(type(event), []):
            handler(event)

    def clear(self) -> None:
        self._handlers.clear()
