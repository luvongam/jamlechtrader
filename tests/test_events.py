"""Tests for the event bus system."""

from datetime import UTC, datetime

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import EventBus, FillEvent, MarketEvent, SignalEvent


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(MarketEvent, handler)
        event = MarketEvent(symbol="EURUSD", timestamp=datetime.now(tz=UTC), data=None)
        bus.publish(event)

        assert len(received) == 1
        assert received[0] is event

    def test_multiple_handlers(self):
        bus = EventBus()
        received_a = []
        received_b = []

        bus.subscribe(MarketEvent, lambda e: received_a.append(e))
        bus.subscribe(MarketEvent, lambda e: received_b.append(e))

        event = MarketEvent(symbol="EURUSD", timestamp=datetime.now(tz=UTC), data=None)
        bus.publish(event)

        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_different_event_types(self):
        bus = EventBus()
        market_events = []
        signal_events = []

        bus.subscribe(MarketEvent, lambda e: market_events.append(e))
        bus.subscribe(SignalEvent, lambda e: signal_events.append(e))

        bus.publish(MarketEvent(symbol="EURUSD", timestamp=datetime.now(tz=UTC), data=None))
        bus.publish(SignalEvent(symbol="EURUSD", side=OrderSide.BUY))

        assert len(market_events) == 1
        assert len(signal_events) == 1

    def test_unsubscribe(self):
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(MarketEvent, handler)
        bus.unsubscribe(MarketEvent, handler)
        bus.publish(MarketEvent(symbol="EURUSD", timestamp=datetime.now(tz=UTC), data=None))

        assert len(received) == 0

    def test_clear(self):
        bus = EventBus()
        bus.subscribe(MarketEvent, lambda e: None)
        bus.subscribe(SignalEvent, lambda e: None)
        bus.clear()

        # Should not raise
        bus.publish(MarketEvent(symbol="EURUSD", timestamp=datetime.now(tz=UTC), data=None))

    def test_no_handlers_no_error(self):
        bus = EventBus()
        # Should not raise
        bus.publish(FillEvent(symbol="EURUSD", side=OrderSide.BUY, quantity=0.01, price=1.0))
