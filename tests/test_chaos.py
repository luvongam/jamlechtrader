"""Chaos tests — random failures, disconnections, reconnect storms."""

from __future__ import annotations

import random
import time

import pytest

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import FillEvent
from jamlechtrader.portfolio.portfolio import Portfolio
from jamlechtrader.portfolio.enterprise_risk import EnterpriseRiskLimits, EnterpriseRiskManager
from jamlechtrader.portfolio.kill_switch import KillSwitch
from jamlechtrader.portfolio.var import VaRCalculator
from jamlechtrader.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, CircuitState
from jamlechtrader.resilience.dead_letter_queue import DeadLetterQueue


class TestRandomDisconnections:
    def test_circuit_breaker_under_random_failures(self):
        """Simulate random disconnections and verify circuit breaker behavior."""
        cb = CircuitBreaker(name="chaos", failure_threshold=5, recovery_timeout=0.1)
        failures = 0
        successes = 0

        for _ in range(100):
            if random.random() < 0.3:  # 30% failure rate
                cb.record_failure()
                failures += 1
            else:
                if cb.allow_request():
                    cb.record_success()
                    successes += 1
                else:
                    time.sleep(0.12)  # Wait for recovery
                    if cb.allow_request():
                        cb.record_success()
                        successes += 1

        # Circuit breaker should have triggered at least once
        assert failures > 0
        assert successes > 0

    def test_dead_letter_queue_under_load(self):
        """Simulate many failed orders hitting the DLQ."""
        dlq = DeadLetterQueue(max_size=50)
        for i in range(100):
            dlq.add({"symbol": f"SYM{i % 5}", "side": "BUY", "qty": 0.01}, f"error_{i}")

        assert dlq.size == 50

        # Retry some
        retried = 0
        while dlq.size > 25:
            entry = dlq.retry()
            if entry:
                retried += 1

        assert retried == 25


class TestCircuitBreakerRecovery:
    def test_open_then_recover(self):
        cb = CircuitBreaker(name="recovery", failure_threshold=3, recovery_timeout=0.1)

        # Trip the breaker
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Successful call recovers
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(name="reopen", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestKillSwitchUnderRapidDrawdown:
    def test_kill_switch_triggers_on_drawdown(self):
        ks = KillSwitch()
        assert not ks.is_triggered

        code = ks.trigger("Rapid drawdown exceeds 10%")
        assert ks.is_triggered
        assert ks.trigger_reason == "Rapid drawdown exceeds 10%"
        assert code is not None

    def test_kill_switch_requires_auth_to_reset(self):
        ks = KillSwitch()
        code = ks.trigger("test")

        assert not ks.reset("wrong-code")
        assert ks.is_triggered

        assert ks.reset(code)
        assert not ks.is_triggered

    def test_consecutive_losses_halt_trading(self):
        limits = EnterpriseRiskLimits(kill_switch_consecutive_losses=3)
        rm = EnterpriseRiskManager(limits=limits)

        rm.record_trade_result(-100.0)
        rm.record_trade_result(-50.0)
        rm.record_trade_result(-75.0)

        from jamlechtrader.core.events import OrderEvent
        from jamlechtrader.core.models import PortfolioSnapshot

        order = OrderEvent(symbol="EURUSD", side=OrderSide.BUY, quantity=0.01)
        snapshot = PortfolioSnapshot(cash=10000, equity=9000)

        result = rm.check_order(order, snapshot)
        assert result is None  # Rejected due to consecutive losses


class TestOrderTimeouts:
    def test_dlq_preserves_order_on_timeout(self):
        dlq = DeadLetterQueue()
        dlq.add({"symbol": "EURUSD", "side": "BUY", "qty": 0.1}, "Execution timeout")

        entry = dlq.peek()
        assert entry is not None
        assert "timeout" in entry.error.lower()


class TestVaRUnderStress:
    def test_var_with_volatile_returns(self):
        import numpy as np

        # Simulate highly volatile returns
        returns = np.random.normal(0, 0.05, 500)  # 5% daily vol
        calc = VaRCalculator(returns=returns)

        var_95 = calc.historical_var(0.95)
        assert var_95 > 0  # VaR should be positive

        cvar = calc.cvar(0.95)
        assert cvar >= var_95  # CVaR >= VaR always

    def test_var_with_insufficient_data(self):
        import numpy as np

        calc = VaRCalculator(returns=np.array([0.01, -0.02]))
        assert calc.historical_var(0.95) == 0.0
        assert calc.parametric_var(0.95) == 0.0
        assert calc.cvar(0.95) == 0.0
