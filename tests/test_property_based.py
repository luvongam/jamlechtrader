"""Property-based tests using Hypothesis."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from jamlechtrader.core.enums import OrderSide, OrderStatus
from jamlechtrader.core.events import FillEvent, OrderEvent
from jamlechtrader.core.models import PortfolioSnapshot
from jamlechtrader.oms.state_machine import VALID_TRANSITIONS, OrderStateMachine
from jamlechtrader.portfolio.portfolio import Portfolio
from jamlechtrader.portfolio.sizing import PositionSizer
from jamlechtrader.portfolio.var import VaRCalculator


class TestEquityConservation:
    @given(
        initial_cash=st.floats(min_value=1000, max_value=1_000_000, allow_nan=False),
        buy_price=st.floats(min_value=0.5, max_value=2.0, allow_nan=False),
        sell_price=st.floats(min_value=0.5, max_value=2.0, allow_nan=False),
        quantity=st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_equity_conserved_on_round_trip(self, initial_cash, buy_price, sell_price, quantity):
        """After opening and closing a position, cash change equals PnL."""
        portfolio = Portfolio(initial_cash=initial_cash)

        # Open
        buy_fill = FillEvent(
            symbol="TEST", side=OrderSide.BUY, quantity=quantity, price=buy_price
        )
        portfolio.on_fill(buy_fill)

        # Close
        sell_fill = FillEvent(
            symbol="TEST", side=OrderSide.SELL, quantity=quantity, price=sell_price
        )
        portfolio.on_fill(sell_fill)

        expected_pnl = (sell_price - buy_price) * quantity
        assert portfolio.realized_pnl == pytest.approx(expected_pnl, abs=1e-6)
        assert portfolio.cash == pytest.approx(initial_cash + expected_pnl, abs=1e-6)
        assert len(portfolio.positions) == 0


class TestOrderStateMachineInvariants:
    @given(
        transitions=st.lists(
            st.sampled_from(list(OrderStatus)),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=200)
    def test_state_machine_never_allows_invalid_transitions(self, transitions):
        """The state machine should never enter an invalid state."""
        sm = OrderStateMachine()

        for target in transitions:
            if sm.is_terminal:
                # Terminal states should reject all transitions
                assert not sm.can_transition(target) or (
                    target == OrderStatus.PARTIALLY_FILLED
                    and sm.status == OrderStatus.PARTIALLY_FILLED
                )
                break

            if sm.can_transition(target):
                sm.transition(target)
                assert sm.status == target
            # If not valid, just skip — this tests that we don't crash


class TestPositionSizerBounds:
    @given(
        equity=st.floats(min_value=100, max_value=1_000_000, allow_nan=False),
        fixed_lot=st.floats(min_value=0.01, max_value=10.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_sizer_returns_positive_bounded_value(self, equity, fixed_lot):
        """Position sizer should always return a positive, bounded value."""
        sizer = PositionSizer(method="fixed", fixed_lot=fixed_lot)
        result = sizer.calculate(equity=equity)
        assert result >= 0.01
        assert result <= 100.0  # reasonable upper bound


class TestVaRPositivity:
    @given(
        returns=st.lists(
            st.floats(min_value=-0.1, max_value=0.1, allow_nan=False, allow_infinity=False),
            min_size=20,
            max_size=500,
        ),
        confidence=st.floats(min_value=0.9, max_value=0.99, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_var_is_non_negative(self, returns, confidence):
        """VaR should always be non-negative."""
        calc = VaRCalculator(returns=np.array(returns))
        var = calc.historical_var(confidence)
        assert var >= 0.0

    @given(
        returns=st.lists(
            st.floats(min_value=-0.1, max_value=0.1, allow_nan=False, allow_infinity=False),
            min_size=20,
            max_size=500,
        ),
        confidence=st.floats(min_value=0.9, max_value=0.99, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_cvar_gte_var(self, returns, confidence):
        """CVaR (Expected Shortfall) should always be >= VaR."""
        calc = VaRCalculator(returns=np.array(returns))
        var = calc.historical_var(confidence)
        cvar = calc.cvar(confidence)
        assert cvar >= var - 1e-6  # small tolerance for floating point
