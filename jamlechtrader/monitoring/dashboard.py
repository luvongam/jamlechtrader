"""FastAPI monitoring dashboard with REST API and WebSocket live feed."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from prometheus_client import generate_latest

from jamlechtrader.monitoring.health import HealthChecker

app = FastAPI(title="JamlechTrader Dashboard", version="0.1.0")

# Shared state — injected at startup
_health_checker: HealthChecker | None = None
_portfolio_fn = None
_orders_fn = None
_positions_fn = None
_ws_clients: list[WebSocket] = []


def configure_dashboard(
    health_checker: HealthChecker | None = None,
    portfolio_fn=None,
    orders_fn=None,
    positions_fn=None,
) -> None:
    """Inject dependencies into the dashboard."""
    global _health_checker, _portfolio_fn, _orders_fn, _positions_fn
    _health_checker = health_checker
    _portfolio_fn = portfolio_fn
    _orders_fn = orders_fn
    _positions_fn = positions_fn


@app.get("/health")
async def health():
    if _health_checker is None:
        return {"status": "unknown", "message": "Health checker not configured"}
    result = _health_checker.check()
    return result.to_dict()


@app.get("/metrics")
async def metrics():
    from fastapi.responses import Response
    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


@app.get("/api/portfolio")
async def portfolio():
    if _portfolio_fn is None:
        return {"error": "Portfolio not configured"}
    data = _portfolio_fn()
    return data


@app.get("/api/orders")
async def orders():
    if _orders_fn is None:
        return {"error": "Orders not configured"}
    return _orders_fn()


@app.get("/api/positions")
async def positions():
    if _positions_fn is None:
        return {"error": "Positions not configured"}
    return _positions_fn()


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            # Keep connection alive; send periodic updates
            data: dict[str, Any] = {"type": "heartbeat", "timestamp": datetime.now(tz=UTC).isoformat()}

            if _portfolio_fn:
                data["portfolio"] = _portfolio_fn()
            if _health_checker:
                data["health"] = _health_checker.check().to_dict()

            await ws.send_json(data)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        _ws_clients.remove(ws)
    except Exception:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


async def broadcast(data: dict[str, Any]) -> None:
    """Broadcast data to all connected WebSocket clients."""
    disconnected = []
    for ws in _ws_clients:
        try:
            await ws.send_json(data)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _ws_clients.remove(ws)


_DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>JamlechTrader Dashboard</title>
    <meta charset="utf-8">
    <style>
        body { font-family: monospace; background: #1a1a2e; color: #e0e0e0; padding: 20px; }
        h1 { color: #00ff88; }
        .card { background: #16213e; border: 1px solid #0f3460; border-radius: 8px;
                padding: 16px; margin: 10px 0; }
        .healthy { color: #00ff88; }
        .degraded { color: #ffaa00; }
        .unhealthy { color: #ff4444; }
        table { border-collapse: collapse; width: 100%; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #0f3460; }
        th { color: #00ff88; }
        #live-data { white-space: pre-wrap; }
    </style>
</head>
<body>
    <h1>JamlechTrader Dashboard</h1>
    <div class="card">
        <h2>Health</h2>
        <div id="health">Loading...</div>
    </div>
    <div class="card">
        <h2>Portfolio</h2>
        <div id="portfolio">Loading...</div>
    </div>
    <div class="card">
        <h2>Live Feed</h2>
        <div id="live-data">Connecting...</div>
    </div>
    <script>
        async function fetchHealth() {
            const resp = await fetch('/health');
            const data = await resp.json();
            document.getElementById('health').innerHTML =
                '<span class="' + data.status + '">' + data.status.toUpperCase() + '</span>' +
                ' | Uptime: ' + Math.floor(data.uptime_seconds) + 's';
        }
        async function fetchPortfolio() {
            const resp = await fetch('/api/portfolio');
            const data = await resp.json();
            document.getElementById('portfolio').textContent = JSON.stringify(data, null, 2);
        }
        const ws = new WebSocket('ws://' + location.host + '/ws/live');
        ws.onmessage = function(event) {
            document.getElementById('live-data').textContent = JSON.stringify(JSON.parse(event.data), null, 2);
        };
        ws.onerror = function() {
            document.getElementById('live-data').textContent = 'WebSocket error';
        };
        setInterval(fetchHealth, 5000);
        setInterval(fetchPortfolio, 5000);
        fetchHealth();
        fetchPortfolio();
    </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard_page():
    return _DASHBOARD_HTML
