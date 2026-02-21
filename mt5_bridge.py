"""MT5 API Bridge - Run on Windows, access from Linux."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import MetaTrader5 as mt5
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="MT5 API Bridge")


class BarRequest(BaseModel):
    symbol: str
    timeframe: str
    start: str
    end: str


class OrderRequest(BaseModel):
    symbol: str
    order_type: str
    volume: float
    price: float | None = None
    sl: float | None = None
    tp: float | None = None


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
        "free_margin": info.free_margin,
        "leverage": info.leverage,
    }


@app.post("/bars")
async def get_bars(request: BarRequest):
    """Get historical bars."""
    timeframe_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    
    tf = timeframe_map.get(request.timeframe, mt5.TIMEFRAME_H1)
    start = datetime.fromisoformat(request.start)
    end = datetime.fromisoformat(request.end)
    
    rates = mt5.copy_rates_range(request.symbol, tf, start, end)
    
    if rates is None:
        raise HTTPException(status_code=404, detail="No data found")
    
    return {
        "bars": [
            {
                "time": int(r[0]),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": int(r[5]),
            }
            for r in rates
        ]
    }


@app.post("/order")
async def place_order(request: OrderRequest):
    """Place an order."""
    order_type_map = {
        "BUY": mt5.ORDER_TYPE_BUY,
        "SELL": mt5.ORDER_TYPE_SELL,
    }
    
    order_type = order_type_map.get(request.order_type)
    if order_type is None:
        raise HTTPException(status_code=400, detail="Invalid order type")
    
    symbol_info = mt5.symbol_info(request.symbol)
    if symbol_info is None:
        raise HTTPException(status_code=404, detail="Symbol not found")
    
    price = request.price or (symbol_info.ask if order_type == mt5.ORDER_TYPE_BUY else symbol_info.bid)
    
    order_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": request.symbol,
        "volume": request.volume,
        "type": order_type,
        "price": price,
        "sl": request.sl or 0,
        "tp": request.tp or 0,
        "deviation": 20,
        "magic": 234000,
        "comment": "JamlechTrader",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(order_request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=500, detail=f"Order failed: {result.comment}")
    
    return {
        "order_id": result.order,
        "volume": result.volume,
        "price": result.price,
        "comment": result.comment,
    }


@app.get("/symbols")
async def get_symbols():
    """Get available symbols."""
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
