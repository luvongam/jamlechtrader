"""MT5 Remote Client - Connect from Linux to Windows MT5 bridge."""

from __future__ import annotations

from datetime import datetime

import requests
from loguru import logger

from jamlechtrader.core.enums import Timeframe
from jamlechtrader.core.models import Bar
from jamlechtrader.data.base import AbstractDataProvider


class MT5RemoteProvider(AbstractDataProvider):
    """Connect to remote MT5 API bridge running on Windows."""

    def __init__(self, host: str = "localhost", port: int = 8000):
        self.base_url = f"http://{host}:{port}"
        self._check_connection()

    def _check_connection(self):
        """Verify connection to MT5 bridge."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            response.raise_for_status()
            logger.info("Connected to MT5 bridge")
        except Exception as e:
            logger.error(f"Failed to connect to MT5 bridge: {e}")
            raise

    def get_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        """Fetch historical bars from remote MT5."""
        response = requests.post(
            f"{self.base_url}/bars",
            json={
                "symbol": symbol,
                "timeframe": timeframe.value,
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
            timeout=30,
        )
        response.raise_for_status()
        
        data = response.json()
        return [
            Bar(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(bar["time"]),
                open=bar["open"],
                high=bar["high"],
                low=bar["low"],
                close=bar["close"],
                volume=bar["volume"],
            )
            for bar in data["bars"]
        ]

    def place_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float | None = None,
        sl: float | None = None,
        tp: float | None = None,
    ) -> dict:
        """Place order via remote MT5."""
        response = requests.post(
            f"{self.base_url}/order",
            json={
                "symbol": symbol,
                "order_type": order_type,
                "volume": volume,
                "price": price,
                "sl": sl,
                "tp": tp,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_account_info(self) -> dict:
        """Get account information."""
        response = requests.get(f"{self.base_url}/account", timeout=5)
        response.raise_for_status()
        return response.json()

    def get_symbols(self) -> list[str]:
        """Get available symbols."""
        response = requests.get(f"{self.base_url}/symbols", timeout=10)
        response.raise_for_status()
        data = response.json()
        return [s["name"] for s in data["symbols"]]
