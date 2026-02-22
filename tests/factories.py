"""Test factories for generating domain objects."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import factory

from jamlechtrader.core.enums import OrderSide, OrderStatus, OrderType
from jamlechtrader.core.events import FillEvent, OrderEvent
from jamlechtrader.core.models import Bar, Fill, Order, Position


class BarFactory(factory.Factory):
    class Meta:
        model = Bar

    symbol = "EURUSD"
    timestamp = factory.LazyFunction(lambda: datetime.now(tz=UTC))
    open = factory.LazyAttribute(lambda o: 1.0800 + factory.random.randgen.uniform(-0.005, 0.005))
    high = factory.LazyAttribute(lambda o: o.open + factory.random.randgen.uniform(0.0005, 0.003))
    low = factory.LazyAttribute(lambda o: o.open - factory.random.randgen.uniform(0.0005, 0.003))
    close = factory.LazyAttribute(lambda o: factory.random.randgen.uniform(o.low, o.high))
    volume = factory.LazyFunction(lambda: factory.random.randgen.uniform(50, 500))
    spread = 2
    tick_volume = factory.LazyAttribute(lambda o: o.volume)


class OrderFactory(factory.Factory):
    class Meta:
        model = Order

    id = factory.LazyFunction(lambda: f"order-{factory.random.randgen.randint(1000, 9999)}")
    symbol = "EURUSD"
    side = OrderSide.BUY
    order_type = OrderType.MARKET
    quantity = 0.01
    price = None
    stop_loss = None
    take_profit = None
    status = OrderStatus.PENDING


class FillFactory(factory.Factory):
    class Meta:
        model = Fill

    id = factory.LazyFunction(lambda: f"fill-{factory.random.randgen.randint(1000, 9999)}")
    order_id = factory.LazyFunction(lambda: f"order-{factory.random.randgen.randint(1000, 9999)}")
    symbol = "EURUSD"
    side = OrderSide.BUY
    quantity = 0.01
    price = 1.0850
    commission = 0.07
    slippage = 0.0001


class PositionFactory(factory.Factory):
    class Meta:
        model = Position

    symbol = "EURUSD"
    side = OrderSide.BUY
    quantity = 0.01
    entry_price = 1.0800
    current_price = 1.0850
    stop_loss = None
    take_profit = None
    unrealized_pnl = 0.0
    ticket = factory.Sequence(lambda n: 1000 + n)


class OrderEventFactory(factory.Factory):
    class Meta:
        model = OrderEvent

    symbol = "EURUSD"
    side = OrderSide.BUY
    order_type = OrderType.MARKET
    quantity = 0.01
    price = None


class FillEventFactory(factory.Factory):
    class Meta:
        model = FillEvent

    symbol = "EURUSD"
    side = OrderSide.BUY
    quantity = 0.01
    price = 1.0850
    commission = 0.07
    slippage = 0.0001
    order_id = factory.LazyFunction(lambda: f"order-{factory.random.randgen.randint(1000, 9999)}")
