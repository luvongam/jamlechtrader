"""Tests for core Pydantic models."""

from datetime import datetime

from jamlechtrader.core.enums import OrderSide, OrderStatus, OrderType
from jamlechtrader.core.models import Bar, Fill, Order, Position, PortfolioSnapshot, Tick


class TestBar:
    def test_create_bar(self):
        bar = Bar(
            symbol="EURUSD",
            timestamp=datetime(2023, 1, 1),
            open=1.05,
            high=1.06,
            low=1.04,
            close=1.055,
            volume=100.0,
            spread=2,
        )
        assert bar.symbol == "EURUSD"
        assert bar.close == 1.055
        assert bar.spread == 2

    def test_bar_serialization(self):
        bar = Bar(
            symbol="GBPUSD",
            timestamp=datetime(2023, 6, 1),
            open=1.25,
            high=1.26,
            low=1.24,
            close=1.255,
            volume=200.0,
        )
        data = bar.model_dump()
        assert data["symbol"] == "GBPUSD"
        bar2 = Bar(**data)
        assert bar2 == bar


class TestTick:
    def test_create_tick(self):
        tick = Tick(
            symbol="EURUSD",
            timestamp=datetime(2023, 1, 1),
            bid=1.0500,
            ask=1.0502,
        )
        assert tick.bid == 1.0500
        assert tick.ask == 1.0502

    def test_tick_spread(self, sample_tick):
        assert sample_tick.ask - sample_tick.bid == pytest.approx(0.0002, abs=1e-5)


class TestOrder:
    def test_default_order(self):
        order = Order(
            symbol="EURUSD",
            side=OrderSide.BUY,
            quantity=0.01,
        )
        assert order.order_type == OrderType.MARKET
        assert order.status == OrderStatus.PENDING

    def test_limit_order(self):
        order = Order(
            symbol="USDJPY",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=0.1,
            price=150.00,
            stop_loss=151.00,
            take_profit=148.00,
        )
        assert order.price == 150.00
        assert order.stop_loss == 151.00


class TestPosition:
    def test_buy_pnl(self, sample_position):
        sample_position.update_pnl(1.0850)
        assert sample_position.unrealized_pnl == pytest.approx(0.0050 * 0.01, abs=1e-8)

    def test_sell_pnl(self):
        pos = Position(
            symbol="EURUSD",
            side=OrderSide.SELL,
            quantity=0.01,
            entry_price=1.0850,
            current_price=1.0800,
        )
        pos.update_pnl(1.0800)
        assert pos.unrealized_pnl == pytest.approx(0.0050 * 0.01, abs=1e-8)


class TestPortfolioSnapshot:
    def test_snapshot_defaults(self):
        snap = PortfolioSnapshot(cash=10000.0, equity=10000.0)
        assert snap.drawdown == 0.0
        assert snap.positions == []


import pytest
