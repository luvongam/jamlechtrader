"""MT5 utility functions: timeframe mapping, error handling, type converters."""

from __future__ import annotations

from datetime import UTC, datetime

import MetaTrader5 as mt5

from jamlechtrader.core.enums import OrderSide, OrderType, Timeframe
from jamlechtrader.core.models import Bar, Position, Tick

# Timeframe enum → MT5 constant mapping
TIMEFRAME_MAP: dict[Timeframe, int] = {
    Timeframe.M1: mt5.TIMEFRAME_M1,
    Timeframe.M2: mt5.TIMEFRAME_M2,
    Timeframe.M3: mt5.TIMEFRAME_M3,
    Timeframe.M4: mt5.TIMEFRAME_M4,
    Timeframe.M5: mt5.TIMEFRAME_M5,
    Timeframe.M6: mt5.TIMEFRAME_M6,
    Timeframe.M10: mt5.TIMEFRAME_M10,
    Timeframe.M12: mt5.TIMEFRAME_M12,
    Timeframe.M15: mt5.TIMEFRAME_M15,
    Timeframe.M20: mt5.TIMEFRAME_M20,
    Timeframe.M30: mt5.TIMEFRAME_M30,
    Timeframe.H1: mt5.TIMEFRAME_H1,
    Timeframe.H2: mt5.TIMEFRAME_H2,
    Timeframe.H3: mt5.TIMEFRAME_H3,
    Timeframe.H4: mt5.TIMEFRAME_H4,
    Timeframe.H6: mt5.TIMEFRAME_H6,
    Timeframe.H8: mt5.TIMEFRAME_H8,
    Timeframe.H12: mt5.TIMEFRAME_H12,
    Timeframe.D1: mt5.TIMEFRAME_D1,
    Timeframe.W1: mt5.TIMEFRAME_W1,
    Timeframe.MN1: mt5.TIMEFRAME_MN1,
}


def to_mt5_timeframe(tf: Timeframe) -> int:
    """Convert Timeframe enum to MT5 constant."""
    return TIMEFRAME_MAP[tf]


def to_mt5_order_type(order_type: OrderType, side: OrderSide) -> int:
    """Convert our OrderType + Side to MT5 order type constant."""
    if order_type == OrderType.MARKET:
        return mt5.ORDER_TYPE_BUY if side == OrderSide.BUY else mt5.ORDER_TYPE_SELL
    if order_type == OrderType.LIMIT:
        return mt5.ORDER_TYPE_BUY_LIMIT if side == OrderSide.BUY else mt5.ORDER_TYPE_SELL_LIMIT
    if order_type == OrderType.STOP:
        return mt5.ORDER_TYPE_BUY_STOP if side == OrderSide.BUY else mt5.ORDER_TYPE_SELL_STOP
    if order_type == OrderType.STOP_LIMIT:
        return mt5.ORDER_TYPE_BUY_STOP_LIMIT if side == OrderSide.BUY else mt5.ORDER_TYPE_SELL_STOP_LIMIT
    raise ValueError(f"Unknown order type: {order_type}")


def mt5_error_message(code: int) -> str:
    """Convert MT5 error code to human-readable message."""
    errors = {
        mt5.RES_S_OK: "Success",
        10004: "Requote",
        10006: "Request rejected",
        10007: "Request cancelled by trader",
        10008: "Order placed",
        10009: "Request completed",
        10010: "Request partially completed",
        10011: "Request processing error",
        10012: "Request cancelled by timeout",
        10013: "Invalid request",
        10014: "Invalid volume",
        10015: "Invalid price",
        10016: "Invalid stops",
        10017: "Trade disabled",
        10018: "Market closed",
        10019: "Insufficient funds",
        10020: "Prices changed",
        10021: "No quotes available",
        10022: "Invalid order expiration",
        10023: "Order state changed",
        10024: "Too frequent requests",
        10025: "No changes in request",
        10026: "Auto-trading disabled by server",
        10027: "Auto-trading disabled by client",
        10028: "Request locked for processing",
        10029: "Order or position frozen",
        10030: "Invalid order filling type",
        10031: "No connection to trade server",
        10032: "Operation allowed only for live accounts",
        10033: "Pending orders limit reached",
        10034: "Volume limit for symbol reached",
        10035: "Invalid or prohibited order type",
        10036: "Position with specified ticket not found",
        10038: "Close order already exists",
        10039: "Close volume exceeds position volume",
        10040: "Position already closed",
        10041: "Account limit reached",
        10042: "Position opening limit reached",
        10043: "Pending order limit for symbol reached",
        10044: "Only position closing allowed",
        10045: "Position close not allowed",
    }
    return errors.get(code, f"Unknown error code: {code}")


def rates_to_bars(rates, symbol: str) -> list[Bar]:
    """Convert MT5 rates array to list of Bar models."""
    bars = []
    for rate in rates:
        bars.append(
            Bar(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(rate[0], tz=UTC),
                open=float(rate[1]),
                high=float(rate[2]),
                low=float(rate[3]),
                close=float(rate[4]),
                tick_volume=float(rate[5]),
                spread=int(rate[6]),
                volume=float(rate[7]) if len(rate) > 7 else float(rate[5]),
            )
        )
    return bars


def tick_to_model(tick_data, symbol: str) -> Tick:
    """Convert MT5 tick struct to Tick model."""
    return Tick(
        symbol=symbol,
        timestamp=datetime.fromtimestamp(tick_data.time, tz=UTC),
        bid=float(tick_data.bid),
        ask=float(tick_data.ask),
        last=float(tick_data.last),
        volume=float(tick_data.volume),
    )


def mt5_position_to_model(pos) -> Position:
    """Convert MT5 position to our Position model."""
    side = OrderSide.BUY if pos.type == mt5.POSITION_TYPE_BUY else OrderSide.SELL
    return Position(
        symbol=pos.symbol,
        side=side,
        quantity=pos.volume,
        entry_price=pos.price_open,
        current_price=pos.price_current,
        stop_loss=pos.sl if pos.sl != 0.0 else None,
        take_profit=pos.tp if pos.tp != 0.0 else None,
        unrealized_pnl=pos.profit,
        ticket=pos.ticket,
        open_time=datetime.fromtimestamp(pos.time, tz=UTC),
    )
