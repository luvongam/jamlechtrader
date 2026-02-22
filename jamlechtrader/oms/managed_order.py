"""ManagedOrder — wraps Order with state machine, partial fill tracking, and metadata."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from jamlechtrader.core.enums import OrderSide, OrderStatus, OrderType, TimeInForce
from jamlechtrader.core.models import Order
from jamlechtrader.oms.state_machine import OrderStateMachine


def _generate_client_order_id() -> str:
    return f"JT-{uuid.uuid4().hex[:12]}"


class ManagedOrder:
    """Enhanced order wrapper with lifecycle management.

    Auto-generates a client_order_id, integrates the state machine,
    and tracks partial fills.
    """

    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        strategy_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        self.client_order_id = _generate_client_order_id()
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.original_quantity = quantity
        self.price = price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.time_in_force = time_in_force
        self.strategy_name = strategy_name
        self.tags = tags or {}

        self._state_machine = OrderStateMachine()
        self.broker_order_id: str | None = None
        self.filled_quantity: float = 0.0
        self.total_fill_cost: float = 0.0
        self.created_at = datetime.now(tz=UTC)
        self.updated_at = self.created_at

        self._fills: list[dict[str, Any]] = []

    @property
    def status(self) -> OrderStatus:
        return self._state_machine.status

    @property
    def remaining_quantity(self) -> float:
        return max(self.original_quantity - self.filled_quantity, 0.0)

    @property
    def average_fill_price(self) -> float:
        if self.filled_quantity <= 0:
            return 0.0
        return self.total_fill_cost / self.filled_quantity

    @property
    def is_terminal(self) -> bool:
        return self._state_machine.is_terminal

    @property
    def state_history(self):
        return self._state_machine.history

    @property
    def fills(self) -> list[dict[str, Any]]:
        return list(self._fills)

    def submit(self, broker_order_id: str | None = None) -> None:
        """Mark order as submitted to the broker."""
        self._state_machine.transition(OrderStatus.SUBMITTED)
        self.broker_order_id = broker_order_id
        self.updated_at = datetime.now(tz=UTC)
        logger.debug(f"Order {self.client_order_id} submitted")

    def on_fill(self, quantity: float, price: float, fill_id: str = "") -> None:
        """Record a (partial) fill."""
        self.filled_quantity += quantity
        self.total_fill_cost += quantity * price
        self._fills.append({
            "fill_id": fill_id,
            "quantity": quantity,
            "price": price,
            "timestamp": datetime.now(tz=UTC),
        })

        if self.remaining_quantity <= 0:
            self._state_machine.transition(OrderStatus.FILLED)
        else:
            self._state_machine.transition(OrderStatus.PARTIALLY_FILLED)

        self.updated_at = datetime.now(tz=UTC)
        logger.debug(
            f"Order {self.client_order_id} fill: {quantity}@{price} "
            f"({self.filled_quantity}/{self.original_quantity})"
        )

    def cancel(self) -> None:
        """Cancel the order."""
        self._state_machine.transition(OrderStatus.CANCELLED)
        self.updated_at = datetime.now(tz=UTC)
        logger.debug(f"Order {self.client_order_id} cancelled")

    def reject(self, reason: str = "") -> None:
        """Reject the order."""
        self._state_machine.transition(OrderStatus.REJECTED)
        self.tags["reject_reason"] = reason
        self.updated_at = datetime.now(tz=UTC)
        logger.debug(f"Order {self.client_order_id} rejected: {reason}")

    def to_order_model(self) -> Order:
        """Convert to the core Order model for execution."""
        return Order(
            id=self.client_order_id,
            symbol=self.symbol,
            side=self.side,
            order_type=self.order_type,
            quantity=self.remaining_quantity,
            price=self.price,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            time_in_force=self.time_in_force,
            status=self.status,
            client_order_id=self.client_order_id,
            tags=self.tags,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.original_quantity,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "price": self.price,
            "average_fill_price": self.average_fill_price,
            "status": self.status.value,
            "strategy_name": self.strategy_name,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
        }
