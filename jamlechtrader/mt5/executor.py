"""MT5 order execution: send, modify, close orders via mt5.order_send()."""

from __future__ import annotations

import MetaTrader5 as mt5
from loguru import logger

from jamlechtrader.core.enums import OrderSide, OrderType
from jamlechtrader.core.models import Fill, Order, Position
from jamlechtrader.mt5.utils import mt5_error_message, mt5_position_to_model, to_mt5_order_type


class MT5Executor:
    """Wraps MT5 order operations with error handling."""

    def send_order(self, order: Order) -> Fill | None:
        """Send an order to MT5 and return a Fill on success."""
        symbol_info = mt5.symbol_info(order.symbol)
        if symbol_info is None:
            logger.error(f"Symbol not found: {order.symbol}")
            return None

        if not symbol_info.visible:
            if not mt5.symbol_select(order.symbol, True):
                logger.error(f"Failed to select symbol: {order.symbol}")
                return None

        mt5_type = to_mt5_order_type(order.order_type, order.side)

        # Use current price for market orders
        if order.order_type == OrderType.MARKET:
            tick = mt5.symbol_info_tick(order.symbol)
            if tick is None:
                logger.error(f"No tick available for {order.symbol}")
                return None
            price = tick.ask if order.side == OrderSide.BUY else tick.bid
        else:
            price = order.price

        request = {
            "action": mt5.TRADE_ACTION_DEAL if order.order_type == OrderType.MARKET else mt5.TRADE_ACTION_PENDING,
            "symbol": order.symbol,
            "volume": order.quantity,
            "type": mt5_type,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": order.comment or "jamlechtrader",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if order.stop_loss is not None:
            request["sl"] = order.stop_loss
        if order.take_profit is not None:
            request["tp"] = order.take_profit

        result = mt5.order_send(request)
        if result is None:
            logger.error(f"order_send returned None: {mt5.last_error()}")
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            msg = mt5_error_message(result.retcode)
            logger.error(f"Order rejected [{result.retcode}]: {msg}")
            return None

        logger.info(
            f"Order filled: {order.symbol} {order.side.value} {order.quantity} @ {result.price}"
        )
        return Fill(
            id=str(result.deal),
            order_id=str(result.order),
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=result.price,
        )

    def close_position(self, position: Position) -> Fill | None:
        """Close an open position by ticket."""
        close_side = OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY
        mt5_type = mt5.ORDER_TYPE_SELL if position.side == OrderSide.BUY else mt5.ORDER_TYPE_BUY

        tick = mt5.symbol_info_tick(position.symbol)
        if tick is None:
            logger.error(f"No tick for {position.symbol}")
            return None

        price = tick.bid if position.side == OrderSide.BUY else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.quantity,
            "type": mt5_type,
            "position": position.ticket,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "jamlechtrader close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
            logger.error(f"Close order_send returned None: {mt5.last_error()}")
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            msg = mt5_error_message(result.retcode)
            logger.error(f"Close rejected [{result.retcode}]: {msg}")
            return None

        logger.info(f"Position closed: {position.symbol} ticket={position.ticket}")
        return Fill(
            id=str(result.deal),
            order_id=str(result.order),
            symbol=position.symbol,
            side=close_side,
            quantity=position.quantity,
            price=result.price,
        )

    def modify_position(
        self,
        ticket: int,
        symbol: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> bool:
        """Modify SL/TP of an open position."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
        }
        if stop_loss is not None:
            request["sl"] = stop_loss
        if take_profit is not None:
            request["tp"] = take_profit

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Modify failed: {mt5.last_error()}")
            return False
        return True

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        """Get all open positions, optionally filtered by symbol."""
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()
        if positions is None:
            return []
        return [mt5_position_to_model(p) for p in positions]

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        """Get pending orders."""
        if symbol:
            orders = mt5.orders_get(symbol=symbol)
        else:
            orders = mt5.orders_get()
        if orders is None:
            return []
        return [
            {
                "ticket": o.ticket,
                "symbol": o.symbol,
                "type": o.type,
                "volume": o.volume_current,
                "price": o.price_open,
                "sl": o.sl,
                "tp": o.tp,
                "comment": o.comment,
            }
            for o in orders
        ]
