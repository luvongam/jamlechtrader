"""Integration tests for the Order Management System."""

from __future__ import annotations

import pytest

from jamlechtrader.core.enums import OrderSide, OrderStatus, OrderType
from jamlechtrader.core.exceptions import AmendmentError, InvalidTransitionError, OrderNotFoundError
from jamlechtrader.oms.amendment import OrderAmendment, OrderAmendmentHandler
from jamlechtrader.oms.bracket_order import BracketOrder, BracketOrderManager, BracketState
from jamlechtrader.oms.managed_order import ManagedOrder
from jamlechtrader.oms.order_manager import OrderManager
from jamlechtrader.oms.state_machine import OrderStateMachine, VALID_TRANSITIONS


class TestOrderStateMachine:
    def test_valid_transitions(self):
        sm = OrderStateMachine()
        assert sm.status == OrderStatus.PENDING

        sm.transition(OrderStatus.SUBMITTED)
        assert sm.status == OrderStatus.SUBMITTED

        sm.transition(OrderStatus.PARTIALLY_FILLED)
        assert sm.status == OrderStatus.PARTIALLY_FILLED

        sm.transition(OrderStatus.FILLED)
        assert sm.status == OrderStatus.FILLED
        assert sm.is_terminal

    def test_invalid_transition_raises(self):
        sm = OrderStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(OrderStatus.FILLED)

    def test_terminal_state_no_transitions(self):
        sm = OrderStateMachine()
        sm.transition(OrderStatus.SUBMITTED)
        sm.transition(OrderStatus.CANCELLED)
        assert sm.is_terminal

        with pytest.raises(InvalidTransitionError):
            sm.transition(OrderStatus.FILLED)

    def test_partial_fill_self_transition(self):
        sm = OrderStateMachine()
        sm.transition(OrderStatus.SUBMITTED)
        sm.transition(OrderStatus.PARTIALLY_FILLED)
        sm.transition(OrderStatus.PARTIALLY_FILLED)
        assert sm.status == OrderStatus.PARTIALLY_FILLED

    def test_history_tracking(self):
        sm = OrderStateMachine()
        sm.transition(OrderStatus.SUBMITTED)
        sm.transition(OrderStatus.FILLED)
        assert len(sm.history) == 2
        assert sm.history[0][0] == OrderStatus.PENDING
        assert sm.history[0][1] == OrderStatus.SUBMITTED

    def test_transition_callbacks(self):
        sm = OrderStateMachine()
        transitions = []
        sm.on_transition(lambda old, new: transitions.append((old, new)))

        sm.transition(OrderStatus.SUBMITTED)
        assert len(transitions) == 1
        assert transitions[0] == (OrderStatus.PENDING, OrderStatus.SUBMITTED)

    def test_can_transition(self):
        sm = OrderStateMachine()
        assert sm.can_transition(OrderStatus.SUBMITTED)
        assert not sm.can_transition(OrderStatus.FILLED)


class TestManagedOrder:
    def test_create_and_submit(self):
        order = ManagedOrder(symbol="EURUSD", side=OrderSide.BUY, quantity=0.1)
        assert order.client_order_id.startswith("JT-")
        assert order.status == OrderStatus.PENDING

        order.submit(broker_order_id="12345")
        assert order.status == OrderStatus.SUBMITTED
        assert order.broker_order_id == "12345"

    def test_full_fill(self):
        order = ManagedOrder(symbol="EURUSD", side=OrderSide.BUY, quantity=0.1)
        order.submit()
        order.on_fill(0.1, 1.0850, fill_id="f1")

        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 0.1
        assert order.remaining_quantity == 0.0
        assert order.average_fill_price == 1.0850

    def test_partial_fills(self):
        order = ManagedOrder(symbol="EURUSD", side=OrderSide.BUY, quantity=1.0)
        order.submit()

        order.on_fill(0.3, 1.0850)
        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert order.remaining_quantity == pytest.approx(0.7)

        order.on_fill(0.5, 1.0860)
        assert order.status == OrderStatus.PARTIALLY_FILLED

        order.on_fill(0.2, 1.0870)
        assert order.status == OrderStatus.FILLED
        assert order.remaining_quantity == 0.0
        assert order.average_fill_price > 0

    def test_cancel(self):
        order = ManagedOrder(symbol="EURUSD", side=OrderSide.BUY, quantity=0.1)
        order.submit()
        order.cancel()
        assert order.status == OrderStatus.CANCELLED
        assert order.is_terminal

    def test_reject(self):
        order = ManagedOrder(symbol="EURUSD", side=OrderSide.BUY, quantity=0.1)
        order.reject(reason="Risk limit exceeded")
        assert order.status == OrderStatus.REJECTED
        assert order.tags["reject_reason"] == "Risk limit exceeded"

    def test_to_dict(self):
        order = ManagedOrder(symbol="EURUSD", side=OrderSide.BUY, quantity=0.1, strategy_name="test")
        d = order.to_dict()
        assert d["symbol"] == "EURUSD"
        assert d["side"] == "BUY"
        assert d["strategy_name"] == "test"


