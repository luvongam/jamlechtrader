"""Order state machine — enforces valid transitions and fires callbacks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable

from loguru import logger

from jamlechtrader.core.enums import OrderStatus
from jamlechtrader.core.exceptions import InvalidTransitionError

VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.CANCELLED},
    OrderStatus.SUBMITTED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
    },
    # Terminal states — no outgoing transitions
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.EXPIRED: set(),
}


class OrderStateMachine:
    """Enforces order state transitions, logs history, fires callbacks."""

    def __init__(self, initial_status: OrderStatus = OrderStatus.PENDING) -> None:
        self._status = initial_status
        self._history: list[tuple[OrderStatus, OrderStatus, datetime]] = []
        self._callbacks: list[Callable[[OrderStatus, OrderStatus], None]] = []

    @property
    def status(self) -> OrderStatus:
        return self._status

    @property
    def history(self) -> list[tuple[OrderStatus, OrderStatus, datetime]]:
        return list(self._history)

    @property
    def is_terminal(self) -> bool:
        return self._status in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }

    def on_transition(self, callback: Callable[[OrderStatus, OrderStatus], None]) -> None:
        self._callbacks.append(callback)

    def transition(self, new_status: OrderStatus) -> None:
        """Transition to a new status. Raises InvalidTransitionError if illegal."""
        if new_status == self._status and new_status == OrderStatus.PARTIALLY_FILLED:
            # Allow self-transition for additional partial fills
            pass
        elif new_status not in VALID_TRANSITIONS.get(self._status, set()):
            raise InvalidTransitionError(
                f"Invalid transition: {self._status.value} → {new_status.value}"
            )

        old = self._status
        self._status = new_status
        ts = datetime.now(tz=UTC)
        self._history.append((old, new_status, ts))

        logger.debug(f"Order state: {old.value} → {new_status.value}")

        for cb in self._callbacks:
            try:
                cb(old, new_status)
            except Exception as e:
                logger.error(f"State transition callback error: {e}")

    def can_transition(self, new_status: OrderStatus) -> bool:
        if new_status == self._status and new_status == OrderStatus.PARTIALLY_FILLED:
            return True
        return new_status in VALID_TRANSITIONS.get(self._status, set())
