"""Integration tests for resilience features."""

from __future__ import annotations

import time

import pytest

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import FillEvent
from jamlechtrader.portfolio.portfolio import Portfolio
from jamlechtrader.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, CircuitState
from jamlechtrader.resilience.dead_letter_queue import DeadLetterQueue
from jamlechtrader.resilience.shutdown import GracefulShutdown


class TestCircuitBreakerIntegration:
    def test_circuit_opens_after_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=1.0)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.allow_request()

    def test_circuit_transitions_to_half_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request()

    def test_circuit_recovers_on_success(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)

        # Access state to trigger OPEN → HALF_OPEN transition
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_circuit_breaker_as_decorator(self):
        cb = CircuitBreaker(name="test_deco", failure_threshold=2, recovery_timeout=1.0)

        @cb
        def failing_fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            failing_fn()
        with pytest.raises(ValueError):
            failing_fn()
        with pytest.raises(CircuitBreakerOpen):
            failing_fn()

    def test_state_change_callback(self):
        cb = CircuitBreaker(name="test_cb", failure_threshold=2, recovery_timeout=0.1)
        transitions = []
        cb.on_state_change(lambda old, new: transitions.append((old, new)))

        cb.record_failure()
        cb.record_failure()
        assert len(transitions) == 1
        assert transitions[0] == (CircuitState.CLOSED, CircuitState.OPEN)


class TestDeadLetterQueue:
    def test_add_and_pop(self):
        dlq = DeadLetterQueue()
        dlq.add({"symbol": "EURUSD", "side": "BUY"}, "Test error")
        assert dlq.size == 1

        entry = dlq.pop()
        assert entry is not None
        assert entry.order_data["symbol"] == "EURUSD"
        assert entry.error == "Test error"
        assert dlq.size == 0

    def test_retry_increments_count(self):
        dlq = DeadLetterQueue()
        dlq.add({"symbol": "EURUSD"}, "error")
        entry = dlq.retry()
        assert entry is not None
        assert entry.retry_count == 1

    def test_max_size(self):
        dlq = DeadLetterQueue(max_size=3)
        for i in range(5):
            dlq.add({"i": i}, f"error {i}")
        assert dlq.size == 3


class TestGracefulShutdown:
    def test_callbacks_run_in_order(self):
        shutdown = GracefulShutdown()
        order = []
        shutdown.register("first", lambda: order.append(1))
        shutdown.register("second", lambda: order.append(2))
        shutdown.register("third", lambda: order.append(3))

        shutdown.execute()
        assert order == [1, 2, 3]
        assert shutdown.is_shutting_down

    def test_callback_error_doesnt_block(self):
        shutdown = GracefulShutdown()
        order = []
        shutdown.register("ok1", lambda: order.append(1))
        shutdown.register("fail", lambda: (_ for _ in ()).throw(ValueError("boom")))
        shutdown.register("ok2", lambda: order.append(3))

        shutdown.execute()
        assert 1 in order
        assert 3 in order


class TestPortfolioStatePersistence:
    def test_portfolio_fill_and_snapshot(self):
        portfolio = Portfolio(initial_cash=10000.0)
        fill = FillEvent(
            symbol="EURUSD", side=OrderSide.BUY, quantity=0.01, price=1.0850
        )
        portfolio.on_fill(fill)
        assert "EURUSD" in portfolio.positions

        snapshot = portfolio.take_snapshot()
        assert snapshot.equity > 0
        assert len(portfolio.equity_curve) == 1

    def test_portfolio_close_trade(self):
        portfolio = Portfolio(initial_cash=10000.0)
        open_fill = FillEvent(symbol="EURUSD", side=OrderSide.BUY, quantity=0.01, price=1.0800)
        portfolio.on_fill(open_fill)

        close_fill = FillEvent(symbol="EURUSD", side=OrderSide.SELL, quantity=0.01, price=1.0850)
        portfolio.on_fill(close_fill)

        assert "EURUSD" not in portfolio.positions
        assert len(portfolio.closed_trades) == 1
        assert portfolio.closed_trades[0]["pnl"] > 0


class TestRiskRejection:
    def test_risk_rejects_over_position_limit(self):
        from jamlechtrader.core.events import OrderEvent
        from jamlechtrader.core.models import PortfolioSnapshot, Position
        from jamlechtrader.portfolio.risk import RiskLimits, RiskManager

        rm = RiskManager(limits=RiskLimits(max_open_positions=1))
        snapshot = PortfolioSnapshot(
            cash=10000.0,
            equity=10000.0,
            positions=[Position(symbol="GBPUSD", side=OrderSide.BUY, quantity=0.01, entry_price=1.25)],
        )
        order = OrderEvent(symbol="EURUSD", side=OrderSide.BUY, quantity=0.01)
        result = rm.check_order(order, snapshot)
        assert result is None