class TestBracketOrder:
    def test_bracket_lifecycle_tp_fill(self):
        bracket = BracketOrder(
            symbol="EURUSD",
            side=OrderSide.BUY,
            quantity=0.1,
            stop_loss_price=1.0800,
            take_profit_price=1.0900,
        )
        assert bracket.state == BracketState.PENDING

        bracket.on_entry_fill(0.1, 1.0850)
        assert bracket.state == BracketState.ACTIVE

        bracket.on_take_profit_fill(0.1, 1.0900)
        assert bracket.state == BracketState.CLOSED
        assert bracket.stop_loss.status == OrderStatus.CANCELLED

    def test_bracket_lifecycle_sl_fill(self):
        bracket = BracketOrder(
            symbol="EURUSD",
            side=OrderSide.BUY,
            quantity=0.1,
            stop_loss_price=1.0800,
            take_profit_price=1.0900,
        )
        bracket.on_entry_fill(0.1, 1.0850)
        bracket.on_stop_loss_fill(0.1, 1.0800)
        assert bracket.state == BracketState.CLOSED
        assert bracket.take_profit.status == OrderStatus.CANCELLED

    def test_bracket_manager(self):
        mgr = BracketOrderManager()
        bracket = BracketOrder(
            symbol="EURUSD", side=OrderSide.BUY, quantity=0.1,
            stop_loss_price=1.08, take_profit_price=1.09,
        )
        key = mgr.create(bracket)
        assert mgr.get(key) is bracket
        assert len(mgr.get_all()) == 1

        bracket.on_entry_fill(0.1, 1.085)
        assert len(mgr.get_active()) == 1

        bracket.on_take_profit_fill(0.1, 1.09)
        removed = mgr.remove_closed()
        assert removed == 1
        assert len(mgr.get_all()) == 0


class TestOrderAmendment:
    def test_successful_amendment(self):
        handler = OrderAmendmentHandler()
        order = ManagedOrder(symbol="EURUSD", side=OrderSide.BUY, quantity=0.1, price=1.0850)
        order.submit()

        amendment = OrderAmendment(new_price=1.0860, new_quantity=0.2)
        replacement = handler.apply_amendment(order, amendment)

        assert replacement.price == 1.0860
        assert replacement.original_quantity == 0.2
        assert replacement.tags["amended_from"] == order.client_order_id

    def test_amendment_terminal_order_raises(self):
        handler = OrderAmendmentHandler()
        order = ManagedOrder(symbol="EURUSD", side=OrderSide.BUY, quantity=0.1)
        order.submit()
        order.on_fill(0.1, 1.0850)

        with pytest.raises(AmendmentError):
            handler.apply_amendment(order, OrderAmendment(new_price=1.09))

    def test_amendment_invalid_quantity_raises(self):
        handler = OrderAmendmentHandler()
        order = ManagedOrder(symbol="EURUSD", side=OrderSide.BUY, quantity=0.1)
        order.submit()

        with pytest.raises(AmendmentError):
            handler.apply_amendment(order, OrderAmendment(new_quantity=-0.1))


class TestOrderManager:
    def test_submit_and_get(self):
        mgr = OrderManager()
        managed = mgr.submit_order(symbol="EURUSD", side=OrderSide.BUY, quantity=0.1)
        assert managed.client_order_id.startswith("JT-")
        assert mgr.get_order(managed.client_order_id) is managed

    def test_cancel_order(self):
        mgr = OrderManager()
        managed = mgr.submit_order(symbol="EURUSD", side=OrderSide.BUY, quantity=0.1)
        result = mgr.cancel_order(managed.client_order_id)
        assert result is True
        assert managed.status == OrderStatus.CANCELLED

    def test_cancel_nonexistent_raises(self):
        mgr = OrderManager()
        with pytest.raises(OrderNotFoundError):
            mgr.cancel_order("nonexistent-id")

    def test_get_open_orders(self):
        mgr = OrderManager()
        mgr.submit_order(symbol="EURUSD", side=OrderSide.BUY, quantity=0.1)
        mgr.submit_order(symbol="GBPUSD", side=OrderSide.SELL, quantity=0.2)

        open_orders = mgr.get_open_orders()
        assert len(open_orders) == 2

    def test_order_history(self):
        mgr = OrderManager()
        for _ in range(5):
            mgr.submit_order(symbol="EURUSD", side=OrderSide.BUY, quantity=0.01)

        history = mgr.get_order_history(limit=3)
        assert len(history) == 3
