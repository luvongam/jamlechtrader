"""MT5 connection management: initialize, login, shutdown, account info."""

from __future__ import annotations

from dataclasses import dataclass

import MetaTrader5 as mt5
from loguru import logger

from jamlechtrader.config.settings import Settings


@dataclass
class AccountInfo:
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    leverage: int
    currency: str
    name: str
    company: str


class MT5Connection:
    """Manages the MetaTrader 5 terminal connection."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connected = False

    def connect(self) -> bool:
        """Initialize MT5 and log in."""
        kwargs = {}
        if self._settings.mt5_path:
            kwargs["path"] = self._settings.mt5_path

        if not mt5.initialize(**kwargs):
            logger.error(f"MT5 initialize failed: {mt5.last_error()}")
            return False

        if self._settings.mt5_login:
            authorized = mt5.login(
                login=self._settings.mt5_login,
                password=self._settings.mt5_password,
                server=self._settings.mt5_server,
            )
            if not authorized:
                logger.error(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False

        self._connected = True
        logger.info("MT5 connected successfully")
        return True

    def disconnect(self) -> None:
        """Shut down MT5 connection."""
        if self._connected:
            mt5.shutdown()
            self._connected = False
            logger.info("MT5 disconnected")

    @property
    def is_connected(self) -> bool:
        if not self._connected:
            return False
        info = mt5.terminal_info()
        return info is not None

    def account_info(self) -> AccountInfo | None:
        """Retrieve current account information."""
        info = mt5.account_info()
        if info is None:
            logger.error(f"Failed to get account info: {mt5.last_error()}")
            return None
        return AccountInfo(
            login=info.login,
            server=info.server,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            leverage=info.leverage,
            currency=info.currency,
            name=info.name,
            company=info.company,
        )

    def __enter__(self) -> MT5Connection:
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.disconnect()
