"""Bridge client — drop-in replacements for MT5Connection/Executor/Data over HTTP.

When ``MT5_BRIDGE_URL`` is set, these classes communicate with the ``mt5_bridge.py``
FastAPI server running on a Windows machine instead of calling MetaTrader5 directly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pandas as pd
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from jamlechtrader.config.settings import Settings
from jamlechtrader.core.enums import OrderSide, Timeframe
from jamlechtrader.core.models import Bar, Fill, Order, Position, Tick
from jamlechtrader.mt5.connection import AccountInfo
from jamlechtrader.resilience.circuit_breaker import CircuitBreaker

# ---------------------------------------------------------------------------
# Shared HTTP helper
# ---------------------------------------------------------------------------

_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 30.0


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _bridge_request(
    client: httpx.Client,
    method: str,
    path: str,
    **kwargs: Any,
) -> httpx.Response:
    """Make an HTTP request to the bridge server with retry."""
    logger.debug(f"Bridge {method} {path}")
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response


# ---------------------------------------------------------------------------
# BridgeMT5Connection
# ---------------------------------------------------------------------------


class BridgeMT5Connection:
    """Connects to MT5 via the HTTP bridge server."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.mt5_bridge_url.rstrip("/")
        self._client: httpx.Client | None = None
        self._connected = False
        self.circuit_breaker = CircuitBreaker(
            name="mt5_bridge_connection",
            failure_threshold=5,
            recovery_timeout=30.0,
        )

    def _ensure_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self._base_url,
                timeout=httpx.Timeout(_READ_TIMEOUT, connect=_CONNECT_TIMEOUT),
            )
        return self._client

    def connect(self) -> bool:
        """Verify the bridge server is up and MT5 is connected."""
        try:
            client = self._ensure_client()
            resp = _bridge_request(client, "GET", "/health")
            data = resp.json()
            if not data.get("mt5_connected"):
                logger.error("Bridge reports MT5 not connected")
                self.circuit_breaker.record_failure()
                return False
            self._connected = True
            self.circuit_breaker.record_success()
            logger.info(f"Connected to MT5 bridge at {self._base_url}")
            return True
        except Exception as e:
            logger.error(f"Bridge connect failed: {e}")
            self.circuit_breaker.record_failure()
            return False

    def disconnect(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            self._client.close()
        self._connected = False
        logger.info("Disconnected from MT5 bridge")

    def reconnect(self) -> bool:
        """Disconnect and reconnect."""
        self.disconnect()
        return self.connect()

    @property
    def is_connected(self) -> bool:
        if not self._connected:
            return False
        try:
            client = self._ensure_client()
            resp = client.get("/health", timeout=5.0)
            data = resp.json()
            return data.get("mt5_connected", False)
        except Exception:
            return False

    def account_info(self) -> AccountInfo | None:
        """Retrieve account information from the bridge."""
        try:
            client = self._ensure_client()
            resp = _bridge_request(client, "GET", "/account")
            data = resp.json()
            return AccountInfo(
                login=data["login"],
                server=data.get("server", ""),
                balance=data["balance"],
                equity=data["equity"],
                margin=data["margin"],
                free_margin=data["free_margin"],
                leverage=data["leverage"],
                currency=data.get("currency", "USD"),
                name=data.get("name", ""),
                company=data.get("company", ""),
            )
        except Exception as e:
            logger.error(f"Bridge account_info failed: {e}")
            return None

    def __enter__(self) -> BridgeMT5Connection:
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.disconnect()


# ---------------------------------------------------------------------------
# BridgeMT5Executor
# ---------------------------------------------------------------------------


class BridgeMT5Executor:
    """Executes orders via the bridge server."""

    def __init__(self, base_url: str, circuit_breaker: CircuitBreaker | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client: httpx.Client | None = None
        self._cb = circuit_breaker or CircuitBreaker(
            name="mt5_bridge_executor", failure_threshold=5, recovery_timeout=30.0
        )

    def _ensure_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self._base_url,
                timeout=httpx.Timeout(_READ_TIMEOUT, connect=_CONNECT_TIMEOUT),
            )
        return self._client

    def send_order(self, order: Order) -> Fill | None:
        """Send an order via the bridge and return a Fill on success."""
        if not self._cb.allow_request():
            logger.error("Circuit breaker open — order rejected")
            return None

        # Map OrderType + OrderSide to bridge order_type string
        order_type_str = _to_bridge_order_type(order.order_type.value, order.side.value)

        payload: dict[str, Any] = {
            "symbol": order.symbol,
            "order_type": order_type_str,
            "volume": order.quantity,
            "comment": order.comment or "jamlechtrader",
        }
        if order.price is not None:
            payload["price"] = order.price
        if order.stop_loss is not None:
            payload["sl"] = order.stop_loss
        if order.take_profit is not None:
            payload["tp"] = order.take_profit

        try:
            client = self._ensure_client()
            resp = _bridge_request(client, "POST", "/order", json=payload)
            data = resp.json()
            self._cb.record_success()
            logger.info(f"Bridge order filled: {order.symbol} {order.side.value} {order.quantity} @ {data['price']}")
            return Fill(
                id=str(data.get("deal_id", "")),
                order_id=str(data["order_id"]),
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=data["price"],
            )
        except Exception as e:
            logger.error(f"Bridge send_order failed: {e}")
            self._cb.record_failure()
            return None

    def close_position(self, position: Position) -> Fill | None:
        """Close a position via the bridge."""
        if not self._cb.allow_request():
            logger.error("Circuit breaker open — close rejected")
            return None

        close_side = OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY

        payload = {
            "ticket": position.ticket,
            "symbol": position.symbol,
            "volume": position.quantity,
            "side": position.side.value,
        }

        try:
            client = self._ensure_client()
            resp = _bridge_request(client, "POST", "/close", json=payload)
            data = resp.json()
            self._cb.record_success()
            logger.info(f"Bridge position closed: {position.symbol} ticket={position.ticket}")
            return Fill(
                id=str(data.get("deal_id", "")),
                order_id=str(data["order_id"]),
                symbol=position.symbol,
                side=close_side,
                quantity=position.quantity,
                price=data["price"],
            )
        except Exception as e:
            logger.error(f"Bridge close_position failed: {e}")
            self._cb.record_failure()
            return None

    def modify_position(
        self,
        ticket: int,
        symbol: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> bool:
        """Modify SL/TP via the bridge."""
        payload: dict[str, Any] = {"ticket": ticket, "symbol": symbol}
        if stop_loss is not None:
            payload["sl"] = stop_loss
        if take_profit is not None:
            payload["tp"] = take_profit

        try:
            client = self._ensure_client()
            resp = _bridge_request(client, "POST", "/modify", json=payload)
            return resp.json().get("success", False)
        except Exception as e:
            logger.error(f"Bridge modify_position failed: {e}")
            return False

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        """Get open positions from the bridge."""
        try:
            client = self._ensure_client()
            path = f"/positions/{symbol}" if symbol else "/positions"
            resp = _bridge_request(client, "GET", path)
            data = resp.json()
            return [_parse_position(p) for p in data.get("positions", [])]
        except Exception as e:
            logger.error(f"Bridge get_positions failed: {e}")
            return []

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        """Get pending orders from the bridge."""
        try:
            client = self._ensure_client()
            path = f"/orders/{symbol}" if symbol else "/orders"
            resp = _bridge_request(client, "GET", path)
            data = resp.json()
            return data.get("orders", [])
        except Exception as e:
            logger.error(f"Bridge get_open_orders failed: {e}")
            return []


# ---------------------------------------------------------------------------
# BridgeMT5Data
# ---------------------------------------------------------------------------


class BridgeMT5Data:
    """Retrieves market data via the bridge server."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client: httpx.Client | None = None

    def _ensure_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self._base_url,
                timeout=httpx.Timeout(_READ_TIMEOUT, connect=_CONNECT_TIMEOUT),
            )
        return self._client

    def get_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        """Fetch historical bars from the bridge."""
        payload = {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        try:
            client = self._ensure_client()
            resp = _bridge_request(client, "POST", "/bars", json=payload)
            data = resp.json()
            return [_parse_bar(b, symbol) for b in data.get("bars", [])]
        except Exception as e:
            logger.warning(f"Bridge get_bars failed: {e}")
            return []

    def get_bars_df(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Fetch historical bars as a DataFrame."""
        bars = self.get_bars(symbol, timeframe, start, end)
        if not bars:
            return pd.DataFrame()
        df = pd.DataFrame([b.model_dump() for b in bars])
        df.set_index("timestamp", inplace=True)
        return df

    def get_latest_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 100,
    ) -> list[Bar]:
        """Fetch the most recent N bars from the bridge."""
        payload = {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "count": count,
        }
        try:
            client = self._ensure_client()
            resp = _bridge_request(client, "POST", "/bars/latest", json=payload)
            data = resp.json()
            return [_parse_bar(b, symbol) for b in data.get("bars", [])]
        except Exception as e:
            logger.warning(f"Bridge get_latest_bars failed: {e}")
            return []

    def get_ticks(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        flags: int = 0,
    ) -> list[Tick]:
        """Bulk tick history is impractical over HTTP — returns empty list."""
        logger.warning("get_ticks() not supported via bridge — use get_current_tick()")
        return []

    def get_current_tick(self, symbol: str) -> Tick | None:
        """Get the latest tick for a symbol from the bridge."""
        try:
            client = self._ensure_client()
            resp = _bridge_request(client, "GET", f"/tick/{symbol}")
            data = resp.json()
            return Tick(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(data["time"], tz=UTC),
                bid=data["bid"],
                ask=data["ask"],
                last=data.get("last", 0.0),
                volume=data.get("volume", 0.0),
            )
        except Exception as e:
            logger.warning(f"Bridge get_current_tick failed: {e}")
            return None

    def get_symbols(self, group: str = "") -> list[str]:
        """Get available symbol names from the bridge."""
        try:
            client = self._ensure_client()
            params = {"group": group} if group else {}
            resp = _bridge_request(client, "GET", "/symbols", params=params)
            data = resp.json()
            return [s["name"] for s in data.get("symbols", [])]
        except Exception as e:
            logger.warning(f"Bridge get_symbols failed: {e}")
            return []

    def symbol_info(self, symbol: str) -> dict | None:
        """Get detailed symbol information from the bridge."""
        try:
            client = self._ensure_client()
            resp = _bridge_request(client, "GET", f"/symbol/{symbol}")
            return resp.json()
        except Exception as e:
            logger.warning(f"Bridge symbol_info failed: {e}")
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_bridge_order_type(order_type: str, side: str) -> str:
    """Convert OrderType + OrderSide to the bridge order_type string."""
    if order_type == "MARKET":
        return side  # "BUY" or "SELL"
    # e.g. "LIMIT" + "BUY" -> "BUY_LIMIT"
    return f"{side}_{order_type}"


def _parse_bar(data: dict, symbol: str) -> Bar:
    """Parse a bar dict from the bridge response."""
    return Bar(
        symbol=symbol,
        timestamp=datetime.fromtimestamp(data["time"], tz=UTC),
        open=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        volume=data.get("volume", data.get("tick_volume", 0)),
        tick_volume=data.get("tick_volume", 0),
        spread=data.get("spread", 0),
    )


def _parse_position(data: dict) -> Position:
    """Parse a position dict from the bridge response."""
    side = OrderSide.BUY if data["type"] == 0 else OrderSide.SELL
    return Position(
        symbol=data["symbol"],
        side=side,
        quantity=data["volume"],
        entry_price=data["price_open"],
        current_price=data.get("price_current", 0.0),
        stop_loss=data["sl"] if data.get("sl", 0) != 0 else None,
        take_profit=data["tp"] if data.get("tp", 0) != 0 else None,
        unrealized_pnl=data.get("profit", 0.0),
        ticket=data["ticket"],
        open_time=datetime.fromtimestamp(data.get("time", 0), tz=UTC),
    )
