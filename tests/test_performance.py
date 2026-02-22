"""Performance benchmarks for critical code paths."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import numpy as np
import pytest

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import FillEvent, MarketEvent, OrderEvent, SignalEvent
from jamlechtrader.core.models import Bar, PortfolioSnapshot
from jamlechtrader.portfolio.portfolio import Portfolio
from jamlechtrader.portfolio.risk import RiskLimits, RiskManager
from jamlechtrader.portfolio.var import VaRCalculator


class TestEventBusThroughput:
    def test_sync_event_bus_throughput(self):
        from jamlechtrader.core.events import EventBus

        bus = EventBus()
        count = [0]

        def handler(event):
            count[0] += 1

        bus.subscribe(MarketEvent, handler)

        n = 10_000
        start = time.perf_counter()
        for i in range(n):
            event = MarketEvent(
                symbol="EURUSD",
                timestamp=datetime.now(tz=UTC),
                data=None,
            )
            bus.publish(event)
        elapsed = time.perf_counter() - start

        assert count[0] == n
        throughput = n / elapsed
        assert throughput > 1000, f"Event bus throughput too low: {throughput:.0f} events/s"


class TestRiskCheckLatency:
    def test_risk_check_under_1ms(self):
        rm = RiskManager(limits=RiskLimits())
        snapshot = PortfolioSnapshot(cash=10000, equity=10000)
        order = OrderEvent(symbol="EURUSD", side=OrderSide.BUY, quantity=0.01)

        n = 1000
        start = time.perf_counter()
        for _ in range(n):
            rm.check_order(order, snapshot)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / n) * 1000
        assert avg_ms < 1.0, f"Risk check too slow: {avg_ms:.3f}ms avg"


class TestPortfolioOnFillLatency:
    def test_on_fill_under_1ms(self):
        portfolio = Portfolio(initial_cash=100_000)

        n = 1000
        start = time.perf_counter()
        for i in range(n):
            symbol = f"SYM{i % 10}"
            fill = FillEvent(
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=0.01,
                price=1.0 + (i % 100) * 0.001,
            )
            portfolio.on_fill(fill)

            # Close half the positions
            if i % 2 == 1 and symbol in portfolio.positions:
                close_fill = FillEvent(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    quantity=portfolio.positions[symbol].quantity,
                    price=1.0 + (i % 100) * 0.001 + 0.005,
                )
                portfolio.on_fill(close_fill)

        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / n) * 1000
        assert avg_ms < 1.0, f"on_fill too slow: {avg_ms:.3f}ms avg"


class TestVaRCalculationSpeed:
    def test_var_calculation_speed(self):
        returns = np.random.normal(0, 0.02, 1000)
        calc = VaRCalculator(returns=returns)

        # Warmup — first call incurs scipy import overhead
        calc.parametric_var(0.95)

        n = 100
        start = time.perf_counter()
        for _ in range(n):
            calc.historical_var(0.95)
            calc.parametric_var(0.95)
            calc.cvar(0.95)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / n) * 1000
        assert avg_ms < 50.0, f"VaR calc too slow: {avg_ms:.3f}ms avg"


class TestBacktestPerformance:
    def test_backtest_1000_bars(self, sample_bars):
        """Benchmark: process 1000 bars through a minimal strategy + portfolio."""
        from jamlechtrader.portfolio.sizing import PositionSizer

        portfolio = Portfolio(initial_cash=10_000)
        rm = RiskManager()
        sizer = PositionSizer(method="fixed", fixed_lot=0.01)

        # Extend sample bars to 1000
        bars = sample_bars * 20  # 50 * 20 = 1000

        start = time.perf_counter()
        for i, bar in enumerate(bars):
            portfolio.update_market_price(bar.symbol, bar.close)

            # Simulate alternating signals
            if i % 20 == 0:
                fill = FillEvent(
                    symbol=bar.symbol,
                    side=OrderSide.BUY,
                    quantity=0.01,
                    price=bar.close,
                )
                portfolio.on_fill(fill)
            elif i % 20 == 10 and bar.symbol in portfolio.positions:
                fill = FillEvent(
                    symbol=bar.symbol,
                    side=OrderSide.SELL,
                    quantity=portfolio.positions[bar.symbol].quantity,
                    price=bar.close,
                )
                portfolio.on_fill(fill)

            snapshot = portfolio.take_snapshot(bar.timestamp)
            if snapshot:
                rm.check_order(
                    OrderEvent(symbol=bar.symbol, side=OrderSide.BUY, quantity=0.01),
                    snapshot,
                )

        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"1000-bar backtest too slow: {elapsed:.2f}s"
