"""MT5 API Bridge - Run on Windows, access from Linux."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import MetaTrader5 as mt5
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="MT5 API Bridge")

# All 21 MT5 timeframes
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M2": mt5.TIMEFRAME_M2,
    "M3": mt5.TIMEFRAME_M3,
    "M4": mt5.TIMEFRAME_M4,
    "M5": mt5.TIMEFRAME_M5,
    "M6": mt5.TIMEFRAME_M6,
    "M10": mt5.TIMEFRAME_M10,
    "M12": mt5.TIMEFRAME_M12,
    "M15": mt5.TIMEFRAME_M15,
    "M20": mt5.TIMEFRAME_M20,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H2": mt5.TIMEFRAME_H2,
    "H3": mt5.TIMEFRAME_H3,
    "H4": mt5.TIMEFRAME_H4,
    "H6": mt5.TIMEFRAME_H6,
    "H8": mt5.TIMEFRAME_H8,
    "H12": mt5.TIMEFRAME_H12,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

# All MT5 order types
ORDER_TYPE_MAP = {
    "BUY": mt5.ORDER_TYPE_BUY,
    "SELL": mt5.ORDER_TYPE_SELL,
    "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
    "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
    "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
    "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP,
    "BUY_STOP_LIMIT": mt5.ORDER_TYPE_BUY_STOP_LIMIT,
    "SELL_STOP_LIMIT": mt5.ORDER_TYPE_SELL_STOP_LIMIT,
}


class BarRequest(BaseModel):
    symbol: str
    timeframe: str
    start: str
    end: str


class LatestBarsRequest(BaseModel):
    symbol: str
    timeframe: str
    count: int = 100


class OrderRequest(BaseModel):
    symbol: str
    order_type: str
    volume: float
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    comment: str = "JamlechTrader"


class CloseRequest(BaseModel):
    ticket: int
    symbol: str
    volume: float
    side: str  # "BUY" or "SELL" — the position side (close uses opposite)


class ModifyRequest(BaseModel):
    ticket: int
    symbol: str
    sl: float | None = None
    tp: float | None = None


def _format_rate(r) -> dict[str, Any]:
    """Convert a single MT5 rate to a dict."""
    return {
        "time": int(r[0]),
        "open": float(r[1]),
        "high": float(r[2]),
        "low": float(r[3]),
        "close": float(r[4]),
        "tick_volume": float(r[5]),
        "spread": int(r[6]),
        "volume": float(r[7]) if len(r) > 7 else float(r[5]),
    }


def _format_position(p) -> dict[str, Any]:
    """Convert an MT5 position to a dict."""
    return {
        "ticket": p.ticket,
        "symbol": p.symbol,
        "type": p.type,
        "volume": p.volume,
        "price_open": p.price_open,
        "price_current": p.price_current,
        "sl": p.sl,
        "tp": p.tp,
        "profit": p.profit,
        "time": p.time,
        "comment": p.comment,
    }


def _format_order(o) -> dict[str, Any]:
    """Convert an MT5 pending order to a dict."""
    return {
        "ticket": o.ticket,
        "symbol": o.symbol,
        "type": o.type,
        "volume": o.volume_current,
        "price": o.price_open,
        "sl": o.sl,
        "tp": o.tp,
        "comment": o.comment,
    }


@app.on_event("startup")
async def startup():
    """Initialize MT5 connection."""
    if not mt5.initialize():
        raise RuntimeError("MT5 initialization failed")


@app.on_event("shutdown")
async def shutdown():
    """Shutdown MT5 connection."""
    mt5.shutdown()


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "mt5_connected": mt5.terminal_info() is not None}


@app.get("/account")
async def get_account():
    """Get account information."""
    info = mt5.account_info()
    if info is None:
        raise HTTPException(status_code=500, detail="Failed to get account info")

    return {
        "login": info.login,
        "balance": info.balance,
        "equity": info.equity,
        "margin": info.margin,
        "free_margin": info.margin_free,
        "leverage": info.leverage,
        "server": info.server,
        "currency": info.currency,
        "name": info.name,
        "company": info.company,
    }


@app.post("/bars")
async def get_bars(request: BarRequest):
    """Get historical bars by date range."""
    tf = TIMEFRAME_MAP.get(request.timeframe)
    if tf is None:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe: {request.timeframe}")

    start = datetime.fromisoformat(request.start)
    end = datetime.fromisoformat(request.end)

    rates = mt5.copy_rates_range(request.symbol, tf, start, end)

    if rates is None:
        raise HTTPException(status_code=404, detail="No data found")

    return {"bars": [_format_rate(r) for r in rates]}


@app.post("/bars/latest")
async def get_latest_bars(request: LatestBarsRequest):
    """Get the most recent N bars."""
    tf = TIMEFRAME_MAP.get(request.timeframe)
    if tf is None:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe: {request.timeframe}")

    rates = mt5.copy_rates_from_pos(request.symbol, tf, 0, request.count)

    if rates is None:
        raise HTTPException(status_code=404, detail="No data found")

    return {"bars": [_format_rate(r) for r in rates]}


@app.get("/tick/{symbol}")
async def get_tick(symbol: str):
    """Get the current tick for a symbol."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise HTTPException(status_code=404, detail=f"No tick for {symbol}")

    return {
        "bid": float(tick.bid),
        "ask": float(tick.ask),
        "last": float(tick.last),
        "volume": float(tick.volume),
        "time": tick.time,
    }


