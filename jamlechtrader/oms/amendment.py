"""Order amendment — cancel-replace pattern for modifying live orders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from jamlechtrader.core.enums import OrderStatus
from jamlechtrader.core.exceptions import AmendmentError

if TYPE_CHECKING:
    from jamlechtrader.oms.managed_order import ManagedOrder


@dataclass
class OrderAmendment:
    """Requested changes to an existing order."""

    new_price: float | None = None
    new_quantity: float | None = None
    new_stop_loss: float | None = None
    new_take_profit: float | None = None


class OrderAmendmentHandler:
    """Implements order amendments via cancel-replace pattern.

    Since most brokers don't support in-place modification, we cancel
    the original order and submit a replacement.
    """

    def validate_amendment(self, order: ManagedOrder, amendment: OrderAmendment) -> None:
        """Validate that the amendment is possible."""
        if order.is_terminal:
            raise AmendmentError(
                f"Cannot amend terminal order {order.client_order_id} "
                f"(status={order.status.value})"
            )

        if order.status not in {OrderStatus.PENDING, OrderStatus.SUBMITTED}:
            raise AmendmentError(
                f"Cannot amend order {order.client_order_id} "
                f"in status {order.status.value} — only PENDING/SUBMITTED allowed"
            )

        if amendment.new_quantity is not None and amendment.new_quantity <= 0:
            raise AmendmentError("Amendment quantity must be positive")

    def apply_amendment(self, order: ManagedOrder, amendment: OrderAmendment) -> ManagedOrder:
        """Create a replacement order with amended fields.

        The caller is responsible for cancelling the original order
        and submitting the replacement.
        """
        self.validate_amendment(order, amendment)

        from jamlechtrader.oms.managed_order import ManagedOrder as MO

        replacement = MO(
            symbol=order.symbol,
            side=order.side,
            quantity=amendment.new_quantity or order.original_quantity,
            order_type=order.order_type,
            price=amendment.new_price if amendment.new_price is not None else order.price,
            stop_loss=amendment.new_stop_loss if amendment.new_stop_loss is not None else order.stop_loss,
            take_profit=amendment.new_take_profit if amendment.new_take_profit is not None else order.take_profit,
            time_in_force=order.time_in_force,
            strategy_name=order.strategy_name,
            tags={**order.tags, "amended_from": order.client_order_id},
        )

        logger.info(
            f"Amendment: {order.client_order_id} → {replacement.client_order_id}"
        )
        return replacement
