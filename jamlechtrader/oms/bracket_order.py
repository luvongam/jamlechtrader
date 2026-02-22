"""Bracket orders — atomic entry + stop loss + take profit groups."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from loguru import logger

from jamlechtrader.core.enums import OrderSide, OrderStatus, OrderType
from jamlechtrader.oms.managed_order import ManagedOrder

if TYPE_CHECKING:
    pass


class BracketState(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"  # entry filled
    CLOSED = "CLOSED"  # SL or TP filled


class BracketOrder:
    """Atomic order group: entry + stop loss + take profit.

    When the entry fills → bracket becomes ACTIVE.
    When SL fills → cancel TP. When TP fills → cancel SL.
    """

    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        entry_price: float | None = None,
        stop_loss_price: float = 0.0,
        take_profit_price: float = 0.0,
        entry_type: OrderType = OrderType.MARKET,
        strategy_name: str | None = None,
    ) -> None:
        self.state = BracketState.PENDING

        self.entry = ManagedOrder(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=entry_type,
            price=entry_price,
            strategy_name=strategy_name,
            tags={"bracket_role": "entry"},
        )

        sl_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
        self.stop_loss = ManagedOrder(
            symbol=symbol,
            side=sl_side,
            quantity=quantity,
            order_type=OrderType.STOP,
            price=stop_loss_price,
            strategy_name=strategy_name,
            tags={"bracket_role": "stop_loss"},
        )

        tp_side = sl_side
        self.take_profit = ManagedOrder(
            symbol=symbol,
            side=tp_side,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            price=take_profit_price,
            strategy_name=strategy_name,
            tags={"bracket_role": "take_profit"},
        )

    @property
    def is_closed(self) -> bool:
        return self.state == BracketState.CLOSED

    def on_entry_fill(self, quantity: float, price: float, fill_id: str = "") -> None:
        """Called when the entry order fills."""
        if self.entry.status == OrderStatus.PENDING:
            self.entry.submit()
        self.entry.on_fill(quantity, price, fill_id)
        if self.entry.status == OrderStatus.FILLED:
            self.state = BracketState.ACTIVE
            logger.info(
                f"Bracket {self.entry.client_order_id} ACTIVE: "
                f"SL={self.stop_loss.price} TP={self.take_profit.price}"
            )

    def on_stop_loss_fill(self, quantity: float, price: float, fill_id: str = "") -> None:
        """Called when the stop loss fills — cancel take profit."""
        if self.stop_loss.status == OrderStatus.PENDING:
            self.stop_loss.submit()
        self.stop_loss.on_fill(quantity, price, fill_id)
        if self.stop_loss.status == OrderStatus.FILLED:
            self.take_profit.cancel()
            self.state = BracketState.CLOSED
            logger.info(f"Bracket {self.entry.client_order_id} CLOSED via SL @ {price}")

    def on_take_profit_fill(self, quantity: float, price: float, fill_id: str = "") -> None:
        """Called when the take profit fills — cancel stop loss."""
        if self.take_profit.status == OrderStatus.PENDING:
            self.take_profit.submit()
        self.take_profit.on_fill(quantity, price, fill_id)
        if self.take_profit.status == OrderStatus.FILLED:
            self.stop_loss.cancel()
            self.state = BracketState.CLOSED
            logger.info(f"Bracket {self.entry.client_order_id} CLOSED via TP @ {price}")


class BracketOrderManager:
    """Manages lifecycle of bracket orders."""

    def __init__(self) -> None:
        self._brackets: dict[str, BracketOrder] = {}

    def create(self, bracket: BracketOrder) -> str:
        """Register a bracket order. Returns the entry client_order_id."""
        key = bracket.entry.client_order_id
        self._brackets[key] = bracket
        return key

    def get(self, entry_order_id: str) -> BracketOrder | None:
        return self._brackets.get(entry_order_id)

    def get_active(self) -> list[BracketOrder]:
        return [b for b in self._brackets.values() if b.state == BracketState.ACTIVE]

    def get_all(self) -> list[BracketOrder]:
        return list(self._brackets.values())

    def remove_closed(self) -> int:
        """Remove closed brackets. Returns number removed."""
        closed_keys = [k for k, b in self._brackets.items() if b.is_closed]
        for k in closed_keys:
            del self._brackets[k]
        return len(closed_keys)
