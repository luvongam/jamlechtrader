"""Central Order Management System facade."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from jamlechtrader.core.enums import OrderSide, OrderStatus, OrderType, TimeInForce
from jamlechtrader.core.exceptions import OrderNotFoundError
from jamlechtrader.oms.amendment import OrderAmendment, OrderAmendmentHandler
from jamlechtrader.oms.bracket_order import BracketOrder, BracketOrderManager
from jamlechtrader.oms.managed_order import ManagedOrder

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from jamlechtrader.audit.logger import AuditLogger
    from jamlechtrader.core.events import FillEvent
    from jamlechtrader.core.models import PortfolioSnapshot
    from jamlechtrader.execution.base import AbstractExecutionHandler
    from jamlechtrader.portfolio.portfolio import Portfolio
    from jamlechtrader.portfolio.risk import RiskManager


class OrderManager:
    """Central OMS facade integrating executor, portfolio, risk, audit, and DB.

    Provides a single entry point for submitting, cancelling, and amending
    orders with full lifecycle management.
    """

    def __init__(
        self,
        executor: AbstractExecutionHandler | None = None,
        portfolio: Portfolio | None = None,
        risk_manager: RiskManager | None = None,
        audit_logger: AuditLogger | None = None,
        db_session: AsyncSession | None = None,
    ) -> None:
        self._executor = executor
        self._portfolio = portfolio
        self._risk_manager = risk_manager
        self._audit_logger = audit_logger
        self._db_session = db_session

        self._orders: dict[str, ManagedOrder] = {}
        self._bracket_manager = BracketOrderManager()
        self._amendment_handler = OrderAmendmentHandler()

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        strategy_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> ManagedOrder:
        """Create, risk-check, and submit an order."""
        managed = ManagedOrder(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_name=strategy_name,
            tags=tags,
        )

        self._orders[managed.client_order_id] = managed
        logger.info(f"OMS: created order {managed.client_order_id}")

        # Risk check
        if self._risk_manager and self._portfolio:
            from jamlechtrader.core.events import OrderEvent

            order_event = OrderEvent(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            snapshot = self._portfolio.take_snapshot()
            checked = self._risk_manager.check_order(order_event, snapshot)
            if checked is None:
                managed.reject("Risk check failed")
                return managed

        # Execute
        if self._executor:
            order_model = managed.to_order_model()
            fill = self._executor.send_order(order_model)
            if fill is not None:
                managed.submit(broker_order_id=fill.order_id)
                managed.on_fill(fill.quantity, fill.price, fill.id)
                logger.info(
                    f"OMS: order {managed.client_order_id} filled "
                    f"{fill.quantity}@{fill.price}"
                )

                # Update portfolio
                if self._portfolio:
                    from jamlechtrader.core.events import FillEvent

                    fill_event = FillEvent(
                        symbol=fill.symbol,
                        side=fill.side,
                        quantity=fill.quantity,
                        price=fill.price,
                        commission=fill.commission,
                        order_id=fill.order_id,
                    )
                    self._portfolio.on_fill(fill_event)
            else:
                managed.reject("Execution failed — no fill returned")
        else:
            managed.submit()

        return managed

    def submit_bracket(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        stop_loss_price: float,
        take_profit_price: float,
        entry_price: float | None = None,
        entry_type: OrderType = OrderType.MARKET,
        strategy_name: str | None = None,
    ) -> BracketOrder:
        """Submit a bracket order (entry + SL + TP)."""
        bracket = BracketOrder(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            entry_type=entry_type,
            strategy_name=strategy_name,
        )

        self._bracket_manager.create(bracket)
        self._orders[bracket.entry.client_order_id] = bracket.entry
        self._orders[bracket.stop_loss.client_order_id] = bracket.stop_loss
        self._orders[bracket.take_profit.client_order_id] = bracket.take_profit

        # Execute entry
        if self._executor:
            entry_model = bracket.entry.to_order_model()
            fill = self._executor.send_order(entry_model)
            if fill is not None:
                bracket.entry.submit(broker_order_id=fill.order_id)
                bracket.on_entry_fill(fill.quantity, fill.price, fill.id)
            else:
                bracket.entry.reject("Entry execution failed")

        logger.info(f"OMS: bracket submitted {bracket.entry.client_order_id}")
        return bracket

    def cancel_order(self, client_order_id: str) -> bool:
        """Cancel an order by client_order_id."""
        managed = self._orders.get(client_order_id)
        if managed is None:
            raise OrderNotFoundError(f"Order {client_order_id} not found")

        if managed.is_terminal:
            logger.warning(f"Cannot cancel terminal order {client_order_id}")
            return False

        managed.cancel()
        logger.info(f"OMS: order {client_order_id} cancelled")
        return True

    def amend_order(self, client_order_id: str, amendment: OrderAmendment) -> ManagedOrder:
        """Amend an order via cancel-replace."""
        managed = self._orders.get(client_order_id)
        if managed is None:
            raise OrderNotFoundError(f"Order {client_order_id} not found")

        replacement = self._amendment_handler.apply_amendment(managed, amendment)
        managed.cancel()
        self._orders[replacement.client_order_id] = replacement

        # Execute replacement
        if self._executor:
            order_model = replacement.to_order_model()
            fill = self._executor.send_order(order_model)
            if fill is not None:
                replacement.submit(broker_order_id=fill.order_id)
                replacement.on_fill(fill.quantity, fill.price, fill.id)

        logger.info(f"OMS: amended {client_order_id} → {replacement.client_order_id}")
        return replacement

    def get_order(self, client_order_id: str) -> ManagedOrder | None:
        return self._orders.get(client_order_id)

    def get_open_orders(self) -> list[ManagedOrder]:
        return [o for o in self._orders.values() if not o.is_terminal]

    def get_order_history(self, limit: int = 100) -> list[ManagedOrder]:
        orders = sorted(self._orders.values(), key=lambda o: o.created_at, reverse=True)
        return orders[:limit]

    @property
    def bracket_manager(self) -> BracketOrderManager:
        return self._bracket_manager