@app.post("/order")
async def place_order(request: OrderRequest):
    """Place an order (market, limit, stop, or stop-limit)."""
    order_type = ORDER_TYPE_MAP.get(request.order_type)
    if order_type is None:
        raise HTTPException(status_code=400, detail=f"Invalid order type: {request.order_type}")

    symbol_info = mt5.symbol_info(request.symbol)
    if symbol_info is None:
        raise HTTPException(status_code=404, detail="Symbol not found")

    is_market = request.order_type in ("BUY", "SELL")
    if is_market:
        price = request.price or (
            symbol_info.ask if order_type == mt5.ORDER_TYPE_BUY else symbol_info.bid
        )
        action = mt5.TRADE_ACTION_DEAL
    else:
        if request.price is None:
            raise HTTPException(status_code=400, detail="Price required for pending orders")
        price = request.price
        action = mt5.TRADE_ACTION_PENDING

    order_request = {
        "action": action,
        "symbol": request.symbol,
        "volume": request.volume,
        "type": order_type,
        "price": price,
        "sl": request.sl or 0,
        "tp": request.tp or 0,
        "deviation": 20,
        "magic": 234000,
        "comment": request.comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(order_request)

    if result is None:
        raise HTTPException(status_code=500, detail="order_send returned None")

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=500, detail=f"Order failed: {result.comment}")

    return {
        "order_id": result.order,
        "deal_id": result.deal,
        "volume": result.volume,
        "price": result.price,
        "comment": result.comment,
    }


@app.post("/close")
async def close_position(request: CloseRequest):
    """Close an open position by ticket."""
    # Determine close side (opposite of position side)
    if request.side == "BUY":
        close_type = mt5.ORDER_TYPE_SELL
    else:
        close_type = mt5.ORDER_TYPE_BUY

    tick = mt5.symbol_info_tick(request.symbol)
    if tick is None:
        raise HTTPException(status_code=404, detail=f"No tick for {request.symbol}")

    price = tick.bid if request.side == "BUY" else tick.ask

    close_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": request.symbol,
        "volume": request.volume,
        "type": close_type,
        "position": request.ticket,
        "price": price,
        "deviation": 20,
        "magic": 234000,
        "comment": "JamlechTrader close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(close_request)

    if result is None:
        raise HTTPException(status_code=500, detail="close order_send returned None")

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=500, detail=f"Close failed: {result.comment}")

    return {
        "order_id": result.order,
        "deal_id": result.deal,
        "volume": result.volume,
        "price": result.price,
        "comment": result.comment,
    }


@app.post("/modify")
async def modify_position(request: ModifyRequest):
    """Modify SL/TP of an open position."""
    modify_request: dict[str, Any] = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": request.symbol,
        "position": request.ticket,
    }
    if request.sl is not None:
        modify_request["sl"] = request.sl
    if request.tp is not None:
        modify_request["tp"] = request.tp

    result = mt5.order_send(modify_request)

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=500, detail="Modify failed")

    return {"success": True}


@app.get("/positions")
async def get_positions():
    """Get all open positions."""
    positions = mt5.positions_get()
    if positions is None:
        return {"positions": []}
    return {"positions": [_format_position(p) for p in positions]}


@app.get("/positions/{symbol}")
async def get_positions_by_symbol(symbol: str):
    """Get open positions filtered by symbol."""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return {"positions": []}
    return {"positions": [_format_position(p) for p in positions]}


@app.get("/orders")
async def get_orders():
    """Get all pending orders."""
    orders = mt5.orders_get()
    if orders is None:
        return {"orders": []}
    return {"orders": [_format_order(o) for o in orders]}


@app.get("/orders/{symbol}")
async def get_orders_by_symbol(symbol: str):
    """Get pending orders filtered by symbol."""
    orders = mt5.orders_get(symbol=symbol)
    if orders is None:
        return {"orders": []}
    return {"orders": [_format_order(o) for o in orders]}


@app.get("/symbols")
async def get_symbols(group: str = ""):
    """Get available symbols."""
    if group:
        symbols = mt5.symbols_get(group=group)
    else:
        symbols = mt5.symbols_get()
    if symbols is None:
        return {"symbols": []}

    return {
        "symbols": [
            {
                "name": s.name,
                "description": s.description,
                "digits": s.digits,
            }
            for s in symbols
        ]
    }


@app.get("/symbol/{symbol}")
async def get_symbol_info(symbol: str):
    """Get detailed symbol information."""
    info = mt5.symbol_info(symbol)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol}")

    return {
        "name": info.name,
        "description": info.description,
        "point": info.point,
        "digits": info.digits,
        "spread": info.spread,
        "trade_contract_size": info.trade_contract_size,
        "volume_min": info.volume_min,
        "volume_max": info.volume_max,
        "volume_step": info.volume_step,
        "currency_base": info.currency_base,
        "currency_profit": info.currency_profit,
        "currency_margin": info.currency_margin,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
