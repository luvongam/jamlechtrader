"""Tests for MT5 bridge client classes and factory."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest
import respx

from jamlechtrader.config.settings import Settings
from jamlechtrader.core.enums import OrderSide, OrderType, Timeframe
from jamlechtrader.core.models import Order, Position
from jamlechtrader.mt5.bridge_client import (
    BridgeMT5Connection,
    BridgeMT5Data,
    BridgeMT5Executor,
)
from jamlechtrader.mt5.factory import (
    create_mt5_connection,
    create_mt5_data,
    create_mt5_executor,
)

BRIDGE_URL = "http://mt5bridge.test:8000"


def _settings(bridge_url: str = BRIDGE_URL) -> Settings:
    return Settings(
        mt5_bridge_url=bridge_url,
        mt5_login=0,
        mt5_password="",
        mt5_server="",
    )


# ---------------------------------------------------------------------------
# BridgeMT5Connection
# ---------------------------------------------------------------------------


class TestBridgeConnection:
    @respx.mock
    def test_connect_success(self):
        respx.get(f"{BRIDGE_URL}/health").mock(
            return_value=httpx.Response(200, json={"status": "ok", "mt5_connected": True})
        )
        conn = BridgeMT5Connection(_settings())
        assert conn.connect() is True
        conn.disconnect()

    @respx.mock
    def test_connect_mt5_not_connected(self):
        respx.get(f"{BRIDGE_URL}/health").mock(
            return_value=httpx.Response(200, json={"status": "ok", "mt5_connected": False})
        )
        conn = BridgeMT5Connection(_settings())
        assert conn.connect() is False

    @respx.mock
    def test_connect_server_down(self):
        respx.get(f"{BRIDGE_URL}/health").mock(side_effect=httpx.ConnectError("refused"))
        conn = BridgeMT5Connection(_settings())
        assert conn.connect() is False

    @respx.mock
    def test_account_info(self):
        respx.get(f"{BRIDGE_URL}/health").mock(
            return_value=httpx.Response(200, json={"status": "ok", "mt5_connected": True})
        )
        respx.get(f"{BRIDGE_URL}/account").mock(
            return_value=httpx.Response(
                200,
                json={
                    "login": 12345,
                    "server": "Demo",
                    "balance": 10000.0,
                    "equity": 10050.0,
                    "margin": 100.0,
                    "free_margin": 9950.0,
                    "leverage": 100,
                    "currency": "USD",
                    "name": "Test User",
                    "company": "TestBroker",
                },
            )
        )
        conn = BridgeMT5Connection(_settings())
        conn.connect()
        info = conn.account_info()
        assert info is not None
        assert info.login == 12345
        assert info.server == "Demo"
        assert info.balance == 10000.0
        assert info.currency == "USD"
        assert info.name == "Test User"
        conn.disconnect()

    @respx.mock
    def test_is_connected_true(self):
        respx.get(f"{BRIDGE_URL}/health").mock(
            return_value=httpx.Response(200, json={"status": "ok", "mt5_connected": True})
        )
        conn = BridgeMT5Connection(_settings())
        conn.connect()
        assert conn.is_connected is True
        conn.disconnect()

    @respx.mock
    def test_is_connected_false_when_not_connected(self):
        conn = BridgeMT5Connection(_settings())
        assert conn.is_connected is False

    @respx.mock
    def test_reconnect(self):
        respx.get(f"{BRIDGE_URL}/health").mock(
            return_value=httpx.Response(200, json={"status": "ok", "mt5_connected": True})
        )
        conn = BridgeMT5Connection(_settings())
        conn.connect()
        assert conn.reconnect() is True
        conn.disconnect()

    @respx.mock
    def test_context_manager(self):
        respx.get(f"{BRIDGE_URL}/health").mock(
            return_value=httpx.Response(200, json={"status": "ok", "mt5_connected": True})
        )
        with BridgeMT5Connection(_settings()) as conn:
            assert conn.is_connected is True


# ---------------------------------------------------------------------------
# BridgeMT5Executor
# ---------------------------------------------------------------------------


class TestBridgeExecutor:
    @respx.mock
    def test_send_market_order(self):
        respx.post(f"{BRIDGE_URL}/order").mock(
            return_value=httpx.Response(
                200,
                json={
                    "order_id": 100,
                    "deal_id": 200,
                    "volume": 0.01,
                    "price": 1.1050,
                    "comment": "ok",
                },
            )
        )
        executor = BridgeMT5Executor(BRIDGE_URL)
        order = Order(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01,
        )
        fill = executor.send_order(order)
        assert fill is not None
        assert fill.price == 1.1050
        assert fill.order_id == "100"
        assert fill.side == OrderSide.BUY

    @respx.mock
    def test_send_limit_order(self):
        respx.post(f"{BRIDGE_URL}/order").mock(
            return_value=httpx.Response(
                200,
                json={
                    "order_id": 101,
                    "deal_id": 201,
                    "volume": 0.02,
                    "price": 1.1000,
                    "comment": "ok",
                },
            )
        )
        executor = BridgeMT5Executor(BRIDGE_URL)
        order = Order(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.02,
            price=1.1000,
        )
        fill = executor.send_order(order)
        assert fill is not None
        assert fill.price == 1.1000

        # Verify the payload sent to bridge
        body = respx.calls.last.request.content
        import json

        payload = json.loads(body)
        assert payload["order_type"] == "BUY_LIMIT"

    @respx.mock
    def test_send_order_failure(self):
        respx.post(f"{BRIDGE_URL}/order").mock(
            return_value=httpx.Response(500, json={"detail": "Order failed"})
        )
        executor = BridgeMT5Executor(BRIDGE_URL)
        order = Order(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01,
        )
        fill = executor.send_order(order)
        assert fill is None

    @respx.mock
    def test_close_position(self):
        respx.post(f"{BRIDGE_URL}/close").mock(
            return_value=httpx.Response(
                200,
                json={
                    "order_id": 300,
                    "deal_id": 400,
                    "volume": 0.01,
                    "price": 1.1100,
                    "comment": "closed",
                },
            )
        )
        executor = BridgeMT5Executor(BRIDGE_URL)
        position = Position(
            symbol="EURUSD",
            side=OrderSide.BUY,
            quantity=0.01,
            entry_price=1.1050,
            ticket=12345,
        )
        fill = executor.close_position(position)
        assert fill is not None
        assert fill.side == OrderSide.SELL  # opposite side
        assert fill.price == 1.1100

    @respx.mock
    def test_modify_position(self):
        respx.post(f"{BRIDGE_URL}/modify").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        executor = BridgeMT5Executor(BRIDGE_URL)
        result = executor.modify_position(
            ticket=12345, symbol="EURUSD", stop_loss=1.1000, take_profit=1.1200
        )
        assert result is True

    @respx.mock
    def test_modify_position_failure(self):
        respx.post(f"{BRIDGE_URL}/modify").mock(
            return_value=httpx.Response(500, json={"detail": "Modify failed"})
        )
        executor = BridgeMT5Executor(BRIDGE_URL)
        result = executor.modify_position(
            ticket=12345, symbol="EURUSD", stop_loss=1.1000
        )
        assert result is False

    @respx.mock
    def test_get_positions(self):
        respx.get(f"{BRIDGE_URL}/positions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "positions": [
                        {
                            "ticket": 1001,
                            "symbol": "EURUSD",
                            "type": 0,
                            "volume": 0.01,
                            "price_open": 1.1050,
                            "price_current": 1.1060,
                            "sl": 1.1000,
                            "tp": 1.1200,
                            "profit": 1.0,
                            "time": 1700000000,
                            "comment": "test",
                        }
                    ]
                },
            )
        )
        executor = BridgeMT5Executor(BRIDGE_URL)
        positions = executor.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "EURUSD"
        assert positions[0].side == OrderSide.BUY
        assert positions[0].ticket == 1001

    @respx.mock
    def test_get_positions_by_symbol(self):
        respx.get(f"{BRIDGE_URL}/positions/EURUSD").mock(
            return_value=httpx.Response(200, json={"positions": []})
        )
        executor = BridgeMT5Executor(BRIDGE_URL)
        positions = executor.get_positions(symbol="EURUSD")
        assert positions == []

    @respx.mock
    def test_get_open_orders(self):
        respx.get(f"{BRIDGE_URL}/orders").mock(
            return_value=httpx.Response(
                200,
                json={
                    "orders": [
                        {
                            "ticket": 2001,
                            "symbol": "GBPUSD",
                            "type": 2,
                            "volume": 0.05,
                            "price": 1.2500,
                            "sl": 0,
                            "tp": 0,
                            "comment": "limit",
                        }
                    ]
                },
            )
        )
        executor = BridgeMT5Executor(BRIDGE_URL)
        orders = executor.get_open_orders()
        assert len(orders) == 1
        assert orders[0]["ticket"] == 2001

    @respx.mock
    def test_circuit_breaker_blocks_order(self):
        executor = BridgeMT5Executor(BRIDGE_URL)
        # Trip the circuit breaker
        for _ in range(5):
            executor._cb.record_failure()

        order = Order(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01,
        )
        fill = executor.send_order(order)
        assert fill is None


# ---------------------------------------------------------------------------
# BridgeMT5Data
# ---------------------------------------------------------------------------


class TestBridgeData:
    @respx.mock
    def test_get_bars(self):
        respx.post(f"{BRIDGE_URL}/bars").mock(
            return_value=httpx.Response(
                200,
                json={
                    "bars": [
                        {
                            "time": 1700000000,
                            "open": 1.1050,
                            "high": 1.1070,
                            "low": 1.1040,
                            "close": 1.1060,
                            "tick_volume": 150,
                            "spread": 2,
                            "volume": 150,
                        }
                    ]
                },
            )
        )
        data = BridgeMT5Data(BRIDGE_URL)
        bars = data.get_bars(
            "EURUSD", Timeframe.H1, datetime(2023, 1, 1), datetime(2023, 12, 31)
        )
        assert len(bars) == 1
        assert bars[0].symbol == "EURUSD"
        assert bars[0].close == 1.1060

    @respx.mock
    def test_get_bars_empty(self):
        respx.post(f"{BRIDGE_URL}/bars").mock(
            return_value=httpx.Response(404, json={"detail": "No data found"})
        )
        data = BridgeMT5Data(BRIDGE_URL)
        bars = data.get_bars(
            "EURUSD", Timeframe.H1, datetime(2023, 1, 1), datetime(2023, 12, 31)
        )
        assert bars == []

    @respx.mock
    def test_get_latest_bars(self):
        respx.post(f"{BRIDGE_URL}/bars/latest").mock(
            return_value=httpx.Response(
                200,
                json={
                    "bars": [
                        {
                            "time": 1700000000,
                            "open": 1.1050,
                            "high": 1.1070,
                            "low": 1.1040,
                            "close": 1.1060,
                            "tick_volume": 150,
                            "spread": 2,
                            "volume": 150,
                        },
                        {
                            "time": 1700003600,
                            "open": 1.1060,
                            "high": 1.1080,
                            "low": 1.1050,
                            "close": 1.1075,
                            "tick_volume": 200,
                            "spread": 2,
                            "volume": 200,
                        },
                    ]
                },
            )
        )
        data = BridgeMT5Data(BRIDGE_URL)
        bars = data.get_latest_bars("EURUSD", Timeframe.H1, count=2)
        assert len(bars) == 2
        assert bars[1].close == 1.1075

    @respx.mock
    def test_get_current_tick(self):
        respx.get(f"{BRIDGE_URL}/tick/EURUSD").mock(
            return_value=httpx.Response(
                200,
                json={
                    "bid": 1.1050,
                    "ask": 1.1052,
                    "last": 1.1051,
                    "volume": 10.0,
                    "time": 1700000000,
                },
            )
        )
        data = BridgeMT5Data(BRIDGE_URL)
        tick = data.get_current_tick("EURUSD")
        assert tick is not None
        assert tick.bid == 1.1050
        assert tick.ask == 1.1052
        assert tick.symbol == "EURUSD"

    @respx.mock
    def test_get_current_tick_not_found(self):
        respx.get(f"{BRIDGE_URL}/tick/UNKNOWN").mock(
            return_value=httpx.Response(404, json={"detail": "No tick"})
        )
        data = BridgeMT5Data(BRIDGE_URL)
        tick = data.get_current_tick("UNKNOWN")
        assert tick is None

    @respx.mock
    def test_get_symbols(self):
        respx.get(f"{BRIDGE_URL}/symbols").mock(
            return_value=httpx.Response(
                200,
                json={
                    "symbols": [
                        {"name": "EURUSD", "description": "Euro/USD", "digits": 5},
                        {"name": "GBPUSD", "description": "GBP/USD", "digits": 5},
                    ]
                },
            )
        )
        data = BridgeMT5Data(BRIDGE_URL)
        symbols = data.get_symbols()
        assert symbols == ["EURUSD", "GBPUSD"]

    @respx.mock
    def test_symbol_info(self):
        respx.get(f"{BRIDGE_URL}/symbol/EURUSD").mock(
            return_value=httpx.Response(
                200,
                json={
                    "name": "EURUSD",
                    "description": "Euro vs US Dollar",
                    "point": 0.00001,
                    "digits": 5,
                    "spread": 10,
                    "trade_contract_size": 100000,
                    "volume_min": 0.01,
                    "volume_max": 100.0,
                    "volume_step": 0.01,
                    "currency_base": "EUR",
                    "currency_profit": "USD",
                    "currency_margin": "EUR",
                },
            )
        )
        data = BridgeMT5Data(BRIDGE_URL)
        info = data.symbol_info("EURUSD")
        assert info is not None
        assert info["name"] == "EURUSD"
        assert info["digits"] == 5

    @respx.mock
    def test_symbol_info_not_found(self):
        respx.get(f"{BRIDGE_URL}/symbol/UNKNOWN").mock(
            return_value=httpx.Response(404, json={"detail": "Not found"})
        )
        data = BridgeMT5Data(BRIDGE_URL)
        info = data.symbol_info("UNKNOWN")
        assert info is None

    @respx.mock
    def test_get_bars_df(self):
        respx.post(f"{BRIDGE_URL}/bars").mock(
            return_value=httpx.Response(
                200,
                json={
                    "bars": [
                        {
                            "time": 1700000000,
                            "open": 1.1050,
                            "high": 1.1070,
                            "low": 1.1040,
                            "close": 1.1060,
                            "tick_volume": 150,
                            "spread": 2,
                            "volume": 150,
                        }
                    ]
                },
            )
        )
        data = BridgeMT5Data(BRIDGE_URL)
        df = data.get_bars_df(
            "EURUSD", Timeframe.H1, datetime(2023, 1, 1), datetime(2023, 12, 31)
        )
        assert len(df) == 1
        assert "close" in df.columns

    def test_get_ticks_returns_empty(self):
        data = BridgeMT5Data(BRIDGE_URL)
        ticks = data.get_ticks("EURUSD", datetime(2023, 1, 1), datetime(2023, 12, 31))
        assert ticks == []


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactory:
    def test_returns_local_when_no_url(self):
        settings = Settings(
            mt5_bridge_url="",
            mt5_login=0,
            mt5_password="",
            mt5_server="",
        )
        conn = create_mt5_connection(settings)
        executor = create_mt5_executor(settings)
        data = create_mt5_data(settings)

        from jamlechtrader.mt5.connection import MT5Connection
        from jamlechtrader.mt5.data import MT5Data
        from jamlechtrader.mt5.executor import MT5Executor

        assert isinstance(conn, MT5Connection)
        assert isinstance(executor, MT5Executor)
        assert isinstance(data, MT5Data)

    def test_returns_bridge_when_url_set(self):
        settings = _settings()
        conn = create_mt5_connection(settings)
        executor = create_mt5_executor(settings)
        data = create_mt5_data(settings)

        assert isinstance(conn, BridgeMT5Connection)
        assert isinstance(executor, BridgeMT5Executor)
        assert isinstance(data, BridgeMT5Data)


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------


class TestResilience:
    @respx.mock
    def test_retry_on_timeout(self):
        """Verify the request retries on transient failures."""
        route = respx.post(f"{BRIDGE_URL}/bars/latest")
        route.side_effect = [
            httpx.ConnectTimeout("timeout"),
            httpx.ConnectTimeout("timeout"),
            httpx.Response(
                200,
                json={
                    "bars": [
                        {
                            "time": 1700000000,
                            "open": 1.1,
                            "high": 1.2,
                            "low": 1.0,
                            "close": 1.15,
                            "tick_volume": 100,
                            "spread": 1,
                            "volume": 100,
                        }
                    ]
                },
            ),
        ]
        data = BridgeMT5Data(BRIDGE_URL)
        bars = data.get_latest_bars("EURUSD", Timeframe.H1, count=1)
        assert len(bars) == 1
        assert route.call_count == 3

    @respx.mock
    def test_retry_exhausted(self):
        """All 3 retries fail — returns empty list."""
        respx.post(f"{BRIDGE_URL}/bars/latest").mock(
            side_effect=httpx.ConnectTimeout("timeout")
        )
        data = BridgeMT5Data(BRIDGE_URL)
        bars = data.get_latest_bars("EURUSD", Timeframe.H1, count=1)
        assert bars == []

    @respx.mock
    def test_circuit_breaker_opens_after_failures(self):
        executor = BridgeMT5Executor(BRIDGE_URL)
        # Manually trip the CB
        for _ in range(5):
            executor._cb.record_failure()

        from jamlechtrader.resilience.circuit_breaker import CircuitState

        assert executor._cb.state == CircuitState.OPEN

        # Orders should be rejected
        order = Order(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01,
        )
        assert executor.send_order(order) is None

    @respx.mock
    def test_circuit_breaker_recovers(self):
        from jamlechtrader.resilience.circuit_breaker import CircuitState

        executor = BridgeMT5Executor(BRIDGE_URL)
        executor._cb = executor._cb.__class__(
            name="test_cb", failure_threshold=2, recovery_timeout=0.1
        )

        # Trip it
        executor._cb.record_failure()
        executor._cb.record_failure()
        assert executor._cb.state == CircuitState.OPEN

        # Wait for recovery
        time.sleep(0.15)
        assert executor._cb.state == CircuitState.HALF_OPEN
