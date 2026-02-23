"""Enhanced MT5 mock with configurable failures, latency injection, and partial fills."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

from jamlechtrader.core.enums import OrderSide, OrderStatus
from jamlechtrader.core.models import Bar, Fill, Order, Position


@dataclass
class MockFillResult:
    retcode: int = 10009  # TRADE_RETCODE_DONE
    deal: int = 0
    order: int = 0
    price: float = 0.0
    volume: float = 0.0
    comment: str = ""


@dataclass
class MockTickResult:
    bid: float = 1.0850
    ask: float = 1.0852
    last: float = 1.0851
    volume: float = 100.0
    time: int = 0


@dataclass
class MockSymbolInfo:
    visible: bool = True
    trade_mode: int = 0
    digits: int = 5
    point: float = 0.00001
    trade_tick_size: float = 0.00001
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01


@dataclass
class MT5MockConfig:
    """Configuration for the enhanced MT5 mock."""

    failure_rate: float = 0.0  # probability of random failure [0.0, 1.0]
    latency_ms: tuple[float, float] = (0.0, 0.0)  # (min_ms, max_ms) latency injection
    partial_fill_rate: float = 0.0  # probability of partial fill
    partial_fill_pct: float = 0.5  # fraction filled on partial
    disconnect_after_calls: int = 0  # 0 = never disconnect
    reject_symbols: set[str] = field(default_factory=set)  # symbols that always reject


class MT5MockServer:
    """Full MT5 mock with configurable failures, latency, and partial fills."""

    def __init__(self, config: MT5MockConfig | None = None) -> None:
        self.config = config or MT5MockConfig()
        self._connected = True
        self._call_count = 0
        self._positions: dict[int, dict[str, Any]] = {}
        self._next_ticket = 1000
        self._next_deal = 2000
        self._order_history: list[dict[str, Any]] = []

    def _maybe_inject_latency(self) -> None:
        min_ms, max_ms = self.config.latency_ms
        if max_ms > 0:
            delay = random.uniform(min_ms, max_ms) / 1000.0
            time.sleep(delay)

    def _maybe_fail(self) -> bool:
        self._call_count += 1
        if self.config.disconnect_after_calls > 0 and self._call_count >= self.config.disconnect_after_calls:
            self._connected = False
            return True
        return random.random() < self.config.failure_rate

    def initialize(self, **kwargs) -> bool:
        self._connected = True
        self._call_count = 0
        return True

    def login(self, login: int = 0, password: str = "", server: str = "") -> bool:
        return self._connected

    def shutdown(self) -> None:
        self._connected = False

    def terminal_info(self):
        if not self._connected:
            return None
        mock = MagicMock()
        mock.connected = True
        return mock

    def last_error(self):
        return (0, "OK")

    def symbol_info(self, symbol: str):
        if symbol in self.config.reject_symbols:
            return None
        return MockSymbolInfo()

    def symbol_info_tick(self, symbol: str):
        self._maybe_inject_latency()
        if not self._connected or self._maybe_fail():
            return None
        return MockTickResult()

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        return True

    def order_send(self, request: dict) -> MockFillResult | None:
        self._maybe_inject_latency()

        if not self._connected or self._maybe_fail():
            return None

        symbol = request.get("symbol", "")
        if symbol in self.config.reject_symbols:
            return MockFillResult(retcode=10006, comment="Rejected")

        volume = request.get("volume", 0.01)
        price = request.get("price", 1.0850)

        # Partial fill simulation
        if random.random() < self.config.partial_fill_rate:
            volume = volume * self.config.partial_fill_pct

        self._next_ticket += 1
        self._next_deal += 1

        # Track as position
        self._positions[self._next_ticket] = {
            "symbol": symbol,
            "type": request.get("type", 0),
            "volume": volume,
            "price": price,
            "ticket": self._next_ticket,
        }

        self._order_history.append(request)

        return MockFillResult(
            retcode=10009,
            deal=self._next_deal,
            order=self._next_ticket,
            price=price,
            volume=volume,
        )

    def positions_get(self, symbol: str | None = None):
        if not self._connected:
            return None
        positions = list(self._positions.values())
        if symbol:
            positions = [p for p in positions if p["symbol"] == symbol]
        if not positions:
            return None
        results = []
        for p in positions:
            mock = MagicMock()
            mock.ticket = p["ticket"]
            mock.symbol = p["symbol"]
            mock.type = p["type"]
            mock.volume = p["volume"]
            mock.price_open = p["price"]
            mock.price_current = p["price"]
            mock.profit = 0.0
            mock.sl = 0.0
            mock.tp = 0.0
            mock.time = 0
            results.append(mock)
        return results

    def orders_get(self, symbol: str | None = None):
        return None

    def copy_rates_range(self, symbol, timeframe, start, end):
        return None

    def copy_rates_from_pos(self, symbol, timeframe, pos, count):
        return None

    def account_info(self):
        if not self._connected:
            return None
        mock = MagicMock()
        mock.login = 12345
        mock.server = "MockServer"
        mock.balance = 10000.0
        mock.equity = 10000.0
        mock.margin = 0.0
        mock.margin_free = 10000.0
        mock.leverage = 100
        mock.currency = "USD"
        mock.name = "Test Account"
        mock.company = "Mock Broker"
        return mock

    def install(self) -> None:
        """Install this mock into sys.modules as MetaTrader5."""
        import sys
        from types import ModuleType
        from tests.mt5_mock import mock_mt5

        # Override functions with our configurable ones
        mock_mt5.initialize = MagicMock(side_effect=self.initialize)
        mock_mt5.login = MagicMock(side_effect=self.login)
        mock_mt5.shutdown = MagicMock(side_effect=self.shutdown)
        mock_mt5.terminal_info = MagicMock(side_effect=self.terminal_info)
        mock_mt5.last_error = MagicMock(side_effect=self.last_error)
        mock_mt5.symbol_info = MagicMock(side_effect=self.symbol_info)
        mock_mt5.symbol_info_tick = MagicMock(side_effect=self.symbol_info_tick)
        mock_mt5.symbol_select = MagicMock(side_effect=self.symbol_select)
        mock_mt5.order_send = MagicMock(side_effect=self.order_send)
        mock_mt5.positions_get = MagicMock(side_effect=self.positions_get)
        mock_mt5.orders_get = MagicMock(side_effect=self.orders_get)
        mock_mt5.account_info = MagicMock(side_effect=self.account_info)
